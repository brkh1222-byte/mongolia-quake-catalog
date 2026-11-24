"""T0.2: fetch XL station metadata and draw the station map.

Writes
  data/meta/stations.csv            one row per station (epochs merged)
  data/meta/stationxml/XL.xml       full response-level StationXML (HH channels)
  results/fig_stations.png          map of the three subarrays

Usage:  python src/stations.py [--config extra.yaml] [--no-map]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
from obspy import UTCDateTime, read_inventory
from obspy.clients.fdsn import Client

from common import base_parser, get_logger, load_config, path

SUBARRAY_COLORS = {"HD": "#c0392b", "HV": "#2471a3", "AT": "#239b56"}
REGIONAL = [("IU", "ULN"), ("II", "TLY"), ("IC", "HIA")]


def fetch_inventory(cfg, log):
    out = path(cfg, "stationxml") / "XL.xml"
    if out.exists():
        log.info("using cached %s", out)
        return read_inventory(str(out))
    out.parent.mkdir(parents=True, exist_ok=True)
    client = Client(cfg["fdsn"]["base_url"])
    inv = client.get_stations(network=cfg["fdsn"]["network"], station="*", channel="HH?",
                              starttime=UTCDateTime(cfg["time"]["start"]),
                              endtime=UTCDateTime(cfg["time"]["end"]), level="response")
    inv.write(str(out), format="STATIONXML")
    log.info("wrote %s", out)
    return inv


def inventory_table(inv, cfg) -> pd.DataFrame:
    """One row per station; epochs of the same code are merged (min start, max end)
    and the most recent coordinates are kept, with the number of epochs and the
    maximum coordinate shift between epochs recorded."""
    rows = []
    for net in inv:
        for sta in net:
            rows.append(dict(network=net.code, station=sta.code, lat=sta.latitude,
                             lon=sta.longitude, elev=sta.elevation,
                             start=sta.start_date.datetime,
                             end=(sta.end_date or UTCDateTime(cfg["time"]["end"])).datetime,
                             n_channels=len(sta.channels)))
    df = pd.DataFrame(rows).sort_values(["station", "start"])
    out = []
    for code, g in df.groupby("station"):
        last = g.iloc[-1]
        shift_km = 111.2 * max(g.lat.max() - g.lat.min(),
                               (g.lon.max() - g.lon.min()) * 0.68)
        out.append(dict(network=last.network, station=code, lat=last.lat, lon=last.lon,
                        elev=last.elev, start=g.start.min(), end=g.end.max(),
                        n_epochs=len(g), max_epoch_shift_km=round(shift_km, 3),
                        subarray=code[:2]))
    return pd.DataFrame(out)


def draw_map(df: pd.DataFrame, outfile: Path, log):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature

        fig = plt.figure(figsize=(9, 6.5))
        ax = plt.axes(projection=ccrs.LambertConformal(central_longitude=100, central_latitude=47))
        ax.set_extent([87, 112, 41, 53], crs=ccrs.PlateCarree())
        try:
            ax.add_feature(cfeature.BORDERS.with_scale("50m"), linewidth=0.6, edgecolor="0.3")
            ax.add_feature(cfeature.LAKES.with_scale("50m"), facecolor="#d6eaf8", edgecolor="0.5", linewidth=0.3)
            ax.add_feature(cfeature.COASTLINE.with_scale("50m"), linewidth=0.4)
        except Exception as e:  # offline: Natural Earth not cached
            log.warning("cartopy features unavailable (%s); map without borders", e)
        gl = ax.gridlines(draw_labels=True, linewidth=0.3, color="0.6")
        gl.top_labels = gl.right_labels = False
        gl.x_inline = gl.y_inline = False
        kw = dict(transform=ccrs.PlateCarree())
    except ImportError:
        fig, ax = plt.subplots(figsize=(9, 6.5))
        ax.set_xlim(87, 112)
        ax.set_ylim(41, 53)
        ax.set_xlabel("Longitude (°E)")
        ax.set_ylabel("Latitude (°N)")
        kw = {}
    names = {"HD": "Hangay (HD, 2012–2014)", "HV": "Khövsgöl (HV, 2014–2016)",
             "AT": "Gobi-Altai (AT, 2014–2016)"}
    for sub, g in df.groupby("subarray"):
        ax.scatter(g.lon, g.lat, s=22, marker="^", color=SUBARRAY_COLORS.get(sub, "k"),
                   edgecolor="k", linewidth=0.4, label=f"{names.get(sub, sub)}: {len(g)}", zorder=5, **kw)
    ax.scatter([106.92], [47.92], s=40, marker="*", color="k", zorder=6, **kw)
    ax.text(107.2, 47.9, "Ulaanbaatar", fontsize=8, zorder=6, **kw)
    ax.legend(loc="lower left", fontsize=8, title=f"XL stations ({len(df)} codes)", title_fontsize=8)
    ax.set_title("Central Mongolia Seismic Experiment (FDSN XL, doi:10.7914/SN/XL_2012)", fontsize=10)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outfile, dpi=200, bbox_inches="tight")
    log.info("wrote %s", outfile)


def main(argv=None):
    ap = base_parser(__doc__)
    ap.add_argument("--no-map", action="store_true")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    log = get_logger("stations")
    inv = fetch_inventory(cfg, log)
    df = inventory_table(inv, cfg)
    out = path(cfg, "meta") / "stations.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    log.info("%d stations: %s", len(df), df.subarray.value_counts().to_dict())
    if not args.no_map:
        draw_map(df, path(cfg, "results") / "fig_stations.png", log)
    return df


if __name__ == "__main__":
    main()
