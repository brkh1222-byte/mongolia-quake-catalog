"""Unit tests that run offline in a few seconds:  .venv/bin/python -m pytest -q tests"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common import load_config  # noqa: E402
from ensemble import ensemble_picks  # noqa: E402
from locate import TwoLayer, locate_event  # noqa: E402
from magnitude import minus_log_a0, wa_paz  # noqa: E402

CFG = load_config()


def _raw(rows):
    return pd.DataFrame(rows, columns=["network", "station", "phase", "time", "prob", "model", "weights"])


def test_ensemble_merges_within_tolerance_and_votes():
    t = "2013-01-01T00:00:{:06.3f}Z"
    raw = _raw([
        ("XL", "HD01", "P", t.format(10.00), 0.9, "PhaseNet", "stead"),
        ("XL", "HD01", "P", t.format(10.10), 0.8, "PhaseNet", "instance"),
        ("XL", "HD01", "P", t.format(10.20), 0.7, "EQTransformer", "stead"),
        ("XL", "HD01", "P", t.format(30.00), 0.95, "PhaseNet", "stead"),  # lone pick: rejected
        ("XL", "HD01", "S", t.format(15.00), 0.6, "PhaseNet", "stead"),
        ("XL", "HD01", "S", t.format(15.30), 0.6, "PhaseNet", "original"),
    ])
    ens = ensemble_picks(raw, n_pairs=6, tolerance={"P": 0.3, "S": 0.5}, min_models=2, min_mean_prob=0.15)
    assert list(ens.phase) == ["P", "S"]
    p = ens.iloc[0]
    assert p.n_models == 3
    assert p.prob == pytest.approx((0.9 + 0.8 + 0.7) / 6)
    w = np.array([0.9, 0.8, 0.7])
    assert pd.Timestamp(p.time).second + pd.Timestamp(p.time).microsecond / 1e6 == pytest.approx(
        float(np.sum(w * [10.0, 10.1, 10.2]) / w.sum()), abs=1e-3)


def test_ensemble_one_pick_per_model_and_ps_conflict():
    t = "2013-01-01T00:00:{:06.3f}Z"
    raw = _raw([
        ("XL", "HD01", "P", t.format(10.00), 0.5, "PhaseNet", "stead"),
        ("XL", "HD01", "P", t.format(10.05), 0.9, "PhaseNet", "stead"),   # same model twice
        ("XL", "HD01", "P", t.format(10.10), 0.9, "PhaseNet", "instance"),
        ("XL", "HD01", "S", t.format(10.20), 0.4, "PhaseNet", "stead"),   # conflicts with P
        ("XL", "HD01", "S", t.format(10.25), 0.4, "PhaseNet", "instance"),
    ])
    ens = ensemble_picks(raw, n_pairs=2, tolerance={"P": 0.3, "S": 0.5}, min_models=2, min_mean_prob=0.3)
    assert len(ens) == 1 and ens.iloc[0].phase == "P"
    assert ens.iloc[0].prob == pytest.approx(0.9)


def test_two_layer_travel_times():
    m = TwoLayer(CFG)
    # vertical incidence from 10 km depth to a sea-level station
    assert m.tt("P", 0.0, 10.0, 0.0) == pytest.approx(10 / 6.4)
    # far away the Moho head wave must be faster than the direct wave
    x = 400.0
    direct = np.hypot(x, 10) / 6.4
    assert m.tt("P", x, 10.0, 0.0) < direct
    # head-wave slope is the mantle velocity
    assert m.tt("P", 500.0, 10.0, 0.0) - m.tt("P", 400.0, 10.0, 0.0) == pytest.approx(100 / 8.0)


def test_locator_recovers_synthetic_event():
    rng = np.random.default_rng(1)
    m = TwoLayer(CFG)
    sx, sy = rng.uniform(-80, 80, 15), rng.uniform(-80, 80, 15)
    se = rng.uniform(1.2, 2.5, 15)
    true = np.array([5.0, -8.0, 12.0, 0.0])
    ph = np.array(["P"] * 15 + ["S"] * 15)
    sx2, sy2, se2 = np.tile(sx, 2), np.tile(sy, 2), np.tile(se, 2)
    d = np.hypot(sx2 - true[0], sy2 - true[1])
    tobs = np.where(ph == "P", m.tt("P", d, true[2], se2), m.tt("S", d, true[2], se2))
    tobs = tobs + rng.normal(0, 0.05, len(tobs))
    sol, res = locate_event(m, (0, 0, 5, 0.5), sx2, sy2, se2, ph, tobs, np.ones(len(tobs)))
    assert abs(sol["x"] - true[0]) < 1.0 and abs(sol["y"] - true[1]) < 1.0
    assert abs(sol["z"] - true[2]) < 2.0
    assert sol["rms"] < 0.1 and sol["erz"] < 3.0


def test_ml_definition():
    # Richter's anchor: 1 mm WA amplitude at 100 km is ML 3.0
    assert minus_log_a0(100.0) == pytest.approx(3.0)
    assert minus_log_a0(17.0) == pytest.approx(1.11 * np.log10(0.17) + 0.00189 * (17 - 100) + 3, abs=1e-9)
    paz = wa_paz()
    assert abs(paz["poles"][0]) == pytest.approx(2 * np.pi / 0.8)
    assert -paz["poles"][0].real / abs(paz["poles"][0]) == pytest.approx(0.7)
