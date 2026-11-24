"""Associate and locate the public QuakeScope picks with exactly our PyOcto and
locator settings, for a like-for-like event-level comparison.
  python scripts/associate_quakescope.py --start 2013-01-01 --end 2013-02-01 --tag pilot_2013-01_qs
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pandas as pd
from obspy import UTCDateTime
from associate import associate
from common import base_parser, get_logger, load_config, path, select_stations
from compare_quakescope import load_quakescope
from locate import locate_catalog, quality_flags, remove_split_duplicates

ap = base_parser(__doc__); ap.add_argument("--tag", required=True); a = ap.parse_args()
cfg = load_config(a.config); log = get_logger("qs_assoc")
st = select_stations(cfg, a.stations or "HD", a.start, a.end)
qs = load_quakescope(cfg, "XL", a.start, a.end)
qs = qs[qs.station.isin(st.station)]
p = pd.DataFrame(dict(network="XL", station=qs.station.values, phase=qs.phase.values,
                      time=[str(UTCDateTime(t)) for t in qs.t], prob=qs.prob.values))
ev, asg = associate(cfg, p, st, log)
if "prob" not in asg:
    asg["prob"] = 1.0
cat, picks = locate_catalog(cfg, ev, asg, st, log)
cat = quality_flags(cat, cfg); cat, dups = remove_split_duplicates(cat)
d = path(cfg, "catalogs") / a.tag; d.mkdir(parents=True, exist_ok=True)
cat.to_csv(d / "events.csv", index=False); picks[picks.event_id.isin(cat.event_id)].to_parquet(d / "picks.parquet", index=False)
log.info("QuakeScope picks %d -> %d events (%d split duplicates removed); quality %s", len(p), len(cat), len(dups),
         cat.quality.value_counts().to_dict())
