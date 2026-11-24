"""T3.1: associate ensemble picks into events with PyOcto (Münchmeyer 2024).

PyOcto searches space-time for origins that explain many picks at once. It
recursively splits a 4-D (x, y, z, t) volume into octree cells. A cell is kept
only while enough picks could still come from an origin inside it, given the
travel-time table and a tolerance. Cells that reach the minimum size become
event candidates. Each candidate is located on a fine grid, and its picks are
removed from the pool. Requirements (config `association`): at least `n_picks`
picks, of which >= `n_p_picks` P, >= `n_s_picks` S, and >= `n_p_and_s_picks`
stations with both P and S.

Velocity model: config `velocity_model` (D4). PyOcto needs a precomputed 1-D
travel-time table; we build it once with `VelocityModel1D.create_model` and
cache it under data/meta/.

Input : ensemble picks data/picks/ensemble/XL.*/{year}/{jday}.parquet
Output: data/catalogs/{tag}/events_pyocto.csv, assignments_pyocto.parquet

Example
  python src/associate.py --start 2013-01-01 --end 2013-02-01 --stations HD --tag pilot_2013-01
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
from obspy import UTCDateTime

from common import to_epoch, base_parser, days, get_logger, load_config, path, select_stations


def step_points(layers, zmax=200.0) -> pd.DataFrame:
    """Turn a layer list (top depth, constant vp/vs) into the point list PyOcto
    expects. PyOcto interpolates *linearly* between consecutive points, so each
    layer is written as two points (top and bottom) with the same velocity; the
    interface is then a step, as in the locator. Depths above sea level are
    clipped to 0 (PyOcto's grid starts at 0)."""
    pts = []
    for i, L in enumerate(layers):
        top = max(L["depth"], 0.0)
        bot = layers[i + 1]["depth"] if i + 1 < len(layers) else zmax
        if bot <= 0:
            continue
        pts.append(dict(depth=top, vp=L["vp"], vs=L["vs"]))
        pts.append(dict(depth=bot, vp=L["vp"], vs=L["vs"]))
    return pd.DataFrame(pts)


def velocity_model(cfg, tolerance=None):
    import pyocto

    layers = step_points(cfg["velocity_model"]["layers"])
    tag = "_".join(f"{r.depth:g}-{r.vp:g}-{r.vs:g}" for r in layers.itertuples())
    f = path(cfg, "meta") / f"pyocto_vmodel_v2_{tag}.bin"
    if not f.exists():
        # Our own exact layered first-arrival tables in PyOcto's binary format
        # (pyocto's create_model needs pyrocko, which does not build against NumPy 2).
        from traveltime import write_pyocto_model

        f.parent.mkdir(parents=True, exist_ok=True)
        write_pyocto_model(cfg["velocity_model"]["layers"], f, delta=1.0, xmax=900.0,
                           zmax=cfg["association"]["zlim"][1] + 5.0)
    a = cfg["association"]
    return pyocto.VelocityModel1D(f, tolerance=tolerance or a.get("tt_tolerance", 1.5),
                                  association_cutoff_distance=a.get("association_cutoff_km"))


def build_associator(cfg, stations: pd.DataFrame):
    import pyocto

    a = cfg["association"]
    m = a["xy_margin_km"] / 111.0
    lat = (stations.lat.min() - m, stations.lat.max() + m)
    lon = (stations.lon.min() - m / np.cos(np.radians(stations.lat.mean())),
           stations.lon.max() + m / np.cos(np.radians(stations.lat.mean())))
    assoc = pyocto.OctoAssociator.from_area(
        lat=lat, lon=lon, zlim=tuple(a["zlim"]), time_before=a["time_before"],
        velocity_model=velocity_model(cfg), n_picks=a["n_picks"], n_p_picks=a["n_p_picks"],
        n_s_picks=a["n_s_picks"], n_p_and_s_picks=a["n_p_and_s_picks"],
        pick_match_tolerance=a["pick_match_tolerance"], n_threads=a.get("n_threads", 4))
    return assoc, lat, lon


def load_ensemble(cfg, stations, start, end) -> pd.DataFrame:
    from ensemble import ens_path

    frames = []
    net = cfg["fdsn"]["network"]
    for t in days(start, end):
        for sta in stations.station:
            f = ens_path(cfg, net, sta, t)
            if f.exists():
                frames.append(pd.read_parquet(f))
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=["network", "station", "phase", "time", "prob"])
    return pd.concat(frames, ignore_index=True)


def associate(cfg, picks: pd.DataFrame, stations: pd.DataFrame, log=None):
    """Run PyOcto. Returns (events, assignments) with absolute times and lat/lon."""
    assoc, lat, lon = build_associator(cfg, stations)
    st = pd.DataFrame(dict(id=stations.station, latitude=stations.lat, longitude=stations.lon,
                           elevation=stations.elev))
    st = assoc.transform_stations(st)
    p = picks.copy()
    p["time"] = to_epoch(p["time"])
    p = p.sort_values("time").reset_index(drop=True)
    p["pick_idx"] = np.arange(len(p))
    tic = time.time()
    events, assignments = assoc.associate(p[["station", "phase", "time", "prob"]].rename(
        columns={"prob": "peak_value"}), st)
    if log:
        log.info("PyOcto: %d picks -> %d events in %.1f s", len(p), len(events), time.time() - tic)
    if len(events) == 0:
        return events, assignments
    events = assoc.transform_events(events)
    events["origin_time"] = [str(UTCDateTime(t)) for t in events["time"]]
    events["edge_flag"] = ((events.latitude - lat[0] < 0.2) | (lat[1] - events.latitude < 0.2) |
                           (events.longitude - lon[0] < 0.3) | (lon[1] - events.longitude < 0.3))
    assignments = assignments.merge(p[["pick_idx", "prob", "n_models", "time_std"]],
                                    on="pick_idx", how="left") if "n_models" in p else assignments
    return events, assignments


def main(argv=None):
    ap = base_parser(__doc__)
    from ensemble import add_ensemble_args

    add_ensemble_args(ap)
    ap.add_argument("--tag", required=True, help="output folder under data/catalogs/")
    args = ap.parse_args(argv)
    from ensemble import apply_ensemble_args

    cfg = apply_ensemble_args(load_config(args.config), args)
    log = get_logger("associate")
    stations = select_stations(cfg, args.stations or cfg["pilot"]["subarray"], args.start, args.end)
    picks = load_ensemble(cfg, stations, args.start, args.end)
    picks = picks[picks.station.isin(stations.station)]
    log.info("%d ensemble picks on %d stations", len(picks), picks.station.nunique())
    events, assignments = associate(cfg, picks, stations, log)
    out = path(cfg, "catalogs") / args.tag
    out.mkdir(parents=True, exist_ok=True)
    events.to_csv(out / "events_pyocto.csv", index=False)
    assignments.to_parquet(out / "assignments_pyocto.parquet", index=False)
    log.info("wrote %s", out)


if __name__ == "__main__":
    main()
