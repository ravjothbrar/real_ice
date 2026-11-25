"""Load interim layers (docs/CONTRACT.md) into per-winter arrays on the ice-capable cell list."""
import pathlib
import numpy as np
import xarray as xr
from . import grid

INTERIM = pathlib.Path(__file__).resolve().parents[1] / "data" / "interim"
PRODUCTS = ("cpom", "petty", "awi")


def _open(name):
    p = INTERIM / name
    return xr.open_dataset(p) if p.exists() else None


def _arr(ds, var):
    if ds is None or var not in ds:
        return None
    a = ds[var].values.astype(float)
    return a if a.shape[-2:] == (grid.CROP, grid.CROP) else None


def winters_available():
    ws = set()
    for p in PRODUCTS:
        for f in INTERIM.glob(f"thick_{p}_*.nc"):
            try:
                ws.add(int(f.stem.split("_")[-1]))
            except ValueError:
                pass
    return sorted(ws)


def thickness(w):
    """Ensemble start thickness for winter w: mean over available products; sd combines product
    uncertainty and between-product spread. Returns dict of 2-D arrays + list of products used."""
    hs, us, used = [], [], []
    for p in PRODUCTS:
        ds = _open(f"thick_{p}_{w}.nc")
        h = _arr(ds, "h0")
        if h is None:
            continue
        u = _arr(ds, "h0_unc")
        hs.append(h); us.append(u if u is not None else np.full_like(h, np.nan)); used.append(p)
    if not hs:
        return None
    H, U = np.stack(hs), np.stack(us)
    n = np.isfinite(H).sum(0)
    with np.errstate(all="ignore"):
        mean = np.nanmean(H, 0)
        spread = np.nanstd(H, 0) if len(hs) > 1 else np.zeros_like(mean)
        unc = np.sqrt(np.nanmean(U ** 2, 0))
    unc = np.where(np.isfinite(unc), unc, 0.3)       # fallback when a product ships no uncertainty
    spread = np.where(n > 1, spread, 0.0)
    return {"h0": mean, "h0_sd": np.sqrt(unc ** 2 + spread ** 2), "spread": np.where(n > 1, spread, np.nan),
            "n_products": n, "products": used, "per_product": dict(zip(used, hs))}


def climate(w):
    ds = _open(f"climate_{w}.nc")
    if ds is None:
        return None
    return {k: _arr(ds, k) for k in ("fdd", "fdd_jan", "melt_days", "snowfall") if _arr(ds, k) is not None}


def retention(w):
    return _arr(_open(f"retention_{w}.nc"), "R")


def static():
    ds = _open("static.nc")
    out = {}
    if ds is not None:
        for k in ("land", "depth", "excl_settlement", "excl_protected", "excl_shipping", "region"):
            a = _arr(ds, k)
            if a is not None:
                out[k] = a
    return out


def sept():
    """(years, sic_sept[year, y, x], freq[y, x])"""
    s, f = _open("sic_sept.nc"), _open("sept_presence.nc")
    years = s["year"].values.astype(int) if s is not None and "year" in s.coords else None
    return years, (s["sic_sept"].values if s is not None else None), _arr(f, "freq")
