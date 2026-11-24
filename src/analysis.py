"""T5.x: catalog statistics (completeness, b-value, depth, blasts, faults).

All functions take a catalog DataFrame (columns: time, latitude, longitude,
depth_km, ml, quality, ...) and are applied by src/analyze.py.

T5.1  Magnitude of completeness and b-value
  * mc_maxc: maximum curvature (the magnitude bin with the most events), plus the
    usual +0.2 correction (Woessner & Wiemer 2005).
  * mc_gof: goodness-of-fit (Wiemer & Wyss 2000). Mc is the smallest cutoff at which
    a Gutenberg–Richter fit explains >= 90 % (or 95 %) of the observed
    frequency–magnitude distribution (FMD).
  * b_value: Aki (1965) maximum likelihood with Utsu's (1966) binning correction,
        b = log10(e) / (mean(M) - (Mc - dM/2)),
    the Shi & Bolt (1982) standard error, and a bootstrap 95 % interval.
  * b_map: b on a grid, from the N nearest events above Mc (minimum N events).
T5.2  Seismogenic depth: D90/D95 (90th/95th depth percentiles) with bootstrap
      intervals, per region; depth sections along great-circle profiles.
T5.3  Distance from events to fault traces (any GeoJSON of lines, e.g. AFEAD)
      and per-fault statistics.
T5.4  Quarry-blast screening: local-time day/night ratio per grid cell; events
      in daytime working hours, shallower than 5 km, in cells with an anomalous
      day/night ratio are *flagged*, not deleted.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

LOG10E = np.log10(np.e)


# ---------------------------------------------------------------- T5.1
def fmd(mags, dm=0.1):
    m = np.asarray(mags, float)
    m = m[np.isfinite(m)]
    if len(m) == 0:
        return np.array([]), np.array([]), np.array([])
    bins = np.round(np.arange(np.floor(m.min() / dm) * dm, m.max() + dm, dm), 6)
    idx = np.round((m - bins[0]) / dm).astype(int)
    counts = np.bincount(idx, minlength=len(bins))[:len(bins)]
    cum = counts[::-1].cumsum()[::-1]
    return bins, counts, cum


def mc_maxc(mags, dm=0.1, correction=0.2):
    bins, counts, _ = fmd(mags, dm)
    if len(bins) == 0:
        return np.nan
    return float(bins[np.argmax(counts)] + correction)


def b_value(mags, mc, dm=0.1, n_boot=1000, seed=0, min_n=50):
    m = np.asarray(mags, float)
    m = m[np.isfinite(m) & (m >= mc - dm / 2 + 1e-9)]
    n = len(m)
    out = dict(n=n, mc=mc, b=np.nan, b_err_shibolt=np.nan, b_lo=np.nan, b_hi=np.nan, a=np.nan)
    if n < 2:
        return out
    mean = m.mean()
    b = LOG10E / (mean - (mc - dm / 2))
    err = 2.3 * b ** 2 * np.sqrt(np.sum((m - mean) ** 2) / (n * (n - 1)))  # Shi & Bolt (1982)
    out.update(b=float(b), b_err_shibolt=float(err), a=float(np.log10(n) + b * mc), reliable=bool(n >= min_n))
    if n_boot > 0:
        rng = np.random.default_rng(seed)
        bs = [LOG10E / (rng.choice(m, n).mean() - (mc - dm / 2)) for _ in range(n_boot)]
        out.update(b_lo=float(np.percentile(bs, 2.5)), b_hi=float(np.percentile(bs, 97.5)))
    return out


def mc_gof(mags, dm=0.1, levels=(95, 90)):
    """Return (Mc, level) for the first level reached, else (nan, None), plus the R curve."""
    bins, counts, cum = fmd(mags, dm)
    curve = []
    for i, mc in enumerate(bins):
        sel = bins >= mc - 1e-9
        if cum[i] < 25:
            break
        b = b_value(mags, mc, dm, n_boot=0)["b"]
        a = np.log10(cum[i]) + b * mc
        pred_cum = 10 ** (a - b * bins[sel])
        pred = -np.diff(np.append(pred_cum, 0.0))
        R = 100 - 100 * np.sum(np.abs(counts[sel] - pred)) / np.sum(counts[sel])
        curve.append((float(mc), float(R)))
    for lev in levels:
        for mc, R in curve:
            if R >= lev:
                return mc, lev, curve
    return np.nan, None, curve


def mc_bootstrap(mags, method="maxc", dm=0.1, n_boot=200, seed=0):
    rng = np.random.default_rng(seed)
    m = np.asarray(mags, float)
    m = m[np.isfinite(m)]
    f = (lambda x: mc_maxc(x, dm)) if method == "maxc" else (lambda x: mc_gof(x, dm)[0])
    vals = np.array([f(rng.choice(m, len(m))) for _ in range(n_boot)], float)
    return float(np.nanmean(vals)), float(np.nanstd(vals))


def b_map(cat, mc, lat_grid, lon_grid, n_nearest=100, max_radius_km=50.0, dm=0.1, min_n=50):
    c = cat[cat.ml >= mc - dm / 2]
    lat, lon, m = c.latitude.to_numpy(), c.longitude.to_numpy(), c.ml.to_numpy()
    B = np.full((len(lat_grid), len(lon_grid)), np.nan)
    for i, la in enumerate(lat_grid):
        for j, lo in enumerate(lon_grid):
            d = 111.2 * np.hypot(lat - la, (lon - lo) * np.cos(np.radians(la)))
            idx = np.argsort(d)[:n_nearest]
            idx = idx[d[idx] <= max_radius_km]
            if len(idx) >= min_n:
                B[i, j] = b_value(m[idx], mc, dm, n_boot=0)["b"]
    return B


# ---------------------------------------------------------------- T5.2
def depth_percentiles(depths, q=(90, 95), n_boot=1000, seed=0):
    d = np.asarray(depths, float)
    d = d[np.isfinite(d)]
    out = dict(n=len(d))
    if len(d) < 5:
        return out
    rng = np.random.default_rng(seed)
    boots = np.array([np.percentile(rng.choice(d, len(d)), q) for _ in range(n_boot)])
    for k, qq in enumerate(q):
        out[f"D{qq}"] = float(np.percentile(d, qq))
        out[f"D{qq}_lo"] = float(np.percentile(boots[:, k], 2.5))
        out[f"D{qq}_hi"] = float(np.percentile(boots[:, k], 97.5))
    return out


def profile_projection(cat, lat0, lon0, lat1, lon1, half_width_km=25.0):
    """Project events onto the segment (lat0,lon0)->(lat1,lon1) in a local flat frame.
    Returns events within half_width_km with distance along profile (km)."""
    from pyproj import Geod

    g = Geod(ellps="WGS84")
    az, _, length = g.inv(lon0, lat0, lon1, lat1)
    az_e, _, dist = g.inv(np.full(len(cat), lon0), np.full(len(cat), lat0),
                          cat.longitude.to_numpy(), cat.latitude.to_numpy())
    ang = np.radians(az_e - az)
    along = dist / 1000 * np.cos(ang)
    across = dist / 1000 * np.sin(ang)
    sel = (np.abs(across) <= half_width_km) & (along >= 0) & (along <= length / 1000)
    out = cat[sel].copy()
    out["along_km"] = along[sel]
    out["across_km"] = across[sel]
    return out, length / 1000


# ---------------------------------------------------------------- regions
def load_regions(f: Path):
    from shapely.geometry import shape

    with open(f) as fh:
        gj = json.load(fh)
    return {ft["properties"]["name"]: shape(ft["geometry"]) for ft in gj["features"]}


def assign_regions(cat, regions: dict):
    from shapely import points, contains

    pts = points(cat.longitude.to_numpy(), cat.latitude.to_numpy())
    lab = np.full(len(cat), "outside", dtype=object)
    for name, poly in regions.items():  # later polygons win where they overlap
        lab[contains(poly, pts)] = name
    return lab


# ---------------------------------------------------------------- T5.3
def fault_distances(cat, faults_geojson: Path, name_field="name"):
    """Distance (km) from each event epicentre to the nearest fault trace, and that fault's name."""
    from pyproj import Transformer
    from shapely import STRtree, points
    from shapely.geometry import shape
    from shapely.ops import transform

    with open(faults_geojson) as fh:
        gj = json.load(fh)
    lat0, lon0 = cat.latitude.mean(), cat.longitude.mean()
    tr = Transformer.from_crs("EPSG:4326", f"+proj=aeqd +lat_0={lat0} +lon_0={lon0} +units=km",
                              always_xy=True)
    geoms, names = [], []
    for k, ft in enumerate(gj["features"]):
        geoms.append(transform(tr.transform, shape(ft["geometry"])))
        names.append(str(ft["properties"].get(name_field) or f"fault_{k}"))
    x, y = tr.transform(cat.longitude.to_numpy(), cat.latitude.to_numpy())
    pts = points(x, y)
    tree = STRtree(geoms)
    idx = tree.nearest(pts)
    d = np.array([pts[i].distance(geoms[j]) for i, j in enumerate(idx)])
    return d, np.array(names, dtype=object)[idx]


