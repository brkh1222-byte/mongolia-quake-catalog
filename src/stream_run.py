"""Full laptop run, stage 1: stream station-days through the pickers
(download -> pick with every model/weight pair -> ensemble -> save picks ->
delete waveform). Continuous data are never kept; see docs/laptop_runbook.md.

Progress ledger: data/ledger.sqlite, table `station_day`
  (station, day, status, bytes, dl_s, pick_s, n_ens, worker, updated)
  status: todo -> downloading -> downloaded -> done | nodata | error
Every state change is committed at once, so a crash, reboot or sleeping laptop
loses at most the station-days in flight. On start-up, rows stuck in
'downloading'/'downloaded' that belong to no live worker are reset to 'todo'
(stale buffer files are reused if complete).

Concurrency: one process = one picking loop (the heavy part, on --device) plus
a small pool of download threads that keep up to --prefetch station-days in
data/buffer/ ahead of the picker. Run at most two processes at once (shared
machine); they claim work atomically from the ledger, so any number can start
and stop at any time.

Each station-day is fetched as one dataselect request for
[day - 60 s, day + 1 d + 60 s], so picks at midnight are not lost; only picks
inside the day are stored.

Examples
  python src/stream_run.py init  --stations HD --start 2012-06-10 --end 2014-04-11
  caffeinate -i nice -n 10 python src/stream_run.py run --device mps --worker w1
  python src/stream_run.py status
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import os
import queue
import socket
import sqlite3
import threading
import time

import numpy as np
import pandas as pd
from obspy import UTCDateTime, read

from common import base_parser, days, get_logger, load_config, path, select_stations

LEDGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS station_day (
  station TEXT, day TEXT, subarray TEXT, prio INTEGER, status TEXT DEFAULT 'todo',
  bytes INTEGER, dl_s REAL, pick_s REAL, n_ens INTEGER, worker TEXT, updated REAL,
  PRIMARY KEY (station, day));
CREATE INDEX IF NOT EXISTS ix_status ON station_day(status, prio, day);
CREATE TABLE IF NOT EXISTS workers (worker TEXT PRIMARY KEY, pid INTEGER, host TEXT, started REAL, beat REAL);
"""
SUBARRAY_PRIO = {"HD": 0, "HV": 1, "AT": 2}  # Hangay first


def ledger(cfg) -> sqlite3.Connection:
    f = path(cfg, "data") / "ledger.sqlite"
    f.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(f), timeout=60, isolation_level=None, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(LEDGER_SCHEMA)
    return con


def cmd_init(cfg, args, log):
    con = ledger(cfg)
    start = args.start or cfg["time"]["start"]
    end = args.end or cfg["time"]["end"]
    st = select_stations(cfg, args.stations or "all", start, end)
    rows = []
    for s in st.itertuples():
        for t in days(max(UTCDateTime(start), UTCDateTime(s.start.date())),
                      min(UTCDateTime(end), UTCDateTime(s.end) + 1)):
            rows.append((s.station, str(t.date), s.subarray, SUBARRAY_PRIO.get(s.subarray, 9)))
    con.executemany("INSERT OR IGNORE INTO station_day(station, day, subarray, prio) VALUES (?,?,?,?)", rows)
    log.info("ledger now has %d station-days (%d offered)",
             con.execute("SELECT COUNT(*) FROM station_day").fetchone()[0], len(rows))


def cmd_mark_done_from_existing(cfg, args, log):
    """Mark station-days already picked by src/pick.py (e.g. the pilot month) as done."""
    from ensemble import ens_path

    con = ledger(cfg)
    net = cfg["fdsn"]["network"]
    n = 0
    for sta, day in con.execute("SELECT station, day FROM station_day WHERE status='todo'").fetchall():
        if ens_path(cfg, net, sta, UTCDateTime(day)).exists():
            con.execute("UPDATE station_day SET status='done', worker='pilot', updated=? "
                        "WHERE station=? AND day=?", (time.time(), sta, day))
            n += 1
    log.info("marked %d station-days done from existing ensemble picks", n)


def cmd_status(cfg, args, log):
    con = ledger(cfg)
    df = pd.read_sql("SELECT subarray, status, COUNT(*) n, SUM(bytes)/1e9 gb, AVG(dl_s) dl_s, "
                     "AVG(pick_s) pick_s FROM station_day GROUP BY subarray, status", con)
    print(df.to_string(index=False))
    done = pd.read_sql("SELECT updated, bytes FROM station_day WHERE status='done' AND worker!='pilot' "
                       "ORDER BY updated", con)
    tot = con.execute("SELECT COUNT(*) FROM station_day").fetchone()[0]
    ndone = con.execute("SELECT COUNT(*) FROM station_day WHERE status IN ('done','nodata')").fetchone()[0]
    if len(done) > 20:
        recent = done[done.updated > done.updated.max() - 6 * 3600]
        span = recent.updated.max() - recent.updated.min()
        rate = (len(recent) - 1) / span if span > 0 else np.nan
        eta = (tot - ndone) / rate if rate > 0 else np.nan
        print(f"\nrate (last 6 h): {rate * 3600:.1f} station-days/h, "
              f"{recent.bytes.sum() / 1e6 / max(span, 1):.2f} MB/s; "
              f"{ndone}/{tot} finished; ETA {pd.Timestamp.now() + pd.Timedelta(seconds=eta)}")


