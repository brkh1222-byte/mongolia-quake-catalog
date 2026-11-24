"""First-arrival travel times in a flat-layered 1-D model (pure NumPy).

Layers are given as a list of {depth (top, km), vp, vs} with constant velocity
inside each layer (step interfaces). The receiver is at depth 0 (sea level),
and depth z is the source depth below sea level.

The first arrival is the minimum of:
  * the direct (upgoing) ray. For a ray parameter p below 1/max(v above the
    source), the source-to-surface ray gives
        x(p) = sum_i h_i p v_i / sqrt(1 - p^2 v_i^2)
        t(p) = sum_i h_i / (v_i sqrt(1 - p^2 v_i^2)),
    with h_i the thickness of each layer crossed. t(x) is tabulated by
    sweeping p and interpolated. Near-horizontal rays are covered by sampling
    p densely close to 1/v_max;
  * head waves along every interface (depth H) below the source whose lower
    velocity v_r exceeds every velocity above it:
        t = x / v_r + sum_i T_i q_i + sum_i B_i q_i,   q_i = sqrt(1/v_i^2 - 1/v_r^2),
    where T_i is the thickness of layer i between the surface and H (receiver
    leg) and B_i its thickness between the source and H (source leg). Valid
    beyond the critical distance.
This is exact for constant-velocity layers. It replaces pyrocko's eikonal
solver, which does not build against NumPy 2.

`write_pyocto_model` writes the binary table format of
pyocto.VelocityModel1D (int nx, int nz, double delta, then the P and S tables
of shape (nx, nz), C order), so PyOcto and our locator use identical travel
times.
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np


def _layers_array(layers, key):
    tops = np.array([max(L["depth"], 0.0) for L in layers], float)
    v = np.array([L[key] for L in layers], float)
    keep = np.r_[True, np.diff(tops) > 0]
    # if several layers start above sea level, keep the deepest of them at 0
    tops, v = tops[keep | (tops > 0)], v[keep | (tops > 0)]
    order = np.argsort(tops, kind="stable")
    tops, v = tops[order], v[order]
    # collapse duplicate tops (keep the last, i.e. the one valid below)
    uniq = np.r_[tops[1:] != tops[:-1], True]
    return tops[uniq], v[uniq]


def first_arrival(layers, key, x, z, n_p=4000):
    """Travel time (s) for source depth z (km, scalar) and distances x (km, array)."""
    tops, v = _layers_array(layers, key)
    x = np.atleast_1d(np.asarray(x, float))
    z = max(float(z), 0.0)
    # thicknesses of the layers between the surface and the source
    bounds = np.r_[tops, np.inf]
    h_up = np.clip(np.minimum(bounds[1:], z) - bounds[:-1], 0, None)
    above = h_up > 0
    t_best = np.full(x.shape, np.inf)
    if z == 0:
        t_best = x / v[0]
    else:
        va, ha = v[above], h_up[above]
        pmax = 1.0 / va.max()
        # dense near-grazing sampling: p = pmax * (1 - s^2)
        s = np.linspace(0, 1, n_p)[::-1]
        p = pmax * (1 - s ** 2) * (1 - 1e-9)
        c = np.sqrt(1 - (p[:, None] * va[None, :]) ** 2)
        xp = np.sum(ha * p[:, None] * va / c, axis=1)
        tp = np.sum(ha / (va * c), axis=1)
        o = np.argsort(xp)
        xp, tp = xp[o], tp[o]
        direct = np.interp(x, xp, tp, right=np.inf)
        # beyond the last sampled x (only very near-grazing rays): straight-line bound
        far = x > xp[-1]
        if far.any():
            direct[far] = tp[-1] + (x[far] - xp[-1]) * pmax
        t_best = direct
    # head waves along interfaces below the source
    for j in range(1, len(tops)):
        H = tops[j]
        if H <= z:
            continue
        vr = v[j]
        if np.any(v[:j] >= vr):
            continue
        q = np.sqrt(1 / v[:j] ** 2 - 1 / vr ** 2)
        thick = np.diff(np.r_[tops[:j], H])
        h_above = np.clip(np.minimum(np.r_[tops[1:j], H], z) - tops[:j], 0, None)  # above source
        h_below = thick - h_above                                                 # source..interface
        delay = np.sum(thick * q) + np.sum(h_below * q)  # receiver side full + source side partial
        xcrit = np.sum(thick * v[:j] / vr / np.sqrt(1 - (v[:j] / vr) ** 2)) + \
            np.sum(h_below * v[:j] / vr / np.sqrt(1 - (v[:j] / vr) ** 2))
        head = np.where(x >= xcrit, x / vr + delay, np.inf)
        t_best = np.minimum(t_best, head)
    return t_best


def table(layers, key, delta=1.0, xmax=900.0, zmax=65.0):
    nx, nz = int(xmax / delta), int(zmax / delta)
    x = np.arange(nx) * delta
    T = np.empty((nx, nz))
    for k in range(nz):
        T[:, k] = first_arrival(layers, key, x, k * delta)
    return T


def write_pyocto_model(layers, path: Path, delta=1.0, xmax=900.0, zmax=65.0):
    tp = table(layers, "vp", delta, xmax, zmax)
    ts = table(layers, "vs", delta, xmax, zmax)
    nx, nz = tp.shape
    with open(path, "wb") as f:
        f.write(struct.pack("iid", nx, nz, delta))
        f.write(np.ascontiguousarray(tp).tobytes())
        f.write(np.ascontiguousarray(ts).tobytes())


class TableModel:
    """Locator interface: tt(phase, x, z, e) from interpolated tables.

    `datum_km` is a reference elevation (km above sea level, e.g. the mean
    station elevation). The tables are computed for a receiver ON the datum, with
    the layer interfaces kept at their true depths below sea level. A source at
    depth z (km below sea level, may be negative down to -datum) is then at
    z + datum below the receiver level, and a station at elevation e gets the
    vertical static (e - datum) / v_top. With datum = 0 this is the plain
    sea-level model with a floor at z = 0."""

    def __init__(self, layers, delta=0.5, xmax=800.0, zmax=80.0, datum_km=0.0):
        from scipy.interpolate import RegularGridInterpolator

        self.zmax = zmax
        self.datum = float(datum_km)
        shifted = [dict(L, depth=(L["depth"] + self.datum) if i > 0 else min(L["depth"] + self.datum, 0.0))
                   for i, L in enumerate(layers)]
        self.interp, self.v_top = {}, {}
        x = np.arange(int(xmax / delta)) * delta
        z = np.arange(int(zmax / delta)) * delta
        for ph, key in (("P", "vp"), ("S", "vs")):
            T = table(shifted, key, delta, xmax, zmax)
            self.interp[ph] = RegularGridInterpolator((x, z), T, bounds_error=False, fill_value=None)
            self.v_top[ph] = _layers_array(shifted, key)[1][0]

    def tt(self, phase, x, z, e):
        x = np.atleast_1d(np.asarray(x, float))
        zz = np.clip(np.broadcast_to(np.asarray(z, float) + self.datum, x.shape), 0.0, self.zmax)
        t = self.interp[phase](np.c_[np.abs(x), zz]) + (np.asarray(e) - self.datum) / self.v_top[phase]
        return t if t.size > 1 else float(t[0])
