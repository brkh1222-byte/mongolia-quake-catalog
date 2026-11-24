"""Build the frozen analysis regions (config/regions.geojson) from rules, and
draw the review map (results/fig_regions.png).

The rules and their published sources are in notes/decisions.md (D20). The
polygons are generated, not hand-drawn, so they can be reproduced exactly:

  hangay_interior  the largest connected area where the ETOPO1 elevation,
                   smoothed with a 50 km x 50 km moving average, is >= THRESH m,
                   searched inside 45-50N, 94-104E; simplified to 0.05 deg.
  hangay_margin    the footprint of the Hangay (HD) stations (convex hull,
                   buffered 0.3 deg) minus hangay_interior.
  khovsgol         the footprint of the Khovsgol (HV) stations (convex hull,
                   buffered 0.3 deg).
  gobi_altai       the footprint of the Gobi-Altai (AT) stations (convex hull,
                   buffered 0.3 deg).
Later regions win where polygons overlap (order: margin, interior, khovsgol,
gobi_altai), so an event is labelled by geography, whichever subarray recorded it.
A ~40 km morphological opening removes narrow necks from the interior mask.

Regions are limited to station footprints on purpose: depths and magnitudes
are only reliable inside the network (azimuthal gap <= 180 deg).

Input : data/reference/dem/etopo1.nc (ETOPO1, NOAA ERDDAP `etopo180`),
        data/meta/stations.csv, config/gem_faults_mongolia.geojson
Usage : python src/make_regions.py [--thresh 2000] [--no-write]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

from common import REPO

BUFFER_DEG = 0.3
SMOOTH_KM = 50.0
SEARCH_BOX = (45.0, 50.0, 94.0, 104.0)


def load_dem():
    from scipy.io import netcdf_file

    f = netcdf_file(str(REPO / "data/reference/dem/etopo1.nc"), mmap=False)
    return (f.variables["latitude"][:].copy(), f.variables["longitude"][:].copy(),
            f.variables["altitude"][:].astype(float))


def interior_polygon(lat, lon, z, thresh):
    from scipy.ndimage import label, uniform_filter
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    dlat_km = 111.2 * (lat[1] - lat[0])
    dlon_km = 111.2 * (lon[1] - lon[0]) * np.cos(np.radians(47.5))
    zs = uniform_filter(z, (int(round(SMOOTH_KM / dlat_km)), int(round(SMOOTH_KM / dlon_km))))
    la0, la1, lo0, lo1 = SEARCH_BOX
    m = (zs >= thresh) & (lat[:, None] > la0) & (lat[:, None] < la1) & (lon[None, :] > lo0) & (lon[None, :] < lo1)
    # morphological opening (~40 km): removes narrow necks that would attach
    # neighbouring ranges (e.g. the Bulnay/Tarvagatai ridge) to the dome
    from scipy.ndimage import binary_opening
    ry, rx = int(round(20 / dlat_km)), int(round(20 / dlon_km))
    yy, xx = np.ogrid[-ry:ry + 1, -rx:rx + 1]
    m = binary_opening(m, structure=(yy / ry) ** 2 + (xx / rx) ** 2 <= 1)
    lab, n = label(m)
    k = np.argmax(np.bincount(lab.ravel())[1:]) + 1
    mm = lab == k
    # raster -> polygon: union of row runs as thin rectangles
    hl, hw = (lat[1] - lat[0]) / 2, (lon[1] - lon[0]) / 2
    boxes = []
    for i in np.where(mm.any(axis=1))[0]:
        row = mm[i].astype(int)
        d = np.diff(np.r_[0, row, 0])
        for a, b in zip(np.where(d == 1)[0], np.where(d == -1)[0]):
            boxes.append(Polygon([(lon[a] - hw, lat[i] - hl), (lon[b - 1] + hw, lat[i] - hl),
                                  (lon[b - 1] + hw, lat[i] + hl), (lon[a] - hw, lat[i] + hl)]))
    poly = unary_union([b.buffer(1e-5) for b in boxes]).buffer(0)
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    poly = Polygon(poly.exterior).simplify(0.05)  # drop holes (small basins inside the dome)
    return poly, zs


def area_km2(poly):
    from pyproj import Geod

    return abs(Geod(ellps="WGS84").geometry_area_perimeter(poly)[0]) / 1e6


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--thresh", type=float, default=2000.0)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args(argv)
    from shapely.geometry import MultiPoint, mapping

    st = pd.read_csv(REPO / "data/meta/stations.csv")
    st = st[~st.station.isin(["HD20A", "HD47A"])]  # short-lived 2012 codes
    hull = {s: MultiPoint(list(zip(g.lon, g.lat))).convex_hull.buffer(BUFFER_DEG) for s, g in st.groupby("subarray")}
    lat, lon, z = load_dem()
    interior, zs = interior_polygon(lat, lon, z, args.thresh)
    interior = interior.intersection(hull["HD"])
    regions = {
        "hangay_margin": hull["HD"].difference(interior),
        "hangay_interior": interior,
        "khovsgol": hull["HV"],
        "gobi_altai": hull["AT"],
    }
    notes = {
        "hangay_interior": f"largest connected area of {SMOOTH_KM:.0f}-km-smoothed ETOPO1 elevation >= {args.thresh:.0f} m, inside the HD footprint",
        "hangay_margin": f"HD station convex hull buffered {BUFFER_DEG} deg, minus hangay_interior",
        "khovsgol": f"HV station convex hull buffered {BUFFER_DEG} deg (wins over hangay_margin where they overlap)",
        "gobi_altai": f"AT station convex hull buffered {BUFFER_DEG} deg (wins over hangay_margin where they overlap)",
    }
    feats = []
    for name, poly in regions.items():
        if poly.geom_type == "MultiPolygon":
            poly = max(poly.geoms, key=lambda g: g.area)
        poly = poly.simplify(0.01)
        regions[name] = poly
        n_sta = int(sum(poly.contains(p) for p in MultiPoint(list(zip(st.lon, st.lat))).geoms))
        feats.append({"type": "Feature",
                      "properties": {"name": name, "rule": notes[name], "area_km2": round(area_km2(poly)),
                                     "n_stations": n_sta},
                      "geometry": json.loads(json.dumps(mapping(poly), default=float))})
        print(f"{name}: {area_km2(poly):.0f} km2, {n_sta} stations")
    gj = {"type": "FeatureCollection", "name": "mqc_regions_v1_FROZEN",
          "description": "Analysis regions, frozen 2026-11-25 before any full-catalogue depth or b-value was computed. "
                         "Generated by src/make_regions.py (rules and sources: notes/decisions.md D20). "
                         "Order matters: later features win where they overlap.",
          "features": feats}
    if not args.no_write:
        def rnd(o):
            if isinstance(o, float):
                return round(o, 4)
            if isinstance(o, (list, tuple)):
                return [rnd(x) for x in o]
            if isinstance(o, dict):
                return {k: rnd(v) for k, v in o.items()}
            return o
        (REPO / "config/regions.geojson").write_text(json.dumps(rnd(gj)))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 7.5))
    sub = (slice(None, None, 3), slice(None, None, 3))
    im = ax.pcolormesh(lon[sub[1]], lat[sub[0]], z[sub], cmap="terrain", vmin=0, vmax=4000, shading="auto", alpha=0.75)
    ax.contour(lon[sub[1]], lat[sub[0]], zs[sub], levels=[args.thresh], colors="k", linewidths=0.5, linestyles=":")
    with open(REPO / "config/gem_faults_mongolia.geojson") as fh:
        for ft in json.load(fh)["features"]:
            g = ft["geometry"]
            for line in ([g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]):
                a = np.array(line)
                ax.plot(a[:, 0], a[:, 1], color="0.15", lw=0.5)
    colors = {"hangay_interior": "#c0392b", "hangay_margin": "#e67e22", "khovsgol": "#2471a3", "gobi_altai": "#1e8449"}
    for name, poly in regions.items():
        x, y = poly.exterior.xy
        ax.plot(x, y, color=colors[name], lw=2, label=f"{name} ({area_km2(poly) / 1000:.0f}k km²)")
        for hole in poly.interiors:
            hx, hy = hole.xy
            ax.plot(hx, hy, color=colors[name], lw=2)
    ax.scatter(st.lon, st.lat, marker="^", s=14, c="w", edgecolors="k", lw=0.5, zorder=5, label="XL stations")
    ax.set_xlim(91.5, 106); ax.set_ylim(42.5, 52.5)
    ax.set_aspect(1 / np.cos(np.radians(47.5)))
    ax.set_xlabel("Longitude (°E)"); ax.set_ylabel("Latitude (°N)")
    plt.colorbar(im, ax=ax, label="elevation (m, ETOPO1)", shrink=0.7)
    ax.legend(loc="lower right", fontsize=8)
    ax.set_title(f"Frozen analysis regions v1. Dotted: {SMOOTH_KM:.0f}-km-smoothed {args.thresh:.0f} m contour. "
                 "Thin lines: GEM active faults", fontsize=9)
    fig.savefig(REPO / "results/fig_regions.png", dpi=180, bbox_inches="tight")
    print("wrote results/fig_regions.png")


if __name__ == "__main__":
    main()
