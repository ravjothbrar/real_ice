"""Thickness layers: contract shape, physical plausibility, disagreement sanity (brief section 6 test 5).
Skips cleanly when data/interim files are absent."""
import pathlib
import numpy as np
import pytest

xr = pytest.importorskip("xarray")
INTERIM = pathlib.Path(__file__).resolve().parents[2] / "data" / "interim"
FILES = sorted(p for prod in ("cpom", "petty", "awi") for p in INTERIM.glob(f"thick_{prod}_*.nc"))
DIS = INTERIM / "thick_disagreement.nc"


def _need(files):
    if not files:
        pytest.skip("no thickness files in data/interim (run python -m pipeline.thickness)")


@pytest.mark.parametrize("path", FILES or [None], ids=lambda p: p.name if p else "none")
def test_contract_shape_and_vars(path):
    _need(FILES)
    with xr.open_dataset(path) as ds:
        assert ds.h0.dims == ("y", "x") and ds.h0.shape == (360, 360)
        assert "h0_unc" in ds and ds.h0_unc.shape == (360, 360)
        assert "lat" in ds.coords and "lon" in ds.coords
        assert ds.h0.dtype == np.float32
        assert "h0_choice" in ds.attrs and "November" in ds.attrs["h0_choice"]
        if "_awi_" not in path.name and not ds.attrs.get("partial"):
            assert "h_apr" in ds and ds.h_apr.shape == (360, 360)


@pytest.mark.parametrize("path", FILES or [None], ids=lambda p: p.name if p else "none")
def test_h0_physically_plausible(path):
    _need(FILES)
    with xr.open_dataset(path) as ds:
        h = ds.h0.values
        v = h[np.isfinite(h)]
        assert v.size > 1000, "suspiciously few valid cells"
        assert v.min() >= 0 and v.max() <= 8
        assert 0.3 < np.median(v) < 3.0  # November Arctic mean thickness is O(1 m)
        u = ds.h0_unc.values
        assert np.nanmin(u) >= 0
        if "h_apr" in ds and np.isfinite(ds.h_apr.values).any():
            a = ds.h_apr.values
            assert np.nanmin(a) >= 0 and np.nanmax(a) <= 8
            # growth season: April median exceeds November median
            assert np.nanmedian(a) > np.nanmedian(h)


def test_ice_where_expected():
    """Central Arctic (85N) must carry ice > 0.5 m in November; the pole hole is allowed to be NaN."""
    _need(FILES)
    from pipeline import grid
    i, j = (int(round(float(k))) for k in grid.lonlat_to_ij(-60.0, 85.0))
    for p in FILES:
        with xr.open_dataset(p) as ds:
            box = ds.h0.values[i - 3:i + 4, j - 3:j + 4]  # NRT 14-day fields have orbit gaps
            assert np.isfinite(box).sum() >= 5 and np.nanmean(box) > 0.5, p.name


def test_disagreement_nonnegative():
    if not DIS.exists():
        pytest.skip("thick_disagreement.nc absent")
    with xr.open_dataset(DIS) as ds:
        vs = [v for v in ds.data_vars if v.startswith("absdiff_")]
        assert vs
        for v in vs:
            a = ds[v].values
            assert a.shape == (360, 360)
            assert np.nanmin(a) >= 0
            n = ds["n_" + v[len("absdiff_"):]].values
            assert np.all(np.isfinite(a) == (n > 0))
