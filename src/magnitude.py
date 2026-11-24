"""T4.3: local magnitude ML from simulated Wood–Anderson amplitudes.

For each event and station with a snippet:
  1. remove the instrument response to ground displacement (m), with a
     pre-filter of 0.5–1–40–45 Hz to keep the deconvolution stable;
  2. convolve with a Wood–Anderson seismometer. Natural period 0.8 s, damping
     0.7 and static magnification 2080 (Uhrhammer & Collins 1990). The poles
     are -h*w0 ± i*w0*sqrt(1 - h^2), with w0 = 2*pi/0.8;
  3. take the peak absolute amplitude A (mm) on each horizontal component, in
     a window from 1 s before the P pick (or predicted P) to 10 s after the
     predicted S;
  4. station-component magnitude  ML_i = log10(A_i) - log10 A0(R)  with the
     distance correction of Hutton & Boore (1987) for hypocentral distance R km:
        -log10 A0(R) = 1.110 log10(R/100) + 0.00189 (R - 100) + 3.0
     (the coefficients in config `magnitude.attenuation` can be replaced by a
     Mongolian scale);
  5. event ML = median over station-components, after optional station
     corrections; the uncertainty is the median absolute deviation (MAD)
     scaled by 1.4826 / sqrt(n).

Calibration (`calibrate`): a constant offset between our ML and reference
magnitudes (ISC/EMSC/USGS) of matched events, estimated with a median and a
bootstrap confidence interval. With few reference events (the pilot month has
fewer than 10) the offset is reported but not applied unless --apply-offset.

Example
  python src/magnitude.py --tag pilot_2013-01
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
from obspy import UTCDateTime, read, read_inventory

from common import base_parser, get_logger, load_config, path

DEFAULT_ATTEN = dict(a=1.110, b=0.00189, c=3.0, r_ref=100.0)  # Hutton & Boore (1987)


def wa_paz(T0=0.8, h=0.7, V=2080.0):
    w0 = 2 * np.pi / T0
    p = complex(-h * w0, w0 * np.sqrt(1 - h ** 2))
    return {"poles": [p, p.conjugate()], "zeros": [0j, 0j], "gain": 1.0, "sensitivity": V}


def minus_log_a0(r_km, coef=None):
    c = coef or DEFAULT_ATTEN
    r = np.asarray(r_km, float)
    return c["a"] * np.log10(r / c["r_ref"]) + c["b"] * (r - c["r_ref"]) + c["c"]


def wa_amplitudes(st, inv, windows: dict, log=None) -> list[dict]:
    """windows: {station: (t_start, t_end)}. Returns peak WA amplitude (mm) per
    horizontal channel."""
    out = []
    paz = wa_paz()
    for tr in st:
        sta, cha = tr.stats.station, tr.stats.channel
        if cha[-1] not in "NE12" or sta not in windows:
            continue
        t0, t1 = windows[sta]
        tr = tr.copy()
        if tr.stats.endtime - tr.stats.starttime < 20:
            continue
        try:
            tr.detrend("demean")
            tr.taper(0.05)
            tr.remove_response(inventory=inv, output="DISP", pre_filt=(0.5, 1.0, 40.0, 45.0),
                               water_level=None, zero_mean=True, taper=True)
            tr.simulate(paz_remove=None, paz_simulate=paz)
        except Exception as e:
            if log:
                log.debug("%s.%s response failed: %s", sta, cha, e)
            continue
        w = tr.slice(t0, t1)
        if w.stats.npts < 10:
            continue
        amp_mm = float(np.max(np.abs(w.data))) * 1000.0
        out.append(dict(station=sta, channel=cha, amp_mm=amp_mm))
    return out


def event_magnitude(amps: pd.DataFrame, coef=None, sta_corr: dict | None = None):
    if amps.empty:
        return np.nan, np.nan, 0
    ml_i = np.log10(amps.amp_mm.to_numpy()) + minus_log_a0(amps.hypo_km.to_numpy(), coef)
    if sta_corr:
        ml_i = ml_i - np.array([sta_corr.get(s, 0.0) for s in amps.station])
    med = float(np.median(ml_i))
    mad = float(np.median(np.abs(ml_i - med))) * 1.4826
    return med, mad / np.sqrt(len(ml_i)), len(ml_i)


def compute_magnitudes(cfg, cat: pd.DataFrame, picks: pd.DataFrame, log=None,
                       max_dist=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    from locate import TwoLayer, local_proj
    from snippets import snippet_path

    inv = read_inventory(str(path(cfg, "stationxml") / "XL.xml"))
    stations = pd.read_csv(path(cfg, "meta") / "stations.csv").set_index("station")
    model = TwoLayer(cfg)
    max_dist = max_dist or cfg["magnitude"]["max_hypo_dist_km"]
    coef = cfg["magnitude"].get("attenuation") or DEFAULT_ATTEN
    rows, amp_rows = [], []
    for ev in cat.itertuples():
        f = snippet_path(cfg, ev.event_id, ev.origin_time)
        if not f.exists():
            rows.append(dict(event_id=ev.event_id, ml=np.nan, ml_err=np.nan, ml_n=0))
            continue
        st = read(str(f))
        proj = local_proj(ev.latitude, ev.longitude)
        evp = picks[picks.event_id == ev.event_id]
        windows, hypo = {}, {}
        for sta in {tr.stats.station for tr in st}:
            if sta not in stations.index:
                continue
            s = stations.loc[sta]
            x, y = proj(s.lon, s.lat)
            epi = float(np.hypot(x, y))
            r = float(np.hypot(epi, ev.depth_km + s.elev / 1000))
            if r > max_dist:
                continue
            tp = UTCDateTime(ev.time) + model.tt("P", epi, ev.depth_km, s.elev / 1000)
            ts = UTCDateTime(ev.time) + model.tt("S", epi, ev.depth_km, s.elev / 1000)
            pp = evp[(evp.station == sta) & (evp.phase == "P")]
            if len(pp):
                tp = UTCDateTime(float(pp.time.iloc[0]))
            windows[sta] = (tp - 1.0, ts + 10.0)
            hypo[sta] = max(r, 1.0)
        amps = pd.DataFrame(wa_amplitudes(st, inv, windows, log))
        if amps.empty:
            rows.append(dict(event_id=ev.event_id, ml=np.nan, ml_err=np.nan, ml_n=0))
            continue
        amps["hypo_km"] = amps.station.map(hypo)
        amps = amps[amps.amp_mm > 0]
        amps["event_id"] = ev.event_id
        ml, err, n = event_magnitude(amps, coef)
        amps["ml_i"] = np.log10(amps.amp_mm) + minus_log_a0(amps.hypo_km, coef)
        amp_rows.append(amps)
        rows.append(dict(event_id=ev.event_id, ml=ml, ml_err=err, ml_n=n))
    mags = pd.DataFrame(rows)
    amps = pd.concat(amp_rows, ignore_index=True) if amp_rows else pd.DataFrame()
    return mags, amps


def station_corrections(amps: pd.DataFrame, mags: pd.DataFrame, min_n=10) -> dict:
    """Median station residual (ML_i - event ML) for stations with >= min_n readings."""
    a = amps.merge(mags[["event_id", "ml"]], on="event_id")
    a["res"] = a.ml_i - a.ml
    g = a.groupby("station").res.agg(["median", "count"])
    return g[g["count"] >= min_n]["median"].to_dict()


def distance_residual_trend(amps: pd.DataFrame, mags: pd.DataFrame):
    """Slope of station residual vs log10(R): a non-zero slope means the
    Hutton–Boore attenuation does not fit Mongolia (a calibration diagnostic)."""
    a = amps.merge(mags[["event_id", "ml"]], on="event_id")
    a = a[np.isfinite(a.ml)]
    if len(a) < 20:
        return np.nan, np.nan
    x = np.log10(a.hypo_km)
    y = a.ml_i - a.ml
    A = np.vstack([x, np.ones_like(x)]).T
    sol, *_ = np.linalg.lstsq(A, y, rcond=None)
    return float(sol[0]), float(sol[1])


def calibrate(ours: pd.DataFrame, matched_ref: pd.DataFrame, n_boot=2000, seed=0) -> dict:
    """matched_ref: columns event_id, ref_mag, ref_magtype. Offset = median(ref - ours)."""
    m = ours.merge(matched_ref, on="event_id").dropna(subset=["ml", "ref_mag"])
    if m.empty:
        return dict(n=0, offset=np.nan, ci=(np.nan, np.nan))
    d = (m.ref_mag - m.ml).to_numpy()
    rng = np.random.default_rng(seed)
    boots = [np.median(rng.choice(d, len(d))) for _ in range(n_boot)]
    return dict(n=len(d), offset=float(np.median(d)),
                ci=(float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))),
                by_type=m.groupby("ref_magtype").apply(lambda g: float(np.median(g.ref_mag - g.ml)),
                                                         include_groups=False).to_dict())


def main(argv=None):
    ap = base_parser(__doc__)
    ap.add_argument("--tag", required=True)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    log = get_logger("magnitude")
    d = path(cfg, "catalogs") / args.tag
    cat = pd.read_csv(d / "events.csv")
    picks = pd.read_parquet(d / "picks.parquet")
    mags, amps = compute_magnitudes(cfg, cat, picks, log)
    corr = station_corrections(amps, mags) if not amps.empty else {}
    if corr:  # second pass with station corrections
        rows = []
        for eid, g in amps.groupby("event_id"):
            ml, err, n = event_magnitude(g, cfg["magnitude"].get("attenuation"), corr)
            rows.append(dict(event_id=eid, ml_corr=ml, ml_corr_err=err))
        mags = mags.merge(pd.DataFrame(rows), on="event_id", how="left")
    slope, icpt = distance_residual_trend(amps, mags) if not amps.empty else (np.nan, np.nan)
    log.info("ML for %d/%d events; residual-vs-logR slope %.3f", mags.ml.notna().sum(), len(mags), slope)
    mags.to_csv(d / "magnitudes.csv", index=False)
    if not amps.empty:
        amps.to_parquet(d / "amplitudes.parquet", index=False)
    pd.Series(corr, name="station_correction").to_csv(d / "station_corrections.csv")
    cat = cat.drop(columns=[c for c in ("ml", "ml_err", "ml_n", "ml_corr", "ml_corr_err") if c in cat])
    cat.merge(mags, on="event_id", how="left").to_csv(d / "events.csv", index=False)


if __name__ == "__main__":
    main()
