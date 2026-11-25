"""Sanity tests for climate_W.nc and static.nc (skip cleanly if interim files are missing)."""
import pathlib
import numpy as np
import pytest

xr = pytest.importorskip("xarray")
INTERIM = pathlib.Path(__file__).resolve().parents[2] / "data" / "interim"
CLIM = sorted(p for p in INTERIM.glob("climate_*.nc"))
STATIC = INTERIM / "static.nc"


def _full_winters():
    out = []
    for p in CLIM:
        ds = xr.open_dataset(p)
        if not ds.attrs.get("partial_winter", 0):
            out.append(ds)
    return out


@pytest.fixture(scope="module")
def static():
    if not STATIC.exists():
        pytest.skip("static.nc missing")
    return xr.open_dataset(STATIC)


@pytest.fixture(scope="module")
def winters():
    w = _full_winters()
    if not w:
        pytest.skip("no complete climate_W.nc")
    return w


def _box_mean(a, lat, lon, lat0, lat1, lon0, lon1):
    lon = ((lon + 180) % 360) - 180
    m = (lat >= lat0) & (lat < lat1) & (lon >= lon0) & (lon < lon1) & np.isfinite(a)
    return np.nanmean(a[m])


def test_fdd_nonnegative(winters):
    for ds in winters:
        for v in ("fdd", "fdd_jan"):
            a = ds[v].values
            assert np.nanmin(a) >= 0, (ds.attrs["winter"], v)
        assert np.all((ds.fdd_jan.values <= ds.fdd.values + 1e-3) | np.isnan(ds.fdd.values))


def test_fdd_central_arctic_exceeds_barents(winters):
    for ds in winters:
        lat, lon = ds.lat.values, ds.lon.values
        central = _box_mean(ds.fdd.values, lat, lon, 85, 90, -180, 180)
        barents = _box_mean(ds.fdd.values, lat, lon, 70, 76, 20, 50)
        assert central > barents, (ds.attrs["winter"], central, barents)
        assert 3000 < central < 7000, central   # order-of-magnitude check, K day


def test_melt_days_range(winters):
    for ds in winters:
        a = ds.melt_days.values
        assert np.nanmin(a) >= 0 and np.nanmax(a) <= 138
        # melting season reaches the central Arctic but is longer in the Barents Sea
        lat, lon = ds.lat.values, ds.lon.values
        assert _box_mean(a, lat, lon, 70, 76, 20, 50) > _box_mean(a, lat, lon, 85, 90, -180, 180)


def test_snowfall_plausible(winters):
    for ds in winters:
        a = ds.snowfall.values
        assert np.nanmin(a) >= 0 and np.nanmax(a) < 5.0
        lat, lon = ds.lat.values, ds.lon.values
        assert 0.02 < _box_mean(a, lat, lon, 85, 90, -180, 180) < 0.5


def test_land_covers_greenland_interior(static):
    from pipeline import grid
    for lon, lat in [(-40, 72), (-45, 65), (-38, 77), (-50, 70)]:
        i, j = grid.lonlat_to_ij(lon, lat)
        assert static.land.values[int(round(float(i))), int(round(float(j)))] == 1, (lon, lat)
    i, j = grid.lonlat_to_ij(0.0, 90.0)
    assert static.land.values[int(round(float(i))), int(round(float(j)))] == 0   # North Pole is ocean


def test_static_layers(static):
    from pipeline import grid
    assert set(np.unique(static.region.values)) <= set(range(8))
    assert static.excl_protected.values.sum() == 0 and static.excl_protected.attrs["status"] == "not available"
    i, j = grid.lonlat_to_ij(-105.06, 69.117)                 # Cambridge Bay hamlet
    i, j = int(round(float(i))), int(round(float(j)))
    assert static.excl_settlement.values[i, j] == 1
    assert static.excl_shipping.values[i, j] == 1


def test_cambridge_bay_csv():
    p = INTERIM / "cambridge_bay_climate.csv"
    if not p.exists():
        pytest.skip("csv missing")
    import csv
    rows = list(csv.DictReader(l for l in open(p) if not l.startswith("#")))
    full = [r for r in rows if r["partial"] == "0"]
    assert full
    for r in full:
        assert 3000 < float(r["fdd"]) < 7500
        assert float(r["fdd_mar"]) <= float(r["fdd_jan"]) <= float(r["fdd"])
