"""T1.1: resumable, parallel download of XL day files with ObsPy MassDownloader.

Day files are written to  data/mseed/{net}.{sta}/{year}/{jday:03d}.mseed
StationXML (response level) to  data/meta/stationxml/{net}.{sta}.xml

Resumability: MassDownloader skips every chunk whose target file already exists,
so re-running the same command only fetches what is missing. Station-days that
the data centre reports as empty are remembered in data/logs/nodata.csv so that
reruns do not ask again (pass --retry-nodata to ignore that list).

An availability log (seconds of data per channel and station-day) is appended
to data/logs/availability.csv after each run (see src/availability.py).

Examples
  python src/download.py --start 2013-05-01 --end 2013-05-04 --stations HD01,HD02
  python src/download.py --start 2012-06-01 --end 2014-05-01 --stations HD      # H100 box
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import logging

import pandas as pd
from obspy import UTCDateTime, read
from obspy.clients.fdsn import Client
from obspy.clients.fdsn.mass_downloader import MassDownloader, Restrictions, GlobalDomain

from common import base_parser, day_path, days, get_logger, load_config, path, select_stations


def make_storage(cfg):
    """MassDownloader storage callbacks that map chunks onto our day-file layout."""
    stationxml_dir = path(cfg, "stationxml")

    def mseed_storage(network, station, location, channel, starttime, endtime):
        # One file per station-day holding all three components. MassDownloader
        # downloads per channel; we write to a per-channel temp name and merge
        # into the day file in `merge_day_files` below.
        p = day_path(cfg, network, station, starttime)
        return str(p.with_name(f"{p.stem}.{location}.{channel}.part.mseed"))

    def stationxml_storage(network, station, channels, starttime, endtime):
        return str(stationxml_dir / f"{network}.{station}.xml")

    return mseed_storage, stationxml_storage


def merge_day_files(cfg, net, sta, t, log) -> bool:
    """Merge per-channel .part files into the final day file. Returns True if a
    day file exists afterwards."""
    final = day_path(cfg, net, sta, t)
    parts = sorted(final.parent.glob(f"{final.stem}.*.part.mseed")) if final.parent.exists() else []
    if final.exists() and not parts:
        return True
    if not parts:
        return False
    st = read(str(parts[0]))
    for p in parts[1:]:
        st += read(str(p))
    if final.exists():
        st += read(str(final))
    st.merge(method=1, fill_value=None)
    st.trim(UTCDateTime(t), UTCDateTime(t) + 86400, nearest_sample=False)
    st = st.split()  # keep gaps as separate traces, never fill with zeros
    tmp = final.with_suffix(".tmp")
    st.write(str(tmp), format="MSEED")
    tmp.replace(final)  # atomic: a killed run never leaves a half-written day file
    for p in parts:
        p.unlink()
    return True


def channels_complete(cfg, net, sta, t) -> bool:
    """A day is complete if the merged day file exists and no .part files remain."""
    final = day_path(cfg, net, sta, t)
    return final.exists() and not list(final.parent.glob(f"{final.stem}.*.part.mseed"))


def availability_rows(cfg, net, sta, t):
    f = day_path(cfg, net, sta, t)
    if not f.exists():
        return []
    st = read(str(f), headonly=True)
    rows = {}
    for tr in st:
        rows.setdefault(tr.stats.channel, 0.0)
        rows[tr.stats.channel] += tr.stats.npts / tr.stats.sampling_rate
    return [dict(network=net, station=sta, day=str(t.date), channel=c, seconds=round(s, 1),
                 bytes=f.stat().st_size) for c, s in rows.items()]


def load_nodata(cfg) -> set:
    f = path(cfg, "logs") / "nodata.csv"
    if not f.exists():
        return set()
    df = pd.read_csv(f)
    return set(zip(df.station, df.day))


def run(cfg, stations: pd.DataFrame, start, end, log, retry_nodata=False, dry_run=False):
    net = cfg["fdsn"]["network"]
    nodata = set() if retry_nodata else load_nodata(cfg)
    todo = []
    for _, s in stations.iterrows():
        for t in days(max(UTCDateTime(start), UTCDateTime(s.start.date())),
                      min(UTCDateTime(end), UTCDateTime(s.end) + 1)):
            if channels_complete(cfg, net, s.station, t) or (s.station, str(t.date)) in nodata:
                continue
            todo.append((s.station, t))
    log.info("%d station-days still to fetch", len(todo))
    if dry_run or not todo:
        return todo

    # One MassDownloader call per station keeps requests small and lets a crash
    # lose at most one station's in-flight chunks.
    mseed_storage, sxml_storage = make_storage(cfg)
    client = Client(cfg["fdsn"]["base_url"], timeout=240)
    mdl = MassDownloader(providers=[client], configure_logging=False)
    logging.getLogger("obspy.clients.fdsn.mass_downloader").setLevel(logging.WARNING)
    for sta in sorted({s for s, _ in todo}):
        tdays = sorted(t for s, t in todo if s == sta)
        restr = Restrictions(
            starttime=tdays[0], endtime=tdays[-1] + 86400, chunklength_in_sec=86400,
            network=net, station=sta, location=cfg["fdsn"]["location"], channel="HH?",
            reject_channels_with_gaps=False, minimum_length=cfg["download"]["minimum_length"],
            minimum_interstation_distance_in_m=0, sanitize=False,
            channel_priorities=["HH[ZNE12]"], location_priorities=["", "00", "10", "*"])
        for attempt in range(cfg["download"]["retries"]):
            try:
                mdl.download(GlobalDomain(), restr, mseed_storage=mseed_storage,
                             stationxml_storage=sxml_storage,
                             threads_per_client=cfg["download"]["parallel_requests"],
                             download_chunk_size_in_mb=50, print_report=False)
                break
            except Exception as e:  # network hiccup: retry the whole station
                log.warning("%s attempt %d failed: %s", sta, attempt + 1, e)
        new_nodata, avail = [], []
        for t in tdays:
            if merge_day_files(cfg, net, sta, t, log):
                avail += availability_rows(cfg, net, sta, t)
            else:
                new_nodata.append(dict(station=sta, day=str(t.date)))
        _append_csv(path(cfg, "logs") / "availability.csv", avail)
        _append_csv(path(cfg, "logs") / "nodata.csv", new_nodata)
        log.info("%s: %d days with data, %d without", sta, len(tdays) - len(new_nodata), len(new_nodata))
    return todo


def _append_csv(f: Path, rows: list[dict]):
    if not rows:
        return
    f.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(f, mode="a", header=not f.exists(), index=False)


def main(argv=None):
    ap = base_parser(__doc__)
    ap.add_argument("--retry-nodata", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    log = get_logger("download", path(cfg, "logs") / "download.log")
    start = args.start or cfg["time"]["start"]
    end = args.end or cfg["time"]["end"]
    stations = select_stations(cfg, args.stations or "all", start, end)
    log.info("%d stations selected for %s – %s", len(stations), start, end)
    run(cfg, stations, start, end, log, retry_nodata=args.retry_nodata, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