def per_fault_stats(cat, dist, names, max_km=10.0, mc=None):
    c = cat.assign(fault=names, fault_dist_km=dist)
    c = c[c.fault_dist_km <= max_km]
    if mc is not None:
        c = c[c.ml >= mc]
    g = c.groupby("fault").agg(n=("time", "size"), ml_max=("ml", "max"),
                               depth_median=("depth_km", "median"))
    return g.sort_values("n", ascending=False)


# ---------------------------------------------------------------- T5.4
def local_hour(times_epoch, lon):
    """Approximate local solar hour (no daylight saving in Mongolia's
    seismicity-relevant sense; solar time avoids time-zone politics)."""
    utc_h = (np.asarray(times_epoch) % 86400) / 3600
    return (utc_h + np.asarray(lon) / 15.0) % 24


def blast_flags(cat, cell_deg=0.25, day=(9, 18), min_events=10, ratio_thr=2.0, max_depth=5.0):
    """Flag likely blasts. Day/night ratio r = (n_day/len_day)/(n_night/len_night) per cell;
    natural seismicity gives r ~ 1. Events flagged: local hour in `day`, depth < max_depth,
    in a cell with >= min_events and r >= ratio_thr."""
    h = local_hour(cat.time.to_numpy(), cat.longitude.to_numpy())
    is_day = (h >= day[0]) & (h < day[1])
    cell = (np.floor(cat.latitude / cell_deg).astype(int).astype(str) + "_" +
            np.floor(cat.longitude / cell_deg).astype(int).astype(str))
    df = pd.DataFrame(dict(cell=cell, day=is_day))
    len_day = day[1] - day[0]
    g = df.groupby("cell").day.agg(["sum", "size"])
    n_night = g["size"] - g["sum"]
    ratio = (g["sum"] / len_day) / ((n_night + 0.5) / (24 - len_day))
    bad = set(g.index[(g["size"] >= min_events) & (ratio >= ratio_thr)])
    flag = np.array([c in bad for c in cell]) & is_day & (cat.depth_km.to_numpy() < max_depth)
    overall = (is_day.sum() / len_day) / (max((~is_day).sum(), 1) / (24 - len_day))
    return flag, ratio, float(overall)
