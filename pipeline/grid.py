"""EASE-Grid 2.0 North, 25 km (EPSG:6931), cropped to the Arctic.

Full EASE2-N 25 km grid is 720 x 720 cells spanning +/-9000 km. We keep the central
CROP x CROP block (+/-4500 km), which reaches ~50N along the diagonals and contains every
cell that has carried sea ice in the satellite era (Hudson Bay, Okhotsk/Bering edges included).
Cell (i, j): i = row from top (y decreasing), j = column from left (x increasing).
"""
import numpy as np
import pyproj

EPSG = 6931
RES = 25_000.0
FULL = 720
CROP = 360
HALF = CROP * RES / 2  # 4,500 km

# cell-centre coordinates in metres
x = -HALF + RES * (np.arange(CROP) + 0.5)
y = HALF - RES * (np.arange(CROP) + 0.5)
XX, YY = np.meshgrid(x, y)

_to_ll = pyproj.Transformer.from_crs(EPSG, 4326, always_xy=True)
_to_xy = pyproj.Transformer.from_crs(4326, EPSG, always_xy=True)
LON, LAT = _to_ll.transform(XX, YY)
CELL_AREA_KM2 = (RES / 1000) ** 2  # EASE2 is equal-area: 625 km2 per cell


def lonlat_to_ij(lon, lat):
    """Return fractional (i, j) indices for lon/lat arrays."""
    xx, yy = _to_xy.transform(np.asarray(lon), np.asarray(lat))
    j = (xx + HALF) / RES - 0.5
    i = (HALF - yy) / RES - 0.5
    return i, j


def xy_to_ij(xx, yy):
    return (HALF - np.asarray(yy)) / RES - 0.5, (np.asarray(xx) + HALF) / RES - 0.5


def regrid_points(lon, lat, values, how="mean"):
    """Bin scattered/finer-grid points onto the 25 km grid (mean of points per cell).
    Suits 5 km -> 25 km aggregation. Returns (CROP, CROP) array with NaN where empty."""
    lon, lat, values = (np.asarray(a).ravel() for a in (lon, lat, values))
    ok = np.isfinite(values) & np.isfinite(lon) & np.isfinite(lat)
    i, j = lonlat_to_ij(lon[ok], lat[ok])
    i = np.rint(i).astype(int); j = np.rint(j).astype(int)
    inb = (i >= 0) & (i < CROP) & (j >= 0) & (j < CROP)
    flat = i[inb] * CROP + j[inb]
    s = np.bincount(flat, weights=values[ok][inb], minlength=CROP * CROP)
    n = np.bincount(flat, minlength=CROP * CROP)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = s / n
    if how == "std":
        s2 = np.bincount(flat, weights=values[ok][inb] ** 2, minlength=CROP * CROP)
        with np.errstate(invalid="ignore", divide="ignore"):
            out = np.sqrt(np.maximum(s2 / n - out ** 2, 0))
    out[n == 0] = np.nan
    return out.reshape(CROP, CROP)


def sample_grid(src_x, src_y, src_vals, method="nearest"):
    """Sample a regular source grid (1-D x, y in EPSG:6931 metres or any projection already
    transformed) at our cell centres. For coarser sources (e.g. 62.5/75 km drift)."""
    from scipy.interpolate import RegularGridInterpolator
    sx, sy, v = np.asarray(src_x), np.asarray(src_y), np.asarray(src_vals, float)
    if sy[0] > sy[-1]:
        sy, v = sy[::-1], v[::-1]
    f = RegularGridInterpolator((sy, sx), v, method=method, bounds_error=False, fill_value=np.nan)
    return f(np.stack([YY.ravel(), XX.ravel()], -1)).reshape(CROP, CROP)


if __name__ == "__main__":
    print("grid", CROP, "x", CROP, "lat range", LAT.min().round(1), LAT.max().round(1))
