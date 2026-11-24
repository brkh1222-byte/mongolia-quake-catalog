"""T2.1: deep-learning phase picking with SeisBench, batched per station-day.

For every station-day and every (model, weights) pair in config `picking.models`
we run the pretrained picker over the continuous day file (padded with 60 s
from the neighbouring days so that arrivals at midnight are not lost) and keep
all picks above a low raw threshold (`picking.raw_threshold`). The ensemble
step (src/ensemble.py) decides which picks survive.

Output: one parquet per model/weights and station-day
  data/picks/raw/{model}_{weights}/{net}.{sta}/{year}/{jday:03d}.parquet
with columns  station, phase, time (UTC ISO), prob, model, weights, network.
An empty parquet is written when a day has no picks, so reruns skip it
(resumable). Runtime per station-day is logged to data/logs/pick_timing.csv.

How it works (for the paper): PhaseNet (Zhu & Beroza 2019) is a U-Net that
maps a 30 s, 3-component window to per-sample P, S and noise probabilities.
EQTransformer (Mousavi et al. 2020) is an attention network over 60 s windows
that outputs detection, P and S probabilities. SeisBench (Woollam et al.
2022) slides the window over the day with overlap, stacks the overlapping
predictions, and reports the time and height of each probability peak above
the threshold. Each weight set ("stead", "instance", "original") is the same
architecture trained on a different labelled data set (STEAD: global; INSTANCE:
Italy; "original": the authors' release weights), so their errors are partly
independent, which is the point of the ensemble.

Examples
  python src/pick.py --start 2013-01-01 --end 2013-01-02 --stations HD01 --device cpu
  python src/pick.py --start 2012-06-01 --end 2014-05-01 --stations HD --device cuda   # H100
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
from obspy import Stream, UTCDateTime, read

from common import base_parser, day_path, days, get_logger, load_config, path, select_stations

PAD_S = 60.0


def raw_pick_path(cfg, model, weights, net, sta, t) -> Path:
    t = UTCDateTime(t)
    return (path(cfg, "picks") / "raw" / f"{model}_{weights}" / f"{net}.{sta}" /
            f"{t.year}" / f"{t.julday:03d}.parquet")


def load_day(cfg, net, sta, t) -> Stream | None:
    """Day stream with PAD_S seconds of the previous and next day attached."""
    t = UTCDateTime(t)
    f = day_path(cfg, net, sta, t)
    if not f.exists():
        return None
    st = read(str(f))
    for tt, sl in ((t - 86400, (t - PAD_S, t)), (t + 86400, (t + 86400, t + 86400 + PAD_S))):
        g = day_path(cfg, net, sta, tt)
        if g.exists():
            st += read(str(g), starttime=sl[0], endtime=sl[1])
    st = st.select(channel="HH?")
    if not st:
        return None
    for tr in st:
        tr.data = tr.data.astype(np.float32)
    st.merge(method=1, fill_value=None)
    st = st.split()
    st.detrend("demean")
    return st


def load_models(cfg, device, log):
    import seisbench.models as sbm
    import torch

    models = []
    for spec in cfg["picking"]["models"]:
        cls = getattr(sbm, spec["model"])
        m = cls.from_pretrained(spec["weights"])
        m.to(device)
        m.eval()
        models.append((spec["model"], spec["weights"], m))
        log.info("loaded %s/%s on %s", spec["model"], spec["weights"], device)
    return models


def run_model(model, st, cfg, t0, t1) -> pd.DataFrame:
    import torch

    thr = cfg["picking"]["raw_threshold"]
    dev = next(model.parameters()).device.type
    # Optional fp16 autocast (config picking.amp). On the Mac fp16 reproduced all
    # fp32 picks within 10 ms for all six pairs (scripts/bench_amp.py); enable on the
    # cloud GPU only after the same check there.
    with torch.autocast(device_type=dev, dtype=torch.float16, enabled=bool(cfg["picking"].get("amp", False))):
        out = model.classify(st, P_threshold=thr["P"], S_threshold=thr["S"],
                             batch_size=cfg["picking"]["batch_size"])
    rows = []
    for p in out.picks:
        if p.peak_time is None or not (t0 <= p.peak_time < t1):
            continue
        net, sta = p.trace_id.split(".")[:2]
        rows.append(dict(network=net, station=sta, phase=p.phase,
                         time=str(p.peak_time), prob=float(p.peak_value)))
    return pd.DataFrame(rows, columns=["network", "station", "phase", "time", "prob"])


def pick_station_day(cfg, models, net, sta, t, log, force=False):
    t = UTCDateTime(t)
    todo = [(n, w, m) for n, w, m in models
            if force or not raw_pick_path(cfg, n, w, net, sta, t).exists()]
    if not todo:
        return None
    st = load_day(cfg, net, sta, t)
    if st is None:
        return None
    timing = {}
    for name, weights, m in todo:
        tic = time.time()
        df = run_model(m, st, cfg, t, t + 86400)
        df["model"], df["weights"] = name, weights
        f = raw_pick_path(cfg, name, weights, net, sta, t)
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        df.to_parquet(tmp, index=False)
        tmp.replace(f)
        timing[f"{name}_{weights}"] = round(time.time() - tic, 2)
        timing[f"n_{name}_{weights}"] = len(df)
    return timing


def main(argv=None):
    ap = base_parser(__doc__)
    ap.add_argument("--force", action="store_true", help="re-pick even if output exists")
    ap.add_argument("--threads", type=int, default=None, help="torch CPU threads")
    ap.add_argument("--require-next-day", action="store_true",
                    help="skip a station-day until the next day's file exists (download still running), "
                         "so the 60 s midnight padding is always available")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    log = get_logger("pick", path(cfg, "logs") / "pick.log")
    import torch

    device = args.device or cfg["picking"]["device"]
    torch.set_num_threads(args.threads or cfg["picking"]["torch_threads"])
    start, end = args.start, args.end
    stations = select_stations(cfg, args.stations or cfg["pilot"]["subarray"], start, end)
    models = load_models(cfg, device, log)
    net = cfg["fdsn"]["network"]
    tlog = path(cfg, "logs") / "pick_timing.csv"
    with torch.no_grad():
        for t in days(start, end):            # day-major order: whole network per day
            for sta in stations.station:
                if (args.require_next_day and t + 86400 < UTCDateTime(end)
                        and not day_path(cfg, net, sta, t + 86400).exists()):
                    continue
                tic = time.time()
                timing = pick_station_day(cfg, models, net, sta, t, log, force=args.force)
                if timing is None:
                    continue
                timing.update(station=sta, day=str(t.date), total_s=round(time.time() - tic, 2),
                              device=device)
                pd.DataFrame([timing]).to_csv(tlog, mode="a", header=not tlog.exists(), index=False)
                log.info("%s %s done in %.1f s", sta, t.date, timing["total_s"])


if __name__ == "__main__":
    main()
