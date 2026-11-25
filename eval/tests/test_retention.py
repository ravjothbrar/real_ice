"""Retention (brief 5.5, test 6.4 'retention is between 0 and 1')."""
import pathlib

import numpy as np
import pytest

from pipeline import retention as rt

INTERIM = pathlib.Path(__file__).resolve().parents[2] / "data" / "interim"

# synthetic grids: 25 km "SIC" grid 40x40, 75 km "drift" grid covering it, y decreasing like EASE2
SX = -500e3 + 25e3 * (np.arange(40) + 0.5)
SY = 500e3 - 25e3 * (np.arange(40) + 0.5)
GX = -600e3 + 75e3 * np.arange(17)
GY = 600e3 - 75e3 * np.arange(17)


def _ice(rng):
    return (rng.random((40, 40)) > 0.4).astype(float)


def test_zero_drift_R_equals_endpoint_indicator():
    rng = np.random.default_rng(1)
    sic0 = _ice(rng)
    sic_end = _ice(rng)
    sic_end[5, 5] = np.nan  # land/no data at the endpoint counts as not ice
    Z = np.zeros((30, GY.size, GX.size))
    R, Rn, _ = rt.retention_core(sic0, sic_end, SX, SY, Z, Z, GX, GY)
    seeded = sic0 >= 0.15
    assert np.all(np.isnan(R[~seeded])) and np.all(Rn[~seeded] == 0) and np.all(Rn[seeded] == rt.N_PER)
    expect = (np.nan_to_num(sic_end) >= 0.15).astype(float)
    assert np.array_equal(R[seeded], expect[seeded])


def test_uniform_drift_moves_particles_right_distance():
    nd, u, v = 20, 7_000.0, -3_000.0  # m/day
    DX = np.full((nd, GY.size, GX.size), u)
    DY = np.full((nd, GY.size, GX.size), v)
    px, py = np.array([0.0, 100e3, -200e3]), np.array([0.0, -50e3, 150e3])
    for method in ("euler", "rk2"):
        ex, ey, inside, held = rt.advect(px, py, DX, DY, GX, GY, method)
        assert np.allclose(ex - px, nd * u) and np.allclose(ey - py, nd * v)
        assert inside.all() and (held == 0).all()


def test_missing_drift_holds_still_and_partial_corners_renormalise():
    DX = np.full((1, GY.size, GX.size), np.nan)
    ex, ey, _, held = rt.advect(np.array([10e3]), np.array([10e3]), DX, DX, GX, GY)
    assert ex[0] == 10e3 and ey[0] == 10e3 and held[0] == 1
    F = np.full((GY.size, GX.size), np.nan)
    F[:, 8] = 5.0  # only one column valid: the renormalised value is that column's value
    val, ok = rt.bilinear(F, GX, GY, np.array([GX[8] + 30e3]), np.array([10e3]))
    assert ok[0] and np.isclose(val[0], 5.0)


def test_leaving_domain_not_retained():
    sic = np.ones((40, 40))
    DX = np.full((10, GY.size, GX.size), 200e3)  # 2000 km east: everything leaves
    R, _, ex = rt.retention_core(sic, sic, SX, SY, DX, DX * 0, GX, GY)
    assert np.all(R == 0) and np.all(ex["exit_frac"] == 1)


def test_R_bounded_random_field():
    rng = np.random.default_rng(3)
    DX = rng.normal(0, 8e3, (40, GY.size, GX.size))
    DY = rng.normal(0, 8e3, (40, GY.size, GX.size))
    DX[:, 3:6, 3:6] = np.nan
    R, _, _ = rt.retention_core(_ice(rng), _ice(rng), SX, SY, DX, DY, GX, GY)
    f = R[np.isfinite(R)]
    assert f.size and f.min() >= 0 and f.max() <= 1


def _files():
    return sorted(INTERIM.glob("retention_*.nc"))


@pytest.mark.skipif(not _files(), reason="retention_W.nc not built")
def test_interim_R_in_unit_interval_and_on_grid():
    xr = pytest.importorskip("xarray")
    for p in _files():
        ds = xr.open_dataset(p)
        R = ds["R"].values
        assert R.shape == (360, 360)
        f = R[np.isfinite(R)]
        assert f.size > 1000 and f.min() >= 0 and f.max() <= 1
        assert set(np.unique(ds["R_n"].values[np.isfinite(R)])) == {float(rt.N_PER)}


@pytest.mark.skipif(not _files(), reason="retention_W.nc not built")
def test_interim_fram_export_lower_than_beaufort_and_north_greenland():
    rows = rt.box_means([int(p.stem.split("_")[1]) for p in _files()])
    m = {k.split(" (")[0]: np.nanmean(v) for k, (v, n) in rows.items()}
    assert m["Fram Strait"] < m["Beaufort"] and m["Fram Strait"] < m["N Greenland / CAA"]


@pytest.mark.skipif(not (INTERIM / "sept_presence.nc").exists(), reason="sept_presence.nc not built")
def test_sept_presence_bounds():
    xr = pytest.importorskip("xarray")
    f = xr.open_dataset(INTERIM / "sept_presence.nc")["freq"].values
    g = f[np.isfinite(f)]
    assert g.min() >= 0 and g.max() <= 1 and (g == 1).sum() > 2000
    s = xr.open_dataset(INTERIM / "sic_sept.nc")["sic_sept"]
    assert list(s["year"].values) == list(range(2011, 2026))
