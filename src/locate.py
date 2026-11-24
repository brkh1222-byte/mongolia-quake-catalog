"""T3.2: first-pass absolute location (notes/decisions.md D5).

PyOcto already returns a grid location for each event. Here every event is
relocated independently with a weighted, robust least-squares inversion of its
associated P and S arrival times (Geiger's method, solved with
scipy.optimize.least_squares).

Travel times come from the analytic first arrival in the 2-layer model of
config `velocity_model`: a crust over a mantle half-space.
  direct wave : t = sqrt(x^2 + (z + e)^2) / v1
  Moho head   : t = x / v2 + ((H - z) + (H + e)) * cos(ic) / v1,  sin ic = v1 / v2
    (valid only beyond the critical distance), where
    x = epicentral distance, z = source depth below sea level,
    e = station elevation, H = Moho depth.
The first arrival is the smaller of the two. Sources below the Moho are not
expected (zlim 0–60 km). For them the direct ray is approximated with the
mean slowness.

Uncertainties: the 1-sigma errors come from the covariance (J^T W J)^-1 * s^2,
where s^2 is the reduced chi-square of the weighted residuals and J is the
Jacobian. We report the horizontal major semi-axis (erh) and the depth error
(erz). Events with fewer than 4 stations, or whose depth sits at a bound, are
flagged.

Output: data/catalogs/{tag}/events.csv (one row per event, final first-pass
locations) and picks.parquet (the picks with residuals).

Example
  python src/locate.py --tag pilot_2013-01 --stations HD --start 2013-01-01 --end 2013-02-01
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
from obspy import UTCDateTime
from pyproj import Proj
from scipy.optimize import least_squares

from common import base_parser, get_logger, load_config, path, select_stations


class TwoLayer:
    def __init__(self, cfg):
        lay = cfg["velocity_model"]["layers"]
        if len(lay) != 2:
            raise NotImplementedError("locate.py implements the 2-layer analytic model only")
        self.H = lay[1]["depth"]
        self.v = {"P": (lay[0]["vp"], lay[1]["vp"]), "S": (lay[0]["vs"], lay[1]["vs"])}

    def tt(self, phase, x, z, e):
        """Travel time (s). x: epicentral km, z: depth km (b.s.l.), e: station elevation km."""
        v1, v2 = self.v[phase]
        d = np.sqrt(x ** 2 + (z + e) ** 2)
        direct = d / v1
        ic = np.arcsin(v1 / v2)
        zz = np.minimum(z, self.H)
        head = x / v2 + ((self.H - zz) + (self.H + e)) * np.cos(ic) / v1
        xcrit = (self.H - zz) * np.tan(ic) + (self.H + e) * np.tan(ic)
        head = np.where(x >= xcrit, head, np.inf)
        return np.minimum(direct, head)


def make_model(cfg):
    lay = cfg["velocity_model"]["layers"]
    if len(lay) == 2 and cfg["velocity_model"].get("kind", "analytic") == "analytic":
        return TwoLayer(cfg)
    from traveltime import TableModel

    return TableModel(lay)


def local_proj(lat0, lon0):
    return Proj(proj="aeqd", lat_0=lat0, lon_0=lon0, datum="WGS84", units="km")


def locate_event(model, ex0, sx, sy, se, ph, tobs, w, zbounds=(-3.0, 60.0)):
    """ex0: initial (x, y, z, t0). Returns dict with solution and errors."""
    def resid(m):
        x = np.hypot(sx - m[0], sy - m[1])
        tp = np.where(ph == "P", model.tt("P", x, m[2], se), model.tt("S", x, m[2], se))
        return (tobs - (m[3] + tp)) * np.sqrt(w)

    lb = [-np.inf, -np.inf, zbounds[0], -np.inf]
    ub = [np.inf, np.inf, zbounds[1], np.inf]
    x0 = np.array(ex0, float)
    x0[2] = np.clip(x0[2], zbounds[0] + 0.5, zbounds[1] - 0.5)
    best = None
    for z0 in (x0[2], 5.0, 15.0, 30.0):  # several starting depths: avoid local minima
        s = x0.copy()
        s[2] = z0
        r = least_squares(resid, s, bounds=(lb, ub), loss="soft_l1", f_scale=0.5)
        if best is None or r.cost < best.cost:
            best = r
    r = best
    n = len(tobs)
    res = resid(r.x) / np.sqrt(w)
    dof = max(n - 4, 1)
    s2 = float(np.sum(w * res ** 2) / dof)
    try:
        cov = np.linalg.inv(r.jac.T @ r.jac) * max(s2, 0.05 ** 2)
        hcov = cov[:2, :2]
        erh = float(np.sqrt(np.max(np.linalg.eigvalsh(hcov))))
        erz = float(np.sqrt(cov[2, 2]))
        ert = float(np.sqrt(cov[3, 3]))
    except np.linalg.LinAlgError:
        erh = erz = ert = np.nan
    at_bound = bool(r.x[2] <= zbounds[0] + 0.05 or r.x[2] >= zbounds[1] - 0.05)
    return dict(x=r.x[0], y=r.x[1], z=r.x[2], t0=r.x[3], rms=float(np.sqrt(np.mean(res ** 2))),
                erh=erh, erz=erz, ert=ert, depth_at_bound=at_bound), res


def locate_catalog(cfg, events: pd.DataFrame, assignments: pd.DataFrame, stations: pd.DataFrame,
                   log=None):
    model = make_model(cfg)
    zb = (-3.0, 60.0) if isinstance(model, TwoLayer) else (0.0, 60.0)
    lat0, lon0 = stations.lat.mean(), stations.lon.mean()
    proj = local_proj(lat0, lon0)
    sxy = {r.station: (*proj(r.lon, r.lat), r.elev / 1000.0) for r in stations.itertuples()}
    out, picks_out = [], []
    for ev in events.itertuples():
        a = assignments[assignments.event_idx == ev.idx]
        a = a[a.station.isin(sxy)]
        if len(a) < 4:
            continue
        sx = np.array([sxy[s][0] for s in a.station])
        sy = np.array([sxy[s][1] for s in a.station])
        se = np.array([sxy[s][2] for s in a.station])
        ph = a.phase.to_numpy()
        tobs = a.time.to_numpy() - ev.time
        w = (a["prob"].to_numpy() if "prob" in a else np.ones(len(a))).astype(float)
        w = np.where(ph == "S", 0.5 * w, w)  # S picks are less precise
        ex, ey = proj(ev.longitude, ev.latitude)
        sol, res = locate_event(model, (ex, ey, ev.z, 0.0), sx, sy, se, ph, tobs, w, zbounds=zb)
        lon, lat = proj(sol["x"], sol["y"], inverse=True)
        dist = np.hypot(sx - sol["x"], sy - sol["y"])
        az = np.degrees(np.arctan2(sx - sol["x"], sy - sol["y"])) % 360
        gap = _azimuthal_gap(az)
        ot = ev.time + sol["t0"]
        out.append(dict(event_id=f"mqc{UTCDateTime(ot).strftime('%Y%m%d%H%M%S')}{int(round((ot % 1) * 100)):02d}",
                        origin_time=str(UTCDateTime(ot)), time=ot, latitude=lat, longitude=lon,
                        depth_km=sol["z"], erh_km=sol["erh"], erz_km=sol["erz"], ert_s=sol["ert"],
                        rms_s=sol["rms"], n_picks=len(a), n_p=int((ph == "P").sum()),
                        n_s=int((ph == "S").sum()), n_sta=a.station.nunique(), gap_deg=gap,
                        dmin_km=float(dist.min()), depth_at_bound=sol["depth_at_bound"],
                        pyocto_lat=ev.latitude, pyocto_lon=ev.longitude, pyocto_depth=ev.z,
                        pyocto_idx=ev.idx, edge_flag=getattr(ev, "edge_flag", False)))
        aa = a.copy()
        aa["event_id"] = out[-1]["event_id"]
        aa["residual_s"] = res
        aa["dist_km"] = dist
        picks_out.append(aa)
    cat = pd.DataFrame(out)
    picks = pd.concat(picks_out, ignore_index=True) if picks_out else pd.DataFrame()
    if log:
        log.info("located %d / %d events", len(cat), len(events))
    return cat, picks


def _azimuthal_gap(az):
    a = np.sort(np.asarray(az))
    if len(a) < 2:
        return 360.0
    return float(np.max(np.diff(np.concatenate([a, [a[0] + 360]]))))


def quality_flags(cat: pd.DataFrame, cfg) -> pd.DataFrame:
    """Quality class A–D used in validation and analysis.
    A: rms<=0.5 s, gap<=180, erh<=3 km, erz<=5 km, dmin<=max(15 km, 1.5*depth), not at a depth bound
    B: rms<=0.8, gap<=250, erh<=6, erz<=10;  C: located but worse;  D: rms>max_rms or edge of grid."""
    q = np.full(len(cat), "C", dtype=object)
    good_dmin = cat.dmin_km <= np.maximum(15.0, 1.5 * cat.depth_km.clip(lower=0))
    a = ((cat.rms_s <= 0.5) & (cat.gap_deg <= 180) & (cat.erh_km <= 3) & (cat.erz_km <= 5) &
         good_dmin & ~cat.depth_at_bound)
    b = (cat.rms_s <= 0.8) & (cat.gap_deg <= 250) & (cat.erh_km <= 6) & (cat.erz_km <= 10)
    q[b.to_numpy()] = "B"
    q[a.to_numpy()] = "A"
    d = (cat.rms_s > cfg["location"]["max_rms_s"]) | cat.edge_flag.astype(bool)
    q[d.to_numpy()] = "D"
    cat = cat.copy()
    cat["quality"] = q
    return cat


def remove_split_duplicates(cat: pd.DataFrame, dt_s=20.0, dist_km=150.0):
    """PyOcto sometimes splits one large regional event into two: the second
    'event' is built from later regional phases (Pg/Sg/Lg picked as P/S) and is
    located ~5–15 s earlier or later and tens of km away (pilot days 1–2: 4 of 44
    events, all M > 2 events NE of the array, each matching one ISC/BYKL event).
    Within dt_s and dist_km, keep the event with more picks; return (kept, removed)."""
    c = cat.sort_values("time").reset_index(drop=True)
    drop = set()
    for i in range(len(c)):
        if i in drop:
            continue
        j = i + 1
        while j < len(c) and c.time[j] - c.time[i] <= dt_s:
            d = 111.2 * np.hypot(c.latitude[j] - c.latitude[i],
                                 (c.longitude[j] - c.longitude[i]) * np.cos(np.radians(c.latitude[i])))
            if d <= dist_km and j not in drop:
                drop.add(j if c.n_picks[j] <= c.n_picks[i] else i)
            j += 1
    keep = c.drop(index=list(drop)).reset_index(drop=True)
    return keep, c.loc[sorted(drop)]


def main(argv=None):
    ap = base_parser(__doc__)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--vmodel", default=None,
                    help="YAML with an alternative velocity_model (sensitivity test); output gets a suffix")
    ap.add_argument("--suffix", default="")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    if args.vmodel:
        import yaml
        cfg["velocity_model"] = yaml.safe_load(open(args.vmodel))["velocity_model"]
    log = get_logger("locate")
    d = path(cfg, "catalogs") / args.tag
    events = pd.read_csv(d / "events_pyocto.csv")
    assignments = pd.read_parquet(d / "assignments_pyocto.parquet")
    stations = select_stations(cfg, args.stations or cfg["pilot"]["subarray"], args.start, args.end)
    cat, picks = locate_catalog(cfg, events, assignments, stations, log)
    cat = quality_flags(cat, cfg)
    cat, dups = remove_split_duplicates(cat)
    dups.to_csv(d / f"events_split_duplicates{args.suffix}.csv", index=False)
    log.info("removed %d split duplicates", len(dups))
    picks = picks[picks.event_id.isin(cat.event_id)]
    cat.to_csv(d / f"events{args.suffix}.csv", index=False)
    picks.to_parquet(d / f"picks{args.suffix}.parquet", index=False)
    log.info("quality classes: %s", cat.quality.value_counts().to_dict())


if __name__ == "__main__":
    main()