class Buffer:
    def __init__(self, cfg):
        self.dir = path(cfg, "data") / "buffer"
        self.dir.mkdir(parents=True, exist_ok=True)

    def file(self, sta, day):
        return self.dir / f"XL.{sta}.{day}.mseed"


def claim(con, worker, n=1):
    """Atomically claim the next n 'todo' station-days (Hangay first, day-major)."""
    # BEGIN IMMEDIATE takes SQLite's write lock, so two threads or processes
    # can never claim the same row.
    con.execute("BEGIN IMMEDIATE")
    rows = con.execute("SELECT station, day FROM station_day WHERE status='todo' "
                       "ORDER BY prio, day, station LIMIT ?", (n,)).fetchall()
    for sta, day in rows:
        con.execute("UPDATE station_day SET status='downloading', worker=?, updated=? "
                    "WHERE station=? AND day=?", (worker, time.time(), sta, day))
    con.execute("COMMIT")
    return rows


def set_status(con, sta, day, status, **kw):
    cols = ", ".join(f"{k}=?" for k in kw)
    sql = f"UPDATE station_day SET status=?, updated=?{', ' + cols if cols else ''} WHERE station=? AND day=?"
    con.execute(sql, (status, time.time(), *kw.values(), sta, day))


def reset_stale(con, log):
    """Reset rows held by workers whose process is gone."""
    live = set()
    for w, pid, host in con.execute("SELECT worker, pid, host FROM workers").fetchall():
        if host == socket.gethostname():
            try:
                os.kill(pid, 0)
                live.add(w)
            except OSError:
                pass
    stale = con.execute("SELECT COUNT(*) FROM station_day WHERE status IN ('downloading','downloaded') "
                        f"AND worker NOT IN ({','.join('?' * len(live)) or 'NULL'})", tuple(live)).fetchone()[0]
    con.execute("UPDATE station_day SET status='todo' WHERE status IN ('downloading','downloaded') "
                f"AND worker NOT IN ({','.join('?' * len(live)) or 'NULL'})", tuple(live))
    if stale:
        log.info("reset %d stale in-flight station-days", stale)


def downloader(cfg, con, worker, buf: Buffer, q: queue.Queue, stop: threading.Event, log):
    from obspy.clients.fdsn import Client
    from obspy.clients.fdsn.header import FDSNNoDataException

    client = Client(cfg["fdsn"]["base_url"], timeout=300)
    net = cfg["fdsn"]["network"]
    while not stop.is_set():
        rows = claim(con, worker, 1)
        if not rows:
            q.put(None)
            return
        sta, day = rows[0]
        t = UTCDateTime(day)
        f = buf.file(sta, day)
        tic = time.time()
        ok = f.exists() and f.stat().st_size > 0
        for attempt in range(4):
            if ok:
                break
            try:
                st = client.get_waveforms(net, sta, "*", "HH?", t - 60, t + 86400 + 60)
                tmp = f.with_suffix(".part")
                st.write(str(tmp), format="MSEED")
                tmp.replace(f)
                ok = True
            except FDSNNoDataException:
                break
            except Exception as e:
                log.warning("%s %s download attempt %d: %s", sta, day, attempt + 1, str(e)[:160])
                time.sleep(30 * (attempt + 1))
        if not ok:
            set_status(con, sta, day, "nodata", dl_s=time.time() - tic)
            continue
        set_status(con, sta, day, "downloaded", bytes=f.stat().st_size, dl_s=time.time() - tic)
        q.put((sta, day))  # blocks when the prefetch buffer is full


def pick_buffered(cfg, models, f: Path, t: UTCDateTime):
    from pick import run_model

    st = read(str(f)).select(channel="HH?")
    for tr in st:
        tr.data = tr.data.astype(np.float32)
    st.merge(method=1, fill_value=None)
    st = st.split()
    st.detrend("demean")
    frames = {}
    for name, weights, m in models:
        df = run_model(m, st, cfg, t, t + 86400)
        df["model"], df["weights"] = name, weights
        frames[(name, weights)] = df
    return frames


def decimated_path(cfg, sta, t) -> Path:
    root = Path(cfg["paths"].get("decimated", "data/mseed20"))
    if not root.is_absolute():
        root = path(cfg, "data").parent / root
    t = UTCDateTime(t)
    return root / f"XL.{sta}" / f"{t.year}" / f"{t.julday:03d}.mseed"


