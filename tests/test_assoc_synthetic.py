"""Synthetic end-to-end test of association + location on the real HD station geometry."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common import load_config, select_stations  # noqa: E402
from locate import make_model, local_proj, locate_catalog, quality_flags  # noqa: E402


def test_pyocto_associates_and_locator_recovers_synthetic_events():
    from associate import associate
    from obspy import UTCDateTime

    cfg = load_config()
    st = select_stations(cfg, "HD", "2013-01-01", "2013-02-01")
    m = make_model(cfg, datum_km=round(float(st.elev.mean()) / 1000.0, 2))  # same datum as locate_catalog
    rng = np.random.default_rng(7)
    proj = local_proj(st.lat.mean(), st.lon.mean())
    sx, sy = proj(st.lon.to_numpy(), st.lat.to_numpy())
    truth, rows = [], []
    t0 = UTCDateTime("2013-01-01T00:00:00").timestamp
    for k in range(5):
        ex, ey, ez = rng.uniform(-100, 100), rng.uniform(-80, 80), rng.uniform(3, 20)
        ot = t0 + 600 * (k + 1)
        lon, lat = proj(ex, ey, inverse=True)
        truth.append((lat, lon, ez, ot))
        d = np.hypot(sx - ex, sy - ey)
        near = np.argsort(d)[:15]
        for i in near:
            for ph in ("P", "S"):
                tt = m.tt(ph, d[i], ez, st.elev.iloc[i] / 1000)
                rows.append(dict(network="XL", station=st.station.iloc[i], phase=ph,
                                 time=str(UTCDateTime(ot + tt + rng.normal(0, 0.05))), prob=0.8,
                                 n_models=6, time_std=0.02))
    # noise picks
    for _ in range(100):
        i = rng.integers(len(st))
        rows.append(dict(network="XL", station=st.station.iloc[i], phase=rng.choice(["P", "S"]),
                         time=str(UTCDateTime(t0 + rng.uniform(0, 3600))), prob=0.4, n_models=2, time_std=0.1))
    picks = pd.DataFrame(rows)
    events, assignments = associate(cfg, picks, st)
    assert len(events) == 5, f"expected 5 events, got {len(events)}"
    cat, p = locate_catalog(cfg, events, assignments, st)
    cat = quality_flags(cat, cfg).sort_values("time").reset_index(drop=True)
    for (lat, lon, z, ot), ev in zip(truth, cat.itertuples()):
        dist = 111.2 * np.hypot(ev.latitude - lat, (ev.longitude - lon) * np.cos(np.radians(lat)))
        assert dist < 2.0, dist
        assert abs(ev.depth_km - z) < 3.0
        assert abs(ev.time - ot) < 0.3
