"""Cut and store short 3-component event waveforms ("snippets").

The full laptop run never keeps continuous data (see docs/laptop_runbook.md).
After association and location, each event gets one miniSEED file holding, for
every station that has a pick for it (plus any station within `radius_km`), the
window
    [predicted P - 10 s,  predicted S + 20 s]   (at least 60 s long).
These snippets feed magnitudes (src/magnitude.py), cross-correlation
(src/xcorr.py) and visual checks.

Source of the waveforms, in order:
  1. local day files under data/mseed (pilot months, or the streaming buffer);
  2. otherwise one FDSN bulk dataselect request per event (EarthScope).

Output: data/snippets/{year}/{event_id}.mseed  (raw counts, as recorded)

Example
  python src/snippets.py --tag pilot_2013-01 --stations HD
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
from obspy import Stream, UTCDateTime, read

from common import base_parser, day_path, get_logger, load_config, path, select_stations
from locate import TwoLayer, local_proj


def snippet_path(cfg, event_id: str, origin_time) -> Path:
    t = UTCDateTime(origin_time)
    root = Path(cfg["paths"].get("snippets", "data/snippets"))
    if not root.is_absolute():
        root = path(cfg, "data").parent / root
    return root / f"{t.year}" / f"{event_id}.mseed"


def windows_for_event(ev, stations, model, picked: set, radius_km: float):
    proj = local_proj(ev.latitude, ev.longitude)
    out = []
    for s in stations.itertuples():
        x, y = proj(s.lon, s.lat)
        d = float(np.hypot(x, y))
        if s.station not in picked and d > radius_km:
            continue
        tp = model.tt("P", d, ev.depth_km, s.elev / 1000)
        ts = model.tt("S", d, ev.depth_km, s.elev / 1000)
        t0 = UTCDateTime(ev.time) + tp - 10.0
        t1 = max(UTCDateTime(ev.time) + ts + 20.0, t0 + 60.0)
        out.append((s.network, s.station, t0, t1))
    return out


def cut_local(cfg, net, sta, t0, t1) -> Stream:
    st = Stream()
    for t in sorted({UTCDateTime(t0.date), UTCDateTime(t1.date)}):
        f = day_path(cfg, net, sta, t)
        if f.exists():
            st += read(str(f), starttime=t0, endtime=t1)
    st.merge(method=1, fill_value=None)
    return st.split()


def fetch_event(cfg, wins, client=None, log=None) -> Stream:
    st, missing = Stream(), []
    for net, sta, t0, t1 in wins:
        s = cut_local(cfg, net, sta, t0, t1)
        if len(s):
            st += s
        else:
            missing.append((net, sta, "*", "HH?", t0, t1))
    if missing:
        try:
            if client is None:
                from obspy.clients.fdsn import Client
                client = Client(cfg["fdsn"]["base_url"], timeout=120)
            st += client.get_waveforms_bulk(missing)
        except Exception as e:  # FDSNNoDataException or network error
            if log and "No data" not in str(e):
                log.warning("bulk request failed: %s", str(e)[:200])
    return st


def main(argv=None):
    ap = base_parser(__doc__)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--radius-km", type=float, default=150.0)
    ap.add_argument("--min-quality", default="C", help="skip events worse than this class")
    ap.add_argument("--threads", type=int, default=4, help="parallel event fetches (FDSN)")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    log = get_logger("snippets", path(cfg, "logs") / "snippets.log")
    d = path(cfg, "catalogs") / args.tag
    cat = pd.read_csv(d / "events.csv")
    picks = pd.read_parquet(d / "picks.parquet")
    cat = cat[cat.quality <= args.min_quality]
    stations = select_stations(cfg, args.stations or cfg["pilot"]["subarray"], cat.origin_time.min(),
                               cat.origin_time.max())
    model = TwoLayer(cfg)
    from concurrent.futures import ThreadPoolExecutor

    from obspy.clients.fdsn import Client

    clients = [Client(cfg["fdsn"]["base_url"], timeout=120) for _ in range(args.threads)]
    picked_by_event = picks.groupby("event_id").station.apply(set).to_dict()

    def job(k, ev):
        f = snippet_path(cfg, ev.event_id, ev.origin_time)
        if f.exists():
            return 0
        wins = windows_for_event(ev, stations, model, picked_by_event.get(ev.event_id, set()), args.radius_km)
        st = fetch_event(cfg, wins, clients[k % args.threads], log)
        if not len(st):
            return 0
        for tr in st:
            if tr.data.dtype.kind == "f":
                tr.data = tr.data.astype(np.float32)
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(f".{k}.tmp")
        st.write(str(tmp), format="MSEED")
        tmp.replace(f)
        return 1

    with ThreadPoolExecutor(max_workers=args.threads) as ex:
        n_new = sum(ex.map(lambda a: job(*a), enumerate(cat.itertuples())))
    log.info("%d new snippet files for %d events", n_new, len(cat))


if __name__ == "__main__":
    main()
