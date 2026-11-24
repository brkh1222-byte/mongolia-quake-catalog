"""T2.3: compare our picks with the public QuakeScope PhaseNet picks for XL
(Ni et al. 2025). Script version of notebooks/02_compare_quakescope.ipynb.

QuakeScope picks are read from
  https://dasway.ess.washington.edu/quakescope/data/picks/network=XL/year=YYYY/month=MM/docdb2025-XL.parquet
(columns tid, cha, pha, start, peak, end, conf, amp, amp_vel). They are
downloaded once into data/reference/quakescope/.

Matching: for each station and phase, a pick in set A matches the nearest pick
in set B if |dt| <= tol (P 0.3 s, S 0.5 s). Each B pick is used at most once
(greedy, in time order). Reported per comparison: counts, recall of B by A,
precision of A against B, and the median and MAD of dt.

Comparisons
  1. QuakeScope vs our ensemble picks (all, and only the picks associated to events)
  2. QuakeScope vs our raw PhaseNet picks for each weight set (like-for-like:
     same architecture, so differences come from the weights, thresholds and
     preprocessing)
  3. QuakeScope pick-count check against the published May 2013 figure
     (209,901 picks on 72 Hangay stations; Ni et al. 2025), if that month is present

Output: results/quakescope_{tag}.md and results/quakescope_{tag}.csv

Example
  python src/compare_quakescope.py --start 2013-01-01 --end 2013-02-01 --stations HD --tag pilot_2013-01
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
from obspy import UTCDateTime

from common import base_parser, days, get_logger, load_config, path, select_stations, to_epoch

QS_URL = ("https://dasway.ess.washington.edu/quakescope/data/picks/network={net}/year={y}/"
          "month={m:02d}/docdb2025-{net}.parquet")
TOL = {"P": 0.3, "S": 0.5}


def load_quakescope(cfg, net, start, end, log=None) -> pd.DataFrame:
    import urllib.request

    out = []
    t = UTCDateTime(start)
    months = sorted({(d.year, d.month) for d in days(start, end)})
    for y, m in months:
        f = path(cfg, "reference") / "quakescope" / f"{net}_{y}_{m:02d}.parquet"
        if not f.exists():
            f.parent.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(QS_URL.format(net=net, y=y, m=m), f)
        out.append(pd.read_parquet(f))
    qs = pd.concat(out, ignore_index=True)
    qs["station"] = qs.tid.str.split(".").str[1]
    qs["t"] = to_epoch(qs.peak.astype(str))
    qs = qs.rename(columns={"pha": "phase", "conf": "prob"})
    qs = qs[(qs.t >= UTCDateTime(start).timestamp) & (qs.t < UTCDateTime(end).timestamp)]
    return qs[["station", "phase", "t", "prob", "amp"]].reset_index(drop=True)


def match(a: pd.DataFrame, b: pd.DataFrame, tol=TOL):
    """Greedy one-to-one matching per station/phase. Returns dt array (a - b) and
    boolean arrays for matched a and matched b."""
    ma = np.zeros(len(a), bool)
    mb = np.zeros(len(b), bool)
    dts = np.full(len(a), np.nan)
    a = a.reset_index(drop=True)
    b = b.reset_index(drop=True)
    for (sta, ph), ga in a.groupby(["station", "phase"]):
        gb = b[(b.station == sta) & (b.phase == ph)]
        if gb.empty:
            continue
        tb = gb.t.to_numpy()
        order = np.argsort(tb)
        tb, ib = tb[order], gb.index.to_numpy()[order]
        used = np.zeros(len(tb), bool)
        for ia, ta in zip(ga.index, ga.t.to_numpy()):
            k = np.searchsorted(tb, ta)
            best, bd = -1, tol[ph]
            for kk in (k - 1, k, k + 1):
                if 0 <= kk < len(tb) and not used[kk] and abs(tb[kk] - ta) <= bd:
                    best, bd = kk, abs(tb[kk] - ta)
            if best >= 0:
                used[best] = True
                ma[ia] = True
                mb[ib[best]] = True
                dts[ia] = ta - tb[best]
    return dts, ma, mb


def summarise(name, a, b, dts, ma, mb):
    rows = []
    for ph in ("P", "S"):
        sa, sb = (a.phase == ph).to_numpy(), (b.phase == ph).to_numpy()
        d = dts[sa & ma]
        rows.append(dict(comparison=name, phase=ph, n_ours=int(sa.sum()), n_qs=int(sb.sum()),
                         n_matched=int((sa & ma).sum()),
                         recall_of_qs=float(mb[sb].mean()) if sb.any() else np.nan,
                         frac_ours_in_qs=float(ma[sa].mean()) if sa.any() else np.nan,
                         dt_median_s=float(np.median(d)) if len(d) else np.nan,
                         dt_mad_s=float(np.median(np.abs(d - np.median(d))) * 1.4826) if len(d) else np.nan))
    return rows


def main(argv=None):
    ap = base_parser(__doc__)
    from ensemble import add_ensemble_args

    add_ensemble_args(ap)
    ap.add_argument("--tag", required=True)
    args = ap.parse_args(argv)
    from ensemble import apply_ensemble_args

    cfg = apply_ensemble_args(load_config(args.config), args)
    log = get_logger("quakescope")
    net = cfg["fdsn"]["network"]
    stations = select_stations(cfg, args.stations or cfg["pilot"]["subarray"], args.start, args.end)
    qs = load_quakescope(cfg, net, args.start, args.end, log)
    qs = qs[qs.station.isin(stations.station)].reset_index(drop=True)

    from associate import load_ensemble
    from pick import raw_pick_path

    ens = load_ensemble(cfg, stations, args.start, args.end)
    ens["t"] = to_epoch(ens.time)
    # restrict QS to station-days we actually picked (fair comparison)
    picked_days = set()
    for t in days(args.start, args.end):
        for sta in stations.station:
            if raw_pick_path(cfg, "PhaseNet", "original", net, sta, t).exists():
                picked_days.add((sta, str(t.date)))
    qday = [(s, str(UTCDateTime(x).date)) in picked_days for s, x in zip(qs.station, qs.t)]
    qs_cov = qs[np.array(qday, bool)].reset_index(drop=True)
    rows = []
    dts, ma, mb = match(ens, qs_cov)
    rows += summarise("ensemble vs QuakeScope", ens, qs_cov, dts, ma, mb)

    catdir = path(cfg, "catalogs") / args.tag
    if (catdir / "picks.parquet").exists():
        assoc = pd.read_parquet(catdir / "picks.parquet")
        assoc = assoc.rename(columns={"time": "t"})[["station", "phase", "t"]]
        dts2, ma2, mb2 = match(assoc, qs_cov)
        rows += summarise("associated picks vs QuakeScope", assoc, qs_cov, dts2, ma2, mb2)
        # how many QS picks fall inside our events' pick windows at all
    for w in ("original", "stead", "instance"):
        frames = []
        for sta, day in picked_days:
            f = raw_pick_path(cfg, "PhaseNet", w, net, sta, UTCDateTime(day))
            if f.exists():
                frames.append(pd.read_parquet(f))
        frames = [f for f in frames if not f.empty]
        if not frames:
            continue
        raw = pd.concat(frames, ignore_index=True)
        raw["t"] = to_epoch(raw.time)
        for thr in ((0.2, 0.3) if w == "instance" else (0.3,)):
            rr = raw[raw.prob >= thr].reset_index(drop=True)
            d3, a3, b3 = match(rr, qs_cov)
            rows += summarise(f"PhaseNet/{w} (p>={thr}) vs QuakeScope", rr, qs_cov, d3, a3, b3)
    res = pd.DataFrame(rows)
    out = path(cfg, "results")
    res.to_csv(out / f"quakescope_{args.tag}.csv", index=False)

    n_sd = len(picked_days)
    lines = [f"# QuakeScope comparison: {args.tag}", "",
             f"Station-days compared: {n_sd} (stations {stations.station.nunique()}, "
             f"{args.start} to {args.end}). QuakeScope picks on these station-days: {len(qs_cov)} "
             f"(P {int((qs_cov.phase == 'P').sum())}, S {int((qs_cov.phase == 'S').sum())}); "
             f"QuakeScope minimum confidence in file: {qs.prob.min():.2f}.", "",
             f"Our ensemble picks: {len(ens)}. Matching tolerance: P {TOL['P']} s, S {TOL['S']} s.", "",
             res.to_markdown(index=False, floatfmt=".3f"), "",
             "Generated by `src/compare_quakescope.py`."]
    (out / f"quakescope_{args.tag}.md").write_text("\n".join(lines))
    log.info("\n%s", res.to_string(index=False))


if __name__ == "__main__":
    main()
