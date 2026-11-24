"""T4.2: relative relocation with GrowClust (Trugman & Shearer 2017).

GrowClust grows clusters hierarchically. It starts from the best-correlated
event pairs, merges events and clusters whose pairs pass the similarity
thresholds (rmin, delmax, rmsmax), and relocates each cluster with an L1-norm
inversion of the cross-correlation differential times. Bootstrap resampling
of the differential times gives relative location errors. Events that join no
cluster keep their absolute locations.

This wrapper:
  1. writes GrowClust inputs from our catalog: the event list in HypoDD
     "phase" header format, the station list, the 1-D velocity model (with
     duplicated depths, so the layer boundary is a step), and the
     xcordata.txt made by src/xcorr.py;
  2. builds the control file from the example .inp shipped with the official
     GrowClust repository (template-driven, so the line layout always matches
     the compiled version), overriding paths and parameters by name;
  3. runs the `growclust` binary and parses out.growclust_cat.

GrowClust is Fortran. It is built by scripts/cloud_bootstrap.sh on the Linux
box (the Mac has no Fortran compiler). Set GROWCLUST_HOME to the cloned repo.

Example
  GROWCLUST_HOME=~/GrowClust python src/relocate.py --tag pilot_2013-01
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import os
import re
import subprocess

import numpy as np
import pandas as pd
from obspy import UTCDateTime

from common import base_parser, get_logger, load_config, path

CAT_COLS = ["yr", "mon", "day", "hr", "mn", "sec", "evid", "latR", "lonR", "depR", "mag", "qID",
            "cID", "nbranch", "qnpair", "qndiffP", "qndiffS", "rmsP", "rmsS", "eh", "ez", "et",
            "latC", "lonC", "depC"]


def write_inputs(cat, stations, cfg, d: Path):
    d.mkdir(parents=True, exist_ok=True)
    evnum = {}
    with open(d / "evlist.txt", "w") as f:
        for k, ev in enumerate(cat.itertuples(), 1):
            t = UTCDateTime(ev.time)
            mag = ev.ml if hasattr(ev, "ml") and np.isfinite(ev.ml) else 0.0
            # HypoDD "phase" header format without the leading '#', as in the GrowClust example:
            # yr mon day hr min sec lat lon dep mag eh ez rms evid. Depths above sea level are set to 0
            # (GrowClust's travel-time table starts at depth 0).
            f.write(f"{t.year:4d} {t.month:2d} {t.day:2d} {t.hour:2d} {t.minute:2d} "
                    f"{t.second + t.microsecond / 1e6:6.3f} {ev.latitude:9.5f} {ev.longitude:10.5f} "
                    f"{max(ev.depth_km, 0.0):7.3f} {mag:6.2f} {min(ev.erh_km, 99):6.3f} {min(ev.erz_km, 99):6.3f} "
                    f"{ev.rms_s:6.3f} {k:9d}\n")
            evnum[ev.event_id] = k
    with open(d / "stlist.txt", "w") as f:
        for s in stations.itertuples():
            f.write(f"{s.station:<6s} {s.lat:9.5f} {s.lon:10.5f} {s.elev:7.1f}\n")
    lay = [dict(L, depth=max(L["depth"], 0.0)) for L in cfg["velocity_model"]["layers"]]
    with open(d / "vzmodel.txt", "w") as f:
        for i, L in enumerate(lay):
            if i > 0:
                prev = lay[i - 1]
                f.write(f"{L['depth']:7.2f} {prev['vp']:5.2f} {prev['vs']:5.2f}\n")
            f.write(f"{L['depth']:7.2f} {L['vp']:5.2f} {L['vs']:5.2f}\n")
        f.write(f"{200.0:7.2f} {lay[-1]['vp']:5.2f} {lay[-1]['vs']:5.2f}\n")
    return evnum


def parse_template(inp: Path):
    """Return list of (comment_block, names, value_line) preserving the file."""
    lines = inp.read_text().splitlines()
    out, last_comment = [], ""
    for ln in lines:
        if ln.strip().startswith("*") or not ln.strip():
            out.append(("raw", ln, None))
            if ln.strip().startswith("*"):
                last_comment = ln
            continue
        names = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", re.sub(r"\(.*?\)", "", last_comment.lstrip("* ")))
        out.append(("val", ln, names))
    return out


def render_control(template, overrides: dict) -> str:
    out, used = [], set()
    for kind, ln, names in template:
        if kind == "raw":
            out.append(ln)
            continue
        toks = ln.split()
        if names and len(names) == len(toks):
            toks = [str(overrides.get(n, t)) for n, t in zip(names, toks)]
            used |= {n for n in names if n in overrides}
        elif names and len(names) == 1 and names[0] in overrides:  # single path value
            toks = [str(overrides[names[0]])]
            used.add(names[0])
        out.append("  ".join(toks))
    missing = set(overrides) - used
    if missing:
        raise RuntimeError(f"GrowClust template has no field(s) {sorted(missing)}; check the .inp format")
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = base_parser(__doc__)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--growclust-home", default=os.environ.get("GROWCLUST_HOME", str(Path.home() / "GrowClust")))
    ap.add_argument("--rmin", type=float, default=0.6)
    ap.add_argument("--delmax", type=float, default=80.0)
    ap.add_argument("--rmsmax", type=float, default=0.2)
    ap.add_argument("--nboot", type=int, default=100)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    log = get_logger("relocate")
    d = path(cfg, "catalogs") / args.tag
    gdir = d / "growclust"
    cat = pd.read_csv(d / "events.csv")
    cat = cat[cat.quality.isin(["A", "B", "C"])].reset_index(drop=True)
    stations = pd.read_csv(path(cfg, "meta") / "stations.csv")
    write_inputs(cat, stations, cfg, gdir)
    xc = d / "xcordata.txt"
    (gdir / "xcordata.txt").write_text(xc.read_text())
    home = Path(args.growclust_home)
    templ = sorted(home.rglob("*.inp"))
    if not templ:
        raise FileNotFoundError(f"no GrowClust example .inp under {home}")
    (gdir / "out").mkdir(exist_ok=True)
    (gdir / "tt").mkdir(exist_ok=True)
    zmax = float(cat.depth_km.max() + 5)
    dmax = 2 * float(111 * max(stations.lat.max() - stations.lat.min(), stations.lon.max() - stations.lon.min()))
    overrides = dict(evlist_fmt=1, fin_evlist="evlist.txt", stlist_fmt=1, fin_stlist="stlist.txt",
                     xcordat_fmt=1, tdif_fmt=12, fin_xcordat="xcordata.txt", fin_vzmdl="vzmodel.txt",
                     fout_vzfine="tt/vzfine.txt", fout_pTT="tt/pTT.txt", fout_sTT="tt/sTT.txt",
                     tt_dep0=0.0, tt_dep1=round(max(zmax, 40.0)), tt_del0=0.0, tt_del1=round(min(dmax, 600)),
                     rmin=args.rmin, delmax=args.delmax, rmsmax=args.rmsmax, nboot=args.nboot,
                     fout_cat="out/out.growclust_cat", fout_clust="out/out.growclust_clust",
                     fout_log="out/out.growclust_log", fout_boot="out/out.growclust_boot")
    tpl = parse_template(templ[0])
    names_present = {n for k, _, ns in tpl if k == "val" for n in (ns or [])}
    overrides = {k: v for k, v in overrides.items() if k in names_present}
    (gdir / "growclust.inp").write_text(render_control(tpl, overrides))
    exe = next((p for p in [home / "SRC" / "growclust", home / "growclust", *home.rglob("growclust")]
                if p.is_file() and os.access(p, os.X_OK)), None)
    if exe is None:
        raise FileNotFoundError("growclust binary not found; run scripts/cloud_bootstrap.sh")
    log.info("running %s", exe)
    r = subprocess.run([str(exe), "growclust.inp"], cwd=gdir, capture_output=True, text=True)
    (gdir / "growclust.stdout").write_text(r.stdout + r.stderr)
    if r.returncode != 0:
        raise RuntimeError(f"GrowClust failed, see {gdir / 'growclust.stdout'}")
    out = pd.read_csv(gdir / "out" / "out.growclust_cat", sep=r"\s+", header=None,
                      names=CAT_COLS, usecols=range(len(CAT_COLS)))
    num2id = dict(zip(range(1, len(cat) + 1), cat.event_id))
    out["event_id"] = out.evid.map(num2id)
    rel = cat.merge(out[["event_id", "latR", "lonR", "depR", "cID", "nbranch", "eh", "ez", "et", "rmsP", "rmsS"]],
                    on="event_id", how="left")
    rel["relocated"] = rel.nbranch.fillna(1) > 1
    rel.to_csv(d / "events_relocated.csv", index=False)
    log.info("%d of %d events relocated in clusters", int(rel.relocated.sum()), len(rel))


if __name__ == "__main__":
    main()
