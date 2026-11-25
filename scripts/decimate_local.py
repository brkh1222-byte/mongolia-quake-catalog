"""Make the 20 Hz copies (as pass 1 does) from local pilot day files, for
testing template matching on the Mac.
  python scripts/decimate_local.py --start 2013-01-01 --end 2013-01-03 --stations HD
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from common import base_parser, day_path, days, load_config, select_stations
from stream_run import decimated_path, write_decimated

a = base_parser(__doc__).parse_args()
cfg = load_config(a.config)
n = 0
for t in days(a.start, a.end):
    for sta in select_stations(cfg, a.stations or "HD", a.start, a.end).station:
        f = day_path(cfg, "XL", sta, t)
        if f.exists() and not decimated_path(cfg, sta, t).exists():
            write_decimated(cfg, f, sta, t); n += 1
print("wrote", n, "20 Hz station-days")
