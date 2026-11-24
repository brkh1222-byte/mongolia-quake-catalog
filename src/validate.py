"""T3.3: validate a catalog against reference bulletins.

References (downloaded once into data/reference/):
  * ISC Bulletin through the ISC FDSN event service (all authors; the prime
    hypocentre per event)
  * EMSC (seismicportal.eu FDSN)
  * USGS ComCat (earthquake.usgs.gov FDSN)
Matching: a reference event matches our nearest event in origin time if
|dt| <= 10 s and the epicentral distance <= 100 km. Reference catalogs for
Mongolia have origin-time and location errors of several seconds and tens of
km (many BYKL solutions are rounded to 0.01–0.1°).
Reported: the match rate for reference events inside the network footprint
(the convex hull of the stations, buffered by 0.3°), epicentral offsets, depth
differences, origin-time differences and our ML vs their magnitudes.
Unmatched reference events are listed with the reason found by a looser search.

Output: results/validation_{tag}.csv (one row per reference event) and a
markdown fragment results/validation_{tag}_refs.md that
results/validation_month.md includes.

Example
  python src/validate.py --tag pilot_2013-01 --start 2013-01-01 --end 2013-02-01 --stations HD
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import io
import urllib.request

import numpy as np
import pandas as pd
from obspy import UTCDateTime

from common import base_parser, get_logger, load_config, path, select_stations, to_epoch

SERVICES = {
    "ISC": "http://www.isc.ac.uk/fdsnws/event/1/query?starttime={s}&endtime={e}&minlatitude={la0}&maxlatitude={la1}"
           "&minlongitude={lo0}&maxlongitude={lo1}&format=text&limit=20000",
    "EMSC": "https://www.seismicportal.eu/fdsnws/event/1/query?starttime={s}&endtime={e}&minlat={la0}&maxlat={la1}"
            "&minlon={lo0}&maxlon={lo1}&format=text&limit=20000",
    "USGS": "https://earthquake.usgs.gov/fdsnws/event/1/query?starttime={s}&endtime={e}&minlatitude={la0}"
            "&maxlatitude={la1}&minlongitude={lo0}&maxlongitude={lo1}&format=text&limit=20000",
}


def fetch_reference(cfg, name, start, end, box, log=None) -> pd.DataFrame:
    f = path(cfg, "reference") / f"{name}_{start}_{end}_{'_'.join(f'{b:g}' for b in box)}.txt"
    if not f.exists():
        url = SERVICES[name].format(s=start, e=end, la0=box[0], la1=box[1], lo0=box[2], lo1=box[3])
        try:
            txt = urllib.request.urlopen(url, timeout=120).read().decode()
        except Exception as e:  # 204 No Content raises in some versions
            txt = ""
            if log:
                log.warning("%s: %s", name, e)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(txt)
    txt = f.read_text()
    if not txt.strip():
        return pd.DataFrame(columns=["ref", "ref_id", "time", "latitude", "longitude", "depth", "author", "magtype", "mag"])
    df = pd.read_csv(io.StringIO(txt.lstrip("#")), sep="|")
    df.columns = [c.strip() for c in df.columns]
    out = pd.DataFrame(dict(ref=name, ref_id=df["EventID"].astype(str),
                            time=to_epoch(df["Time"].astype(str).str.replace("Z", "", regex=False) + "Z"),
                            latitude=df["Latitude"], longitude=df["Longitude"],
                            depth=pd.to_numeric(df["Depth/km"], errors="coerce"),
                            author=df["Author"].astype(str), magtype=df["MagType"].astype(str),
                            mag=pd.to_numeric(df["Magnitude"], errors="coerce")))
    return out


def footprint(stations, buffer_deg=0.3):
    from shapely.geometry import MultiPoint

    return MultiPoint(list(zip(stations.lon, stations.lat))).convex_hull.buffer(buffer_deg)


def match_reference(cat, ref, dt_max=10.0, dist_max=100.0):
    rows = []
    t = cat.time.to_numpy()
    for r in ref.itertuples():
        i = np.searchsorted(t, r.time)
        cands = [k for k in range(max(i - 5, 0), min(i + 5, len(t))) if abs(t[k] - r.time) <= dt_max]
        best, bd = None, np.inf
        for k in cands:
            d = 111.2 * np.hypot(cat.latitude.iloc[k] - r.latitude,
                                 (cat.longitude.iloc[k] - r.longitude) * np.cos(np.radians(r.latitude)))
            if d <= dist_max and d < bd:
                best, bd = k, d
        row = r._asdict()
        if best is None:
            # looser search, for diagnosing misses
            loose = [k for k in range(max(i - 20, 0), min(i + 20, len(t))) if abs(t[k] - r.time) <= 60]
            row.update(matched=False, note=f"{len(loose)} of our events within ±60 s")
        else:
            e = cat.iloc[best]
            row.update(matched=True, event_id=e.event_id, dt_s=e.time - r.time, dist_km=bd,
                       our_depth=e.depth_km, ddepth_km=(e.depth_km - r.depth) if np.isfinite(r.depth) else np.nan,
                       our_ml=e.get("ml", np.nan), our_quality=e.quality, our_nsta=e.n_sta,
                       our_erh=e.erh_km, our_erz=e.erz_km, note="")
        rows.append(row)
    return pd.DataFrame(rows)


def main(argv=None):
    ap = base_parser(__doc__)
    ap.add_argument("--tag", required=True)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    log = get_logger("validate")
    d = path(cfg, "catalogs") / args.tag
    cat = pd.read_csv(d / "events.csv").sort_values("time").reset_index(drop=True)
    st = select_stations(cfg, args.stations or cfg["pilot"]["subarray"], args.start, args.end)
    fp = footprint(st)
    box = (round(st.lat.min() - 2, 1), round(st.lat.max() + 2, 1), round(st.lon.min() - 3, 1), round(st.lon.max() + 3, 1))
    refs = pd.concat([fetch_reference(cfg, n, args.start, args.end, box, log) for n in SERVICES], ignore_index=True)
    from shapely import points, contains

    refs["inside"] = contains(fp, points(refs.longitude.to_numpy(), refs.latitude.to_numpy()))
    m = match_reference(cat, refs)
    m["origin_time"] = [str(UTCDateTime(x)) for x in m.time]
    m.to_csv(path(cfg, "results") / f"validation_{args.tag}.csv", index=False)
    lines = []
    for name, g in m.groupby("ref"):
        gi = g[g.inside]
        mm = gi[gi.matched]
        lines.append(dict(reference=name, n_ref=len(g), n_inside=len(gi), n_inside_matched=len(mm),
                          match_rate_inside=(len(mm) / len(gi)) if len(gi) else np.nan,
                          n_outside_matched=int(g[~g.inside].matched.sum()),
                          median_dist_km=mm.dist_km.median() if len(mm) else np.nan,
                          median_abs_dt_s=mm.dt_s.abs().median() if len(mm) else np.nan,
                          median_ddepth_km=mm.ddepth_km.median() if len(mm) else np.nan))
    summ = pd.DataFrame(lines)
    cols = ["ref", "ref_id", "origin_time", "latitude", "longitude", "depth", "author", "magtype", "mag",
            "inside", "matched", "dist_km", "dt_s", "our_depth", "our_ml", "our_quality", "our_nsta", "note"]
    md = ("### Reference-bulletin match\n\n" + summ.to_markdown(index=False, floatfmt=".2f") +
          "\n\n#### Every reference event\n\n" +
          m[[c for c in cols if c in m]].to_markdown(index=False, floatfmt=".2f") + "\n")
    (path(cfg, "results") / f"validation_{args.tag}_refs.md").write_text(md)
    log.info("\n%s", summ.to_string(index=False))


if __name__ == "__main__":
    main()
