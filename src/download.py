"""T1.1: resumable, parallel download of XL day files from the EarthScope FDSN
dataselect service.

Each station-day is one request (HH?, all locations), written atomically to
    data/mseed/{net}.{sta}/{year}/{jday:03d}.mseed
so a killed run never leaves a half-written file. Reruns skip existing files
(resumable). Station-days the data centre reports as empty are remembered in
data/logs/nodata.csv (pass --retry-nodata to ask again). Per-request timing and
size go to data/logs/download_timing.csv, from which throughput (MB/s) is
measured; seconds of data per channel go to data/logs/availability.csv.

`--streams N` sets the number of parallel requests (threads). EarthScope asks
users to keep concurrency modest. The pilot measured how throughput scales
with N (see results/download_throughput.md).

(The first version used ObsPy's MassDownloader. Plain per-day dataselect
requests turned out simpler and are the same code path as the cloud streaming
run in src/stream_run.py.)

Examples
  python src/download.py --start 2013-05-01 --end 2013-05-04 --stations HD01,HD02
  python src/download.py --start 2013-01-01 --end 2013-02-01 --stations HD --streams 8
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from obspy import UTCDateTime

from common import base_parser, day_path, days, get_logger, load_config, path, select_stations

_lock = threading.Lock()


def fetch_station_day(cfg, client, net, sta, t, pad=0.0):
    """Download one station-day. Returns (status, bytes, seconds, stream|None)."""
    from obspy.clients.fdsn.header import FDSNNoDataException

    tic = time.time()
    for attempt in range(cfg["download"]["retries"] + 1):
        try:
            st = client.get_waveforms(net, sta, cfg["fdsn"]["location"], "HH?", t - pad, t + 86400 + pad)
            return "ok", st, time.time() - tic
        except FDSNNoDataException:
            return "nodata", None, time.time() - tic
        except Exception as e:  # timeouts, 5xx: back off and retry
            err = str(e)[:200]
            time.sleep(min(120, 15 * (attempt + 1)))
    return f"error: {err}", None, time.time() - tic


def write_day(st, f: Path, t):
    st.trim(UTCDateTime(t), UTCDateTime(t) + 86400, nearest_sample=False)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    st.write(str(tmp), format="MSEED")
    tmp.replace(f)
    return f.stat().st_size


def availability_rows(st, net, sta, t, nbytes):
    secs = {}
    for tr in st:
        secs[tr.stats.channel] = secs.get(tr.stats.channel, 0.0) + tr.stats.npts / tr.stats.sampling_rate
    return [dict(network=net, station=sta, day=str(t.date), channel=c, seconds=round(s, 1), bytes=nbytes)
            for c, s in secs.items()]


def _append_csv(f: Path, rows: list[dict]):
    if not rows:
        return
    with _lock:
        f.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(f, mode="a", header=not f.exists(), index=False)


def load_nodata(cfg) -> set:
    f = path(cfg, "logs") / "nodata.csv"
    if not f.exists():
        return set()
    df = pd.read_csv(f)
    return set(zip(df.station, df.day))


def todo_list(cfg, stations, start, end, retry_nodata=False):
    net = cfg["fdsn"]["network"]
    nodata = set() if retry_nodata else load_nodata(cfg)
    todo = []
    for t in days(start, end):  # day-major: the whole network fills in day by day
        for s in stations.itertuples():
            if not (UTCDateTime(s.start.date()) <= t <= UTCDateTime(s.end)):
                continue
            if day_path(cfg, net, s.station, t).exists() or (s.station, str(t.date)) in nodata:
                continue
            todo.append((s.station, t))
    return todo


def run(cfg, todo, streams, log, tag=""):
    from obspy.clients.fdsn import Client

    net = cfg["fdsn"]["network"]
    clients = [Client(cfg["fdsn"]["base_url"], timeout=300) for _ in range(streams)]
    tl = path(cfg, "logs")
    t_start, total = time.time(), 0

    def job(k, sta, t):
        status, st, dt = fetch_station_day(cfg, clients[k % streams], net, sta, t)
        nbytes = 0
        if status == "ok":
            nbytes = write_day(st, day_path(cfg, net, sta, t), t)
            _append_csv(tl / "availability.csv", availability_rows(st, net, sta, t, nbytes))
        elif status == "nodata":
            _append_csv(tl / "nodata.csv", [dict(station=sta, day=str(t.date))])
        _append_csv(tl / "download_timing.csv", [dict(station=sta, day=str(t.date), status=status[:40],
                                                      bytes=nbytes, seconds=round(dt, 2), streams=streams,
                                                      finished=round(time.time(), 1), tag=tag)])
        return sta, t, status, nbytes

    with ThreadPoolExecutor(max_workers=streams) as ex:
        futs = [ex.submit(job, k, sta, t) for k, (sta, t) in enumerate(todo)]
        for n, fu in enumerate(as_completed(futs), 1):
            sta, t, status, nbytes = fu.result()
            total += nbytes
            if status.startswith("error"):
                log.warning("%s %s %s", sta, t.date, status)
            if n % 25 == 0 or n == len(futs):
                el = time.time() - t_start
                log.info("%d/%d station-days, %.2f GB, %.2f MB/s (%d streams)", n, len(futs),
                         total / 1e9, total / 1e6 / el, streams)
    el = time.time() - t_start
    return dict(n=len(todo), bytes=total, seconds=el, mbps=total / 1e6 / max(el, 1e-9), streams=streams)


def main(argv=None):
    ap = base_parser(__doc__)
    ap.add_argument("--streams", type=int, default=None, help="parallel requests")
    ap.add_argument("--limit", type=int, default=0, help="only the first N station-days (benchmarks)")
    ap.add_argument("--tag", default="", help="label written to download_timing.csv")
    ap.add_argument("--retry-nodata", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    log = get_logger("download", path(cfg, "logs") / "download.log")
    start = args.start or cfg["time"]["start"]
    end = args.end or cfg["time"]["end"]
    stations = select_stations(cfg, args.stations or "all", start, end)
    todo = todo_list(cfg, stations, start, end, args.retry_nodata)
    if args.limit:
        todo = todo[:args.limit]
    log.info("%d stations, %d station-days to fetch (%s – %s)", len(stations), len(todo), start, end)
    if args.dry_run or not todo:
        return
    res = run(cfg, todo, args.streams or cfg["download"]["parallel_requests"], log, args.tag)
    log.info("finished: %s", res)


if __name__ == "__main__":
    main()
