"""T2.2: merge picks from several model/weight pairs into one ensemble pick list.

Rule (config `ensemble`, notes/decisions.md D6):
  * For each station and phase, raw picks from all model/weight pairs are
    sorted in time and grouped: a pick joins the current group if it lies within
    `tolerance_s[phase]` of the group's first pick. A group keeps at most one
    pick per model/weight pair (the most probable one).
  * The ensemble pick time is the probability-weighted mean of the group times;
    `time_std` is their spread (a cheap pick-uncertainty proxy).
  * `prob` is the mean probability over *all* N pairs, with a missing pair
    counting as 0. So one confident model alone cannot pass when N = 6.
  * A group survives if  n_models >= min_models  and  prob >= min_mean_prob.
  * If a P and an S ensemble pick at one station are closer than 0.5 s, only
    the more probable one is kept (a single arrival cannot be both).

Input: the raw parquet files written by src/pick.py (or in-memory DataFrames).
Output: data/picks/ensemble/{net}.{sta}/{year}/{jday:03d}.parquet
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
from obspy import UTCDateTime

from common import to_epoch, base_parser, days, get_logger, load_config, path, select_stations

COLS = ["network", "station", "phase", "time", "prob", "n_models", "time_std", "models"]


def ensemble_picks(raw: pd.DataFrame, n_pairs: int, tolerance: dict, min_models: int,
                   min_mean_prob: float) -> pd.DataFrame:
    """Merge raw picks (columns network, station, phase, time, prob, model, weights)."""
    if raw.empty:
        return pd.DataFrame(columns=COLS)
    raw = raw.copy()
    raw["t"] = to_epoch(raw["time"])
    raw["pair"] = raw["model"].astype(str) + "_" + raw["weights"].astype(str)
    out = []
    for (net, sta, ph), g in raw.groupby(["network", "station", "phase"], sort=False):
        tol = tolerance[ph]
        g = g.sort_values("t")
        t, p, pair = g["t"].to_numpy(), g["prob"].to_numpy(), g["pair"].to_numpy()
        i = 0
        while i < len(t):
            j = i
            while j + 1 < len(t) and t[j + 1] - t[i] <= tol:
                j += 1
            best = {}
            for k in range(i, j + 1):
                if pair[k] not in best or p[k] > p[best[pair[k]]]:
                    best[pair[k]] = k
            idx = np.fromiter(best.values(), dtype=int)
            w = p[idx]
            tm = float(np.sum(w * t[idx]) / np.sum(w))
            out.append((net, sta, ph, tm, float(w.sum() / n_pairs), len(idx),
                        float(np.std(t[idx])), ",".join(sorted(best))))
            i = j + 1
    df = pd.DataFrame(out, columns=["network", "station", "phase", "t", "prob", "n_models",
                                    "time_std", "models"])
    df = df[(df.n_models >= min_models) & (df.prob >= min_mean_prob)]
    df = _resolve_ps_conflicts(df)
    df["time"] = [str(UTCDateTime(x)) for x in df.t]
    return df.drop(columns="t").sort_values(["station", "time"])[COLS].reset_index(drop=True)


def _resolve_ps_conflicts(df: pd.DataFrame, gap: float = 0.5) -> pd.DataFrame:
    keep = np.ones(len(df), bool)
    df = df.sort_values(["station", "t"]).reset_index(drop=True)
    t, ph, pr, st = df.t.to_numpy(), df.phase.to_numpy(), df.prob.to_numpy(), df.station.to_numpy()
    for i in range(len(df) - 1):
        if st[i] == st[i + 1] and ph[i] != ph[i + 1] and t[i + 1] - t[i] < gap:
            keep[i if pr[i] < pr[i + 1] else i + 1] = False
    return df[keep]


def ensemble_from_cfg(raw: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    e = cfg["ensemble"]
    return ensemble_picks(raw, len(cfg["picking"]["models"]), e["tolerance_s"],
                          e["min_models"], e["min_mean_prob"])


def ens_path(cfg, net, sta, t) -> Path:
    t = UTCDateTime(t)
    return path(cfg, "picks") / "ensemble" / f"{net}.{sta}" / f"{t.year}" / f"{t.julday:03d}.parquet"


def load_raw_day(cfg, net, sta, t) -> pd.DataFrame | None:
    from pick import raw_pick_path

    frames = []
    for spec in cfg["picking"]["models"]:
        f = raw_pick_path(cfg, spec["model"], spec["weights"], net, sta, t)
        if not f.exists():
            return None  # incomplete: not all pairs have run
        frames.append(pd.read_parquet(f))
    frames = [f for f in frames if not f.empty]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["network", "station", "phase", "time", "prob", "model", "weights"])


def main(argv=None):
    ap = base_parser(__doc__)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    log = get_logger("ensemble")
    net = cfg["fdsn"]["network"]
    stations = select_stations(cfg, args.stations or cfg["pilot"]["subarray"], args.start, args.end)
    n = 0
    for t in days(args.start, args.end):
        for sta in stations.station:
            raw = load_raw_day(cfg, net, sta, t)
            if raw is None:
                continue
            ens = ensemble_from_cfg(raw, cfg)
            f = ens_path(cfg, net, sta, t)
            f.parent.mkdir(parents=True, exist_ok=True)
            ens.to_parquet(f, index=False)
            n += len(ens)
    log.info("wrote %d ensemble picks", n)


if __name__ == "__main__":
    main()
