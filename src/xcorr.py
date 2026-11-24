"""T4.1: waveform cross-correlation differential times for relocation.

For every pair of events whose first-pass hypocentres are within
`--max-sep-km` (default 10 km), and every station where both have a pick of
the same phase:
  * P: vertical component, window [pick - 0.5 s, pick + 1.0 s];
  * S: both horizontals, window [pick - 0.5 s, pick + 2.0 s]; the CC functions of
    N and E are averaged before the lag is chosen;
  * band-pass 2–15 Hz (zero-phase); lag search ±`--max-lag` s (default 0.6 s);
  * normalised CC with parabolic sub-sample refinement.
The differential travel time is then
    dt = (t_i - ot_i) - (t_j' - ot_j),  with  t_j' = t_j + lag
i.e. GrowClust's `tdif_fmt = 12` convention (tt1 - tt2).

The correlation runs as one batched grouped convolution in PyTorch
(conv1d with groups = batch), so the same code runs on CPU, Apple MPS or CUDA.

Input : data/catalogs/{tag}/events.csv, picks.parquet and data/snippets/
Output: data/catalogs/{tag}/xcorr.parquet and xcordata.txt (GrowClust text format:
        "# evid1 evid2 0.0" then "sta dt cc phase" lines)

Example
  python src/xcorr.py --tag pilot_2013-01 --device cpu
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
from obspy import UTCDateTime, read
from scipy.spatial import cKDTree

from common import base_parser, get_logger, load_config, path

WIN = {"P": (0.5, 1.0), "S": (0.5, 2.0)}
COMP = {"P": ("Z",), "S": ("N", "E", "1", "2")}


def event_pairs(cat: pd.DataFrame, max_sep_km: float, max_neighbours: int = 40):
    from locate import local_proj

    proj = local_proj(cat.latitude.mean(), cat.longitude.mean())
    x, y = proj(cat.longitude.to_numpy(), cat.latitude.to_numpy())
    xyz = np.c_[x, y, cat.depth_km.to_numpy()]
    tree = cKDTree(xyz)
    pairs = set()
    for i, nb in enumerate(tree.query_ball_point(xyz, r=max_sep_km)):
        nb = [j for j in nb if j != i]
        if len(nb) > max_neighbours:  # keep the nearest neighbours only
            d = np.linalg.norm(xyz[nb] - xyz[i], axis=1)
            nb = list(np.asarray(nb)[np.argsort(d)[:max_neighbours]])
        for j in nb:
            pairs.add((min(i, j), max(i, j)))
    return sorted(pairs)


def load_event_waveforms(cfg, ev, fs=100.0):
    from snippets import snippet_path

    f = snippet_path(cfg, ev.event_id, ev.origin_time)
    if not f.exists():
        return {}
    st = read(str(f))
    st.merge(method=1, fill_value=0)
    out = {}
    for tr in st:
        if tr.stats.sampling_rate != fs:
            continue
        tr.detrend("demean")
        tr.taper(0.02)
        tr.filter("bandpass", freqmin=2.0, freqmax=15.0, corners=4, zerophase=True)
        out[(tr.stats.station, tr.stats.channel[-1])] = (tr.stats.starttime.timestamp,
                                                         tr.data.astype(np.float32))
    return out


def _segment(wf, t_center, before, after, fs):
    t0, data = wf
    i0 = int(round((t_center - before - t0) * fs))
    n = int(round((before + after) * fs)) + 1
    if i0 < 0 or i0 + n > len(data):
        return None
    return data[i0:i0 + n]


def batched_cc(templates: np.ndarray, segments: np.ndarray, device="cpu"):
    """templates (B, L), segments (B, L + 2K). Returns normalised CC (B, 2K+1)."""
    import torch

    T = torch.as_tensor(templates, device=device)
    S = torch.as_tensor(segments, device=device)
    B, L = T.shape
    T = T - T.mean(dim=1, keepdim=True)
    num = torch.nn.functional.conv1d(S.unsqueeze(0), T.unsqueeze(1), groups=B)[0]
    ones = torch.ones((1, 1, L), device=device)
    s1 = torch.nn.functional.conv1d(S.unsqueeze(1), ones)[:, 0]
    s2 = torch.nn.functional.conv1d((S * S).unsqueeze(1), ones)[:, 0]
    var_s = torch.clamp(s2 - s1 * s1 / L, min=1e-20)
    norm_t = torch.sqrt(torch.clamp((T * T).sum(dim=1, keepdim=True), min=1e-20))
    return (num / (norm_t * torch.sqrt(var_s))).cpu().numpy()


def subsample_peak(cc_row):
    k = int(np.argmax(cc_row))
    if 0 < k < len(cc_row) - 1:
        y0, y1, y2 = cc_row[k - 1], cc_row[k], cc_row[k + 1]
        den = y0 - 2 * y1 + y2
        off = 0.5 * (y0 - y2) / den if den != 0 else 0.0
        return k + off, float(y1 - 0.25 * (y0 - y2) * off)
    return float(k), float(cc_row[k])


def compute_xcorr(cfg, cat, picks, max_sep_km=10.0, max_lag=0.6, device="cpu", fs=100.0,
                  min_cc=0.6, batch=4096, log=None):
    cat = cat.reset_index(drop=True)
    pairs = event_pairs(cat, max_sep_km)
    if log:
        log.info("%d event pairs within %.0f km", len(pairs), max_sep_km)
    pk = {(r.event_id, r.station, r.phase): float(r.time) for r in picks.itertuples()}
    wf_cache: dict = {}

    def wf(i):
        if i not in wf_cache:
            if len(wf_cache) > 2000:
                wf_cache.pop(next(iter(wf_cache)))
            wf_cache[i] = load_event_waveforms(cfg, cat.iloc[i], fs)
        return wf_cache[i]

    K = int(round(max_lag * fs))
    buf = {"P": ([], [], []), "S": ([], [], [])}  # per phase: jobs, templates, segments (equal lengths)
    rows = []

    def flush(ph):
        jobs, T, S = buf[ph]
        if not jobs:
            return
        ncomp = {}
        cc = batched_cc(np.stack(T), np.stack(S), device)
        # average CC over components of the same (pair, station, phase)
        for (key, _comp), c in zip(jobs, cc):
            ncomp.setdefault(key, []).append(c)
        for key, cs in ncomp.items():
            i, j, sta, ph_ = key
            lag_idx, ccmax = subsample_peak(np.mean(cs, axis=0))
            lag = (lag_idx - K) / fs
            ev_i, ev_j = cat.iloc[i], cat.iloc[j]
            dt = (pk[(ev_i.event_id, sta, ph_)] - ev_i.time) - (pk[(ev_j.event_id, sta, ph_)] + lag - ev_j.time)
            rows.append((ev_i.event_id, ev_j.event_id, sta, ph_, dt, ccmax, lag))
        jobs.clear(); T.clear(); S.clear()

    for i, j in pairs:
        ei, ej = cat.event_id.iloc[i], cat.event_id.iloc[j]
        wi, wj = wf(i), wf(j)
        if not wi or not wj:
            continue
        for ph in ("P", "S"):
            b, a = WIN[ph]
            stas = {s for (e, s, p) in [(ei, s, ph) for s in {k[0] for k in wi}] if (ei, s, ph) in pk}
            for sta in stas:
                if (ej, sta, ph) not in pk:
                    continue
                for comp in COMP[ph]:
                    if (sta, comp) not in wi or (sta, comp) not in wj:
                        continue
                    t = _segment(wi[(sta, comp)], pk[(ei, sta, ph)], b, a, fs)
                    s = _segment(wj[(sta, comp)], pk[(ej, sta, ph)], b + max_lag, a + max_lag, fs)
                    if t is None or s is None or len(s) != len(t) + 2 * K:
                        continue
                    buf[ph][0].append(((i, j, sta, ph), comp)); buf[ph][1].append(t); buf[ph][2].append(s)
        for ph in ("P", "S"):
            if len(buf[ph][0]) >= batch:
                flush(ph)
    flush("P"); flush("S")
    df = pd.DataFrame(rows, columns=["evid1", "evid2", "station", "phase", "dt", "cc", "lag"])
    return df[df.cc >= min_cc].reset_index(drop=True), len(pairs)


def write_growclust_xcor(df: pd.DataFrame, evnum: dict, f: Path):
    with open(f, "w") as fh:
        for (e1, e2), g in df.groupby(["evid1", "evid2"], sort=False):
            fh.write(f"# {evnum[e1]} {evnum[e2]} 0.0\n")
            for r in g.itertuples():
                fh.write(f"{r.station:>6s} {r.dt:9.4f} {r.cc:6.4f} {r.phase}\n")


def main(argv=None):
    ap = base_parser(__doc__)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--max-sep-km", type=float, default=10.0)
    ap.add_argument("--max-lag", type=float, default=0.6)
    ap.add_argument("--min-cc", type=float, default=0.6)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    log = get_logger("xcorr")
    d = path(cfg, "catalogs") / args.tag
    cat = pd.read_csv(d / "events.csv")
    cat = cat[cat.quality.isin(["A", "B", "C"])].reset_index(drop=True)
    picks = pd.read_parquet(d / "picks.parquet")
    device = args.device or cfg["picking"]["device"]
    df, npairs = compute_xcorr(cfg, cat, picks, args.max_sep_km, args.max_lag, device,
                               min_cc=args.min_cc, log=log)
    df.to_parquet(d / "xcorr.parquet", index=False)
    evnum = {e: k + 1 for k, e in enumerate(cat.event_id)}
    write_growclust_xcor(df, evnum, d / "xcordata.txt")
    log.info("%d differential times (cc >= %.2f) from %d pairs", len(df), args.min_cc, npairs)


if __name__ == "__main__":
    main()
