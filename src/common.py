"""Shared helpers: config loading, paths, logging, station tables.

Every pipeline script imports this module so that paths and parameters come
from one YAML file (config/default.yaml, optionally overridden by a second
file such as config/h100.yaml).
"""
from __future__ import annotations

import argparse
import logging
import os
from copy import deepcopy
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "config" / "default.yaml"


def _merge(a: dict, b: dict) -> dict:
    out = deepcopy(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(extra: str | os.PathLike | None = None) -> dict:
    """Load config/default.yaml and merge an optional override file."""
    with open(DEFAULT_CONFIG) as f:
        cfg = yaml.safe_load(f)
    if extra:
        with open(extra) as f:
            cfg = _merge(cfg, yaml.safe_load(f))
    return cfg


def path(cfg: dict, key: str) -> Path:
    """Resolve cfg['paths'][key] relative to the repository root."""
    p = Path(cfg["paths"][key])
    return p if p.is_absolute() else REPO / p


def base_parser(desc: str) -> argparse.ArgumentParser:
    """Arguments shared by all scripts (TASKS.md: --start/--end/--stations/--device)."""
    ap = argparse.ArgumentParser(description=desc)
    ap.add_argument("--config", default=None, help="override YAML merged over config/default.yaml")
    ap.add_argument("--start", default=None, help="UTC start date, e.g. 2013-05-01")
    ap.add_argument("--end", default=None, help="UTC end date (exclusive), e.g. 2013-06-01")
    ap.add_argument("--stations", default=None,
                    help="comma-separated station codes, a prefix such as HD, or 'all'")
    ap.add_argument("--device", default=None, choices=["cpu", "cuda", "mps"])
    return ap


def get_logger(name: str, logfile: Path | None = None) -> logging.Logger:
    log = logging.getLogger(name)
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    h = logging.StreamHandler()
    h.setFormatter(fmt)
    log.addHandler(h)
    if logfile is not None:
        logfile.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(logfile)
        fh.setFormatter(fmt)
        log.addHandler(fh)
    return log


def load_stations(cfg: dict):
    """Return the station table written by src/stations.py."""
    import pandas as pd

    f = path(cfg, "meta") / "stations.csv"
    if not f.exists():
        raise FileNotFoundError(f"{f} missing: run `python src/stations.py` first")
    return pd.read_csv(f, parse_dates=["start", "end"])


def select_stations(cfg: dict, spec: str | None, start=None, end=None):
    """Filter the station table by a spec ('all', 'HD', 'HD01,HD02') and an
    operating window overlap."""
    import pandas as pd

    st = load_stations(cfg)
    if spec and spec != "all":
        items = [s.strip() for s in spec.split(",") if s.strip()]
        mask = st["station"].isin(items)
        for it in items:
            if it in cfg["subarrays"]:
                mask |= st["subarray"] == it
        st = st[mask]
    if start is not None:
        st = st[st["end"] >= pd.Timestamp(start)]
    if end is not None:
        st = st[st["start"] < pd.Timestamp(end)]
    return st.reset_index(drop=True)


def day_path(cfg: dict, net: str, sta: str, t) -> Path:
    """Canonical day-file path: data/mseed/{net}.{sta}/{year}/{jday:03d}.mseed."""
    from obspy import UTCDateTime

    t = UTCDateTime(t)
    return path(cfg, "mseed") / f"{net}.{sta}" / f"{t.year}" / f"{t.julday:03d}.mseed"


def days(start, end):
    """List of UTCDateTime day starts in [start, end)."""
    from obspy import UTCDateTime

    t = UTCDateTime(UTCDateTime(start).date)
    end = UTCDateTime(end)
    out = []
    while t < end:
        out.append(t)
        t += 86400
    return out
