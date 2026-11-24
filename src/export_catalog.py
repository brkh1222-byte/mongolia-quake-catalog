"""T7.1: export a catalog as CSV + QuakeML, plus a Zenodo-ready folder.

Input : data/catalogs/{tag}/events_relocated.csv (or events.csv), picks.parquet
Output: release/{tag}/
          catalog.csv          one row per event (absolute + relocated coordinates,
                               errors, quality, ML, blast flag if present)
          catalog.xml          QuakeML 1.2 with origins, arrivals, picks and magnitudes
          picks.csv            associated ensemble picks
          README.md            column definitions, method summary, citation, licence (CC BY 4.0)

Example
  python src/export_catalog.py --tag full_HD
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd
from obspy import UTCDateTime
from obspy.core.event import (Arrival, Catalog, CreationInfo, Event, Magnitude, Origin, OriginQuality,
                              OriginUncertainty, Pick, QuantityError, ResourceIdentifier, WaveformStreamID)

from common import REPO, base_parser, get_logger, load_config, path

COLUMNS = {
    "event_id": "unique id (mqc + origin time)",
    "origin_time": "UTC origin time (relocated if available)",
    "latitude": "deg N (relocated if available, else absolute)",
    "longitude": "deg E",
    "depth_km": "km below sea level",
    "erh_km": "1-sigma horizontal error (km; GrowClust bootstrap if relocated, else absolute)",
    "erz_km": "1-sigma depth error (km)",
    "rms_s": "rms travel-time residual of the absolute location (s)",
    "n_picks": "number of associated picks", "n_sta": "number of stations", "gap_deg": "azimuthal gap",
    "dmin_km": "distance to the nearest station", "quality": "A–D location quality class (see paper)",
    "ml": "local magnitude (Wood–Anderson, Hutton & Boore 1987 distance term, station-corrected if available)",
    "ml_err": "magnitude uncertainty (scaled MAD / sqrt(n))", "relocated": "True if relocated by GrowClust",
    "cluster_id": "GrowClust cluster id", "abs_latitude": "absolute (single-event) latitude",
    "abs_longitude": "absolute longitude", "abs_depth_km": "absolute depth", "blast_flag": "possible quarry blast",
}


def build_table(cat: pd.DataFrame) -> pd.DataFrame:
    out = cat.copy()
    out["abs_latitude"], out["abs_longitude"], out["abs_depth_km"] = cat.latitude, cat.longitude, cat.depth_km
    if "relocated" in cat:
        r = cat.relocated.fillna(False).astype(bool)
        out.loc[r, "latitude"] = cat.loc[r, "latR"]
        out.loc[r, "longitude"] = cat.loc[r, "lonR"]
        out.loc[r, "depth_km"] = cat.loc[r, "depR"]
        out.loc[r, "erh_km"] = cat.loc[r, "eh"]
        out.loc[r, "erz_km"] = cat.loc[r, "ez"]
        out["cluster_id"] = cat.get("cID")
    if "ml_corr" in cat:
        out["ml"] = cat.ml_corr.where(cat.ml_corr.notna(), cat.get("ml"))
    return out[[c for c in COLUMNS if c in out]]


def to_quakeml(tab: pd.DataFrame, picks: pd.DataFrame, net="XL") -> Catalog:
    ci = CreationInfo(agency_id="mqc", author="mongolia-quake-catalog", creation_time=UTCDateTime())
    catq = Catalog(creation_info=ci, description="Open ML earthquake catalogue, FDSN network XL")
    pg = picks.groupby("event_id") if len(picks) else {}
    for ev in tab.itertuples():
        rid = f"smi:mqc/{ev.event_id}"
        o = Origin(resource_id=ResourceIdentifier(rid + "/origin"), time=UTCDateTime(ev.origin_time),
                   latitude=ev.latitude, longitude=ev.longitude, depth=ev.depth_km * 1000,
                   depth_errors=QuantityError(uncertainty=float(ev.erz_km) * 1000 if np.isfinite(ev.erz_km) else None),
                   origin_uncertainty=OriginUncertainty(horizontal_uncertainty=float(ev.erh_km) * 1000
                                                        if np.isfinite(ev.erh_km) else None),
                   quality=OriginQuality(standard_error=float(ev.rms_s), azimuthal_gap=float(ev.gap_deg),
                                         used_station_count=int(ev.n_sta), associated_phase_count=int(ev.n_picks),
                                         minimum_distance=float(ev.dmin_km) / 111.19),
                   evaluation_mode="automatic", creation_info=ci)
        e = Event(resource_id=ResourceIdentifier(rid), event_type="earthquake", creation_info=ci)
        if getattr(ev, "blast_flag", False):
            e.event_type = "not reported"
            e.event_type_certainty = "suspected"
        if len(picks) and ev.event_id in pg.groups:
            for k, p in enumerate(pg.get_group(ev.event_id).itertuples()):
                pid = ResourceIdentifier(f"{rid}/pick/{k}")
                cha = "HHZ" if p.phase == "P" else "HHN"
                e.picks.append(Pick(resource_id=pid, time=UTCDateTime(float(p.time)), phase_hint=p.phase,
                                    waveform_id=WaveformStreamID(net, p.station, "", cha),
                                    evaluation_mode="automatic", method_id=ResourceIdentifier("smi:mqc/seisbench-ensemble")))
                o.arrivals.append(Arrival(pick_id=pid, phase=p.phase,
                                          time_residual=float(p.residual_s) if hasattr(p, "residual_s") else None,
                                          distance=float(p.dist_km) / 111.19 if hasattr(p, "dist_km") else None))
        e.origins.append(o)
        e.preferred_origin_id = o.resource_id
        if np.isfinite(getattr(ev, "ml", np.nan)):
            m = Magnitude(resource_id=ResourceIdentifier(rid + "/ml"), mag=float(ev.ml), magnitude_type="ML",
                          mag_errors=QuantityError(uncertainty=float(ev.ml_err) if np.isfinite(ev.ml_err) else None),
                          origin_id=o.resource_id)
            e.magnitudes.append(m)
            e.preferred_magnitude_id = m.resource_id
        catq.append(e)
    return catq


def main(argv=None):
    ap = base_parser(__doc__)
    ap.add_argument("--tag", required=True)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    log = get_logger("export")
    d = path(cfg, "catalogs") / args.tag
    f = d / "events_relocated.csv" if (d / "events_relocated.csv").exists() else d / "events.csv"
    cat = pd.read_csv(f)
    an = path(cfg, "results") / args.tag / "events_analyzed.csv"
    if an.exists():
        cat = cat.merge(pd.read_csv(an)[["event_id", "blast_flag"]], on="event_id", how="left")
    picks = pd.read_parquet(d / "picks.parquet")
    tab = build_table(cat)
    out = REPO / "release" / args.tag
    out.mkdir(parents=True, exist_ok=True)
    tab.to_csv(out / "catalog.csv", index=False, float_format="%.5g")
    pk = picks[picks.event_id.isin(tab.event_id)]
    pk.assign(time_utc=[str(UTCDateTime(float(t))) for t in pk.time]).to_csv(out / "picks.csv", index=False)
    to_quakeml(tab, pk).write(str(out / "catalog.xml"), format="QUAKEML")
    lines = [f"# mongolia-quake-catalog release: {args.tag}", "",
             "Automatic machine-learning earthquake catalogue from FDSN network XL (Central Mongolia Seismic Experiment, "
             "doi:10.7914/SN/XL_2012). Method: see the accompanying paper and https://github.com/brkh1222-byte/mongolia-quake-catalog.",
             "", "Licence: CC BY 4.0. Please cite the paper, this data release, and the XL network DOI.", "",
             "## catalog.csv columns", ""] + [f"- `{k}`: {v}" for k, v in COLUMNS.items() if k in tab] + \
            ["", f"Events: {len(tab)}. Picks: {len(pk)}."]
    (out / "README.md").write_text("\n".join(lines) + "\n")
    log.info("wrote %s (%d events)", out, len(tab))


if __name__ == "__main__":
    main()
