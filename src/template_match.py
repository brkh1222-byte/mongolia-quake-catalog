"""T6.1 (pass 3): template matching with EQcorrscan (Chamberlain et al. 2018),
using the fast_matched_filter CUDA backend (Beaucé et al. 2018) when it is
available.

Idea: a well-recorded earthquake is a template, cut on several stations and
components. Sliding it over continuous data and summing the normalised
cross-correlation over channels finds near-copies too small for the ML picker.
A detection is declared when the network-summed CC exceeds `threshold` times
the median absolute deviation (MAD) of that day's CC sum.

Data: the 20 Hz decimated day files written by pass 1 (stream_run.py
--decimate), band-passed here at 2–8 Hz.
Templates: quality-A events with >= --min-stations stations with picks. Each
template is 4 s long with 0.5 s before the pick: P on the vertical, S on both
horizontals.

Outputs (data/catalogs/{tag}/templates/):
  tribe.tgz               EQcorrscan Tribe (templates)
  detections/{day}.csv    template, detect_time, detect_val, threshold, no_chans
  progress ledger: done_days.txt (resumable)

Linux only in practice: EQcorrscan needs FFTW, and FMF needs nvcc. Both are
built by scripts/cloud_bootstrap.sh. Mac: not tested (no compiler; see
notes/STATUS.md).

Example
  python src/template_match.py --tag full_HD --stations HD --start 2012-06-10 --end 2014-04-11 --device cuda
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import time

import numpy as np
import pandas as pd
from obspy import Stream, UTCDateTime, read
from obspy.core.event import (Catalog, Event, Origin, Pick, WaveformStreamID, ResourceIdentifier)

from common import base_parser, days, get_logger, load_config, path, select_stations


def to_obspy_catalog(cat: pd.DataFrame, picks: pd.DataFrame, net="XL") -> Catalog:
    out = Catalog()
    for ev in cat.itertuples():
        e = Event(resource_id=ResourceIdentifier(ev.event_id))
        e.origins.append(Origin(time=UTCDateTime(ev.time), latitude=ev.latitude,
                                longitude=ev.longitude, depth=ev.depth_km * 1000))
        for p in picks[picks.event_id == ev.event_id].itertuples():
            cha = "HHZ" if p.phase == "P" else "HHN"
            e.picks.append(Pick(time=UTCDateTime(float(p.time)), phase_hint=p.phase,
                                waveform_id=WaveformStreamID(net, p.station, "", cha)))
        out.append(e)
    return out


def load_day20(cfg, stations, t) -> Stream:
    from stream_run import decimated_path

    st = Stream()
    for sta in stations:
        f = decimated_path(cfg, sta, t)
        if f.exists():
            st += read(str(f))
    for tr in st:
        tr.stats.location = ""
    st.merge(method=1, fill_value=0)
    return st


def build_tribe(cfg, cat, picks, stations, log, min_stations=6, length=4.0, prepick=0.5):
    from eqcorrscan import Tribe

    sel = cat[(cat.quality == "A") & (cat.n_sta >= min_stations)].copy()
    sel["day"] = [str(UTCDateTime(t).date) for t in sel.time]
    tribe = Tribe()
    for day, g in sel.groupby("day"):
        st = load_day20(cfg, stations, UTCDateTime(day))
        if not len(st):
            continue
        ocat = to_obspy_catalog(g, picks)
        try:
            t = Tribe().construct(method="from_meta_file", meta_file=ocat, st=st, lowcut=2.0, highcut=8.0,
                                  samp_rate=20.0, filt_order=4, length=length, prepick=prepick, swin="all",
                                  all_horiz=True, process_len=86400, min_snr=4.0, parallel=False)
            for tmpl in t:
                if len({tr.stats.station for tr in tmpl.st}) >= min_stations:
                    tribe += tmpl
        except Exception as e:
            log.warning("templates for %s failed: %s", day, e)
    log.info("built %d templates from %d candidate events", len(tribe), len(sel))
    return tribe


def main(argv=None):
    ap = base_parser(__doc__)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--threshold", type=float, default=9.0, help="MAD multiple")
    ap.add_argument("--min-stations", type=int, default=6)
    ap.add_argument("--max-templates", type=int, default=0)
    ap.add_argument("--backend", default="auto", choices=["auto", "fftw", "fmf"],
                    help="auto: fast_matched_filter on cuda, EQcorrscan FFTW otherwise")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    log = get_logger("template", path(cfg, "logs") / "template_match.log")
    from eqcorrscan import Tribe

    d = path(cfg, "catalogs") / args.tag
    td = d / "templates"
    (td / "detections").mkdir(parents=True, exist_ok=True)
    stations = select_stations(cfg, args.stations or "all", args.start, args.end).station.tolist()
    if (td / "tribe.tgz").exists():
        tribe = Tribe().read(str(td / "tribe.tgz"))
    else:
        cat = pd.read_csv(d / "events_relocated.csv" if (d / "events_relocated.csv").exists() else d / "events.csv")
        picks = pd.read_parquet(d / "picks.parquet")
        tribe = build_tribe(cfg, cat, picks, stations, log, args.min_stations)
        tribe.write(str(td / "tribe.tgz"))
    if args.max_templates:
        tribe.templates = tribe.templates[:args.max_templates]
    device = args.device or cfg["picking"]["device"]
    if args.backend == "fmf" or (args.backend == "auto" and device == "cuda"):
        xcorr = dict(xcorr_func="fmf", arch="gpu" if device == "cuda" else "cpu")
    else:
        xcorr = dict(xcorr_func="fftw")
    done_f = td / "done_days.txt"
    done = set(done_f.read_text().split()) if done_f.exists() else set()
    for t in days(args.start, args.end):
        day = str(t.date)
        if day in done:
            continue
        st = load_day20(cfg, stations, t)
        if len(st) < 3 * args.min_stations:
            done_f.open("a").write(day + "\n")
            continue
        tic = time.time()
        try:
            party = tribe.detect(stream=st, threshold=args.threshold, threshold_type="MAD", trig_int=2.0,
                                 plot=False, daylong=True, ignore_bad_data=True, return_stream=False,
                                 parallel_process=False, **xcorr)
            party.decluster(trig_int=2.0)
            rows = [dict(template=f.template.name, detect_time=str(det.detect_time), detect_val=det.detect_val,
                         threshold=det.threshold, no_chans=det.no_chans)
                    for f in party for det in f]
        except Exception as e:
            log.error("%s detect failed: %s", day, e)
            continue
        pd.DataFrame(rows).to_csv(td / "detections" / f"{day}.csv", index=False)
        done_f.open("a").write(day + "\n")
        log.info("%s: %d detections, %d templates, %.0f s", day, len(rows), len(tribe), time.time() - tic)


if __name__ == "__main__":
    main()