def write_decimated(cfg, f: Path, sta, t, factor=5):
    """20 Hz copy for template matching (pass 3): 8 Hz zero-phase low-pass
    (anti-alias, below the 10 Hz Nyquist), decimate 100 -> 20 Hz, round to int32
    counts and store Steim2-compressed (~1/5 of the raw size)."""
    st = read(str(f)).select(channel="HH?")
    st.trim(UTCDateTime(t), UTCDateTime(t) + 86400, nearest_sample=False)
    st.merge(method=1, fill_value=None)
    st = st.split()
    out = st.copy()
    out.traces = []
    for tr in st:
        if tr.stats.sampling_rate != 100.0 or tr.stats.npts < 500:
            continue
        tr.data = tr.data.astype(np.float64)
        tr.detrend("demean")
        tr.filter("lowpass", freq=8.0, corners=8, zerophase=True)
        tr.decimate(factor, no_filter=True)
        tr.data = np.round(tr.data).astype(np.int32)
        out += tr
    g = decimated_path(cfg, sta, t)
    g.parent.mkdir(parents=True, exist_ok=True)
    tmp = g.with_suffix(".tmp")
    out.write(str(tmp), format="MSEED", encoding="STEIM2")
    tmp.replace(g)
    return g.stat().st_size


def cmd_run(cfg, args, log):
    import torch

    from ensemble import ens_path, ensemble_from_cfg
    from pick import load_models, raw_pick_path

    device = args.device or cfg["picking"]["device"]
    torch.set_num_threads(args.threads or cfg["picking"]["torch_threads"])
    con = ledger(cfg)
    worker = args.worker or f"w{os.getpid()}"
    con.execute("INSERT OR REPLACE INTO workers VALUES (?,?,?,?,?)",
                (worker, os.getpid(), socket.gethostname(), time.time(), time.time()))
    reset_stale(con, log)
    models = load_models(cfg, device, log)
    buf = Buffer(cfg)
    q: queue.Queue = queue.Queue(maxsize=args.prefetch)
    stop = threading.Event()
    threads = [threading.Thread(target=downloader, args=(cfg, ledger(cfg), worker, buf, q, stop, log),
                                daemon=True) for _ in range(args.download_threads)]
    for th in threads:
        th.start()
    finished_threads, n = 0, 0
    net = cfg["fdsn"]["network"]
    try:
        with torch.no_grad():
            while finished_threads < len(threads):
                item = q.get()
                if item is None:
                    finished_threads += 1
                    continue
                sta, day = item
                t = UTCDateTime(day)
                f = buf.file(sta, day)
                tic = time.time()
                try:
                    frames = pick_buffered(cfg, models, f, t)
                except Exception as e:
                    log.error("%s %s picking failed: %s", sta, day, e)
                    set_status(con, sta, day, "error")
                    continue
                for (name, weights), df in frames.items():
                    out = raw_pick_path(cfg, name, weights, net, sta, t)
                    out.parent.mkdir(parents=True, exist_ok=True)
                    df.to_parquet(out, index=False)
                ens = ensemble_from_cfg(pd.concat(frames.values(), ignore_index=True), cfg)
                eo = ens_path(cfg, net, sta, t)
                eo.parent.mkdir(parents=True, exist_ok=True)
                ens.to_parquet(eo, index=False)
                if args.decimate:
                    write_decimated(cfg, f, sta, t)
                if not args.keep_waveforms:
                    f.unlink(missing_ok=True)
                set_status(con, sta, day, "done", pick_s=time.time() - tic, n_ens=len(ens))
                con.execute("UPDATE workers SET beat=? WHERE worker=?", (time.time(), worker))
                n += 1
                if n % 20 == 0:
                    log.info("%s: %d station-days done (last %s %s, %d picks, %.1f s)",
                             worker, n, sta, day, len(ens), time.time() - tic)
                if args.max_station_days and n >= args.max_station_days:
                    break
    finally:
        stop.set()
        log.info("%s stopping after %d station-days", worker, n)


def main(argv=None):
    ap = base_parser(__doc__)
    ap.add_argument("cmd", choices=["init", "run", "status", "mark-existing"])
    ap.add_argument("--worker", default=None)
    ap.add_argument("--threads", type=int, default=None, help="torch CPU threads")
    ap.add_argument("--download-threads", type=int, default=3)
    ap.add_argument("--prefetch", type=int, default=6, help="max station-days waiting in data/buffer")
    ap.add_argument("--keep-waveforms", action="store_true")
    ap.add_argument("--decimate", action="store_true", help="also keep a 20 Hz copy (paths.decimated)")
    ap.add_argument("--max-station-days", type=int, default=0)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    log = get_logger("stream", path(cfg, "logs") / "stream.log")
    {"init": cmd_init, "run": cmd_run, "status": cmd_status,
     "mark-existing": cmd_mark_done_from_existing}[args.cmd](cfg, args, log)


if __name__ == "__main__":
    main()
