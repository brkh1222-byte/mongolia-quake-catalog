"""T1.2: data-availability plot (station x time).

EarthScope retired its fdsnws/availability service, so availability is built
from what we have:
  1. station epochs from the StationXML metadata (grey bars: the station was
     installed);
  2. where they exist, the actual seconds of data per station-day: from
     data/logs/availability.csv (download.py), the streaming ledger
     (data/ledger.sqlite: done / nodata), or the QuakeScope pick counts
     (a proxy: a station-day with picks had data).
Output: results/fig_availability.png

Example
  python src/availability.py [--quakescope] [--mark 2013-01-01,2013-02-01]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sqlite3

import numpy as np
import pandas as pd

from common import base_parser, get_logger, load_config, path

COL = {"HD": "#c0392b", "HV": "#2471a3", "AT": "#239b56"}


def main(argv=None):
    ap = base_parser(__doc__)
    ap.add_argument("--mark", default="2013-01-01,2013-02-01", help="shade a window (pilot month)")
    ap.add_argument("--quakescope", action="store_true", help="use QuakeScope pick counts as a data proxy")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    log = get_logger("availability")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    st = pd.read_csv(path(cfg, "meta") / "stations.csv", parse_dates=["start", "end"])
    st = st.sort_values(["subarray", "station"], key=lambda s: s.map({"HD": 0, "HV": 1, "AT": 2}) if s.name == "subarray" else s)
    st = st.reset_index(drop=True)
    y = {s: i for i, s in enumerate(st.station)}
    fig, ax = plt.subplots(figsize=(10, 12))
    for r in st.itertuples():
        ax.barh(y[r.station], (r.end - r.start).days + 1, left=r.start, height=0.8, color=COL[r.subarray],
                alpha=0.25, lw=0)
    # actual data, where known
    days = []
    f = path(cfg, "logs") / "availability.csv"
    if f.exists():
        a = pd.read_csv(f)
        a = a[a.channel.str.endswith("Z")].groupby(["station", "day"]).seconds.sum().reset_index()
        days.append(a.assign(frac=(a.seconds / 86400).clip(0, 1))[["station", "day", "frac"]])
    led = path(cfg, "data") / "ledger.sqlite"
    if led.exists():
        con = sqlite3.connect(str(led))
        l = pd.read_sql("SELECT station, day, status FROM station_day WHERE status IN ('done','nodata')", con)
        days.append(l.assign(frac=np.where(l.status == "done", 1.0, 0.0))[["station", "day", "frac"]])
    nodata = path(cfg, "logs") / "nodata.csv"
    if nodata.exists():
        n = pd.read_csv(nodata)
        days.append(n.assign(frac=0.0)[["station", "day", "frac"]])
    qsdir = path(cfg, "reference") / "quakescope"
    if args.quakescope and qsdir.exists():
        # proxy for the whole deployment: a station-day with >= 5 QuakeScope picks had data
        q = []
        for f in sorted(qsdir.glob("XL_*.parquet")):
            try:
                t = pd.read_parquet(f, columns=["tid", "peak"])
            except Exception:
                continue
            t["station"] = t.tid.str.split(".").str[1]
            t["day"] = t.peak.astype(str).str[:10]
            q.append(t.groupby(["station", "day"]).size().rename("n").reset_index())
        if q:
            q = pd.concat(q)
            q = q[q.n >= 5]
            ax.scatter(pd.to_datetime(q.day), q.station.map(y), s=1, marker="s", c="0.35", lw=0,
                       label="QuakeScope picks (>=5) on that day (data proxy)")
            log.info("QuakeScope proxy: %d station-days with picks", len(q))
            q[["station", "day", "n"]].to_csv(path(cfg, "meta") / "quakescope_station_days.csv", index=False)
    if days:
        dd = pd.concat(days).drop_duplicates(["station", "day"], keep="first")
        dd = dd[dd.station.isin(y)]
        dd["d"] = pd.to_datetime(dd.day)
        ok = dd[dd.frac > 0.5]
        bad = dd[dd.frac <= 0.5]
        ax.scatter(ok.d, ok.station.map(y), s=2, marker="s", c="k", lw=0, label="data downloaded (>50% of day)")
        ax.scatter(bad.d, bad.station.map(y), s=4, marker="x", c="orange", lw=0.6, label="no / partial data")
        log.info("%d station-days with known availability (%d with data)", len(dd), len(ok))
    if args.mark:
        a0, a1 = pd.to_datetime(args.mark.split(","))
        ax.axvspan(a0, a1, color="gold", alpha=0.3, label="pilot month")
    ax.set_yticks(range(len(st)))
    ax.set_yticklabels(st.station, fontsize=4.5)
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    from matplotlib.patches import Patch

    h, l = ax.get_legend_handles_labels()
    h += [Patch(color=c, alpha=0.35) for c in COL.values()]
    l += [f"{sub} station epoch (metadata)" for sub in COL]
    ax.legend(h, l, loc="lower left", fontsize=7)
    ax.set_title("XL data availability: station epochs (metadata) and downloaded station-days", fontsize=10)
    out = path(cfg, "results") / "fig_availability.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    log.info("wrote %s", out)


if __name__ == "__main__":
    main()
