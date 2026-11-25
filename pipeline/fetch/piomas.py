"""PIOMAS v2.1 monthly ice thickness (heff) and snow, regridded to the 25 km EASE2-N grid.

Source: https://pscfiles.apl.uw.edu/zhang/PIOMAS/data/v2.1/{heff,other}/ (anonymous https).
Files heff.H<yyyy>.gz / snow.H<yyyy>.gz: flat little-endian float32, 12 months x 120 x 360, no header.
Grid: https://pscfiles.apl.uw.edu/zhang/PIOMAS/utilities/grid.dat ('(10f8.2)': clon then clat, 360x120).
MODEL OUTPUT, not observation (Zhang & Rothrock 2003).

Output data/interim/piomas_W.nc for W = 2011..2024: h_nov (Nov W), h_apr (Apr W+1), snow_apr (Apr W+1).
"""
import gzip, numpy as np, xarray as xr
from scipy.interpolate import LinearNDInterpolator
from scipy.spatial import cKDTree
from pipeline import http, grid

BASE = "https://pscfiles.apl.uw.edu/zhang/PIOMAS"
NX, NY = 360, 120
INTERIM = http.RAW.parent / "interim"


def _grid():
    p = http.get(f"{BASE}/utilities/grid.dat", "piomas/grid.dat")
    vals = np.array(p.read_text().split(), float)
    n = NX * NY
    return vals[:n].reshape(NY, NX), vals[n:2 * n].reshape(NY, NX)   # lon, lat


def _year(var, y):
    sub = "heff" if var == "heff" else "other"
    p = http.get(f"{BASE}/data/v2.1/{sub}/{var}.H{y}.gz", f"piomas/{var}.H{y}.gz")
    a = np.frombuffer(gzip.decompress(p.read_bytes()), "<f4")
    return a.reshape(-1, NY, NX), p


class Regridder:
    def __init__(self):
        lon, lat = _grid()
        x, y = grid._to_xy.transform(lon.ravel(), lat.ravel())
        self.src = np.c_[x, y]
        self.tri = None
        d, _ = cKDTree(self.src).query(np.c_[grid.XX.ravel(), grid.YY.ravel()])
        self.far = (d > 60_000).reshape(grid.CROP, grid.CROP)   # outside PIOMAS domain (>60 km from any node)

    def __call__(self, field):
        v = np.asarray(field, float).ravel()
        if self.tri is None:
            self.tri = LinearNDInterpolator(self.src, v)
        else:
            self.tri.values = v.reshape(-1, 1).astype(self.tri.values.dtype)
        out = self.tri(grid.XX, grid.YY)
        out[self.far] = np.nan
        return out.astype(np.float32)


def build(winters=range(2011, 2025)):
    INTERIM.mkdir(parents=True, exist_ok=True)
    rg = Regridder()
    files, cache = {}, {}

    def get(var, y):
        if (var, y) not in cache:
            a, p = _year(var, y)
            cache[(var, y)] = a
            files[p.name] = {"name": f"data/raw/piomas/{p.name}", "sha256": http.sha256(p), "bytes": p.stat().st_size}
        return cache[(var, y)]

    for W in winters:
        h_nov = rg(get("heff", W)[10])
        h_apr = rg(get("heff", W + 1)[3])
        s_apr = rg(get("snow", W + 1)[3])
        ds = xr.Dataset(
            {"h_nov": (("y", "x"), h_nov, {"units": "m", "long_name": "PIOMAS mean ice thickness (volume per area), November W"}),
             "h_apr": (("y", "x"), h_apr, {"units": "m", "long_name": "PIOMAS mean ice thickness, April W+1"}),
             "snow_apr": (("y", "x"), s_apr, {"units": "m", "long_name": "PIOMAS snow depth (per PSC table: water equivalent), April W+1"})},
            coords={"lat": (("y", "x"), grid.LAT.astype(np.float32)), "lon": (("y", "x"), grid.LON.astype(np.float32))},
            attrs={"source": "PIOMAS v2.1 monthly (Zhang & Rothrock 2003), Polar Science Center, APL-UW",
                   "url": f"{BASE}/data/v2.1/", "winter": W, "note": "MODEL output, not observation. Linear (Delaunay) regrid in EPSG:6931 from the 360x120 curvilinear grid."})
        enc = {v: {"zlib": True, "complevel": 4} for v in ds.data_vars}
        ds.to_netcdf(INTERIM / f"piomas_{W}.nc", encoding=enc)
        print("piomas", W, "h_nov mean", np.nanmean(h_nov).round(2), "h_apr mean", np.nanmean(h_apr).round(2))
    gp = http.RAW / "piomas/grid.dat"
    files["grid.dat"] = {"name": "data/raw/piomas/grid.dat", "sha256": http.sha256(gp), "bytes": gp.stat().st_size}
    http.record("piomas", dataset="PIOMAS v2.1 monthly sea-ice thickness (heff) and snow depth",
                url=f"{BASE}/data/v2.1/heff/ and {BASE}/data/v2.1/other/ ; grid {BASE}/utilities/grid.dat",
                doi="Zhang, J. & Rothrock, D.A. (2003) Mon. Wea. Rev. 131, 845-861, doi:10.1175/1520-0493(2003)131<0845:MGSIWA>2.0.CO;2; Schweiger et al. (2011) JGR 116, C00D06, doi:10.1029/2011JC007084",
                licence="Freely available from the Polar Science Center (APL, University of Washington) for research use with citation of Zhang & Rothrock (2003) and Schweiger et al. (2011); no formal open licence stated on the data page.",
                files=list(files.values()),
                notes="Model output, not observation. Version 2.1. H2026 holds only Jan-Feb 2026 at access, so W=2025 April fields unavailable.")


if __name__ == "__main__":
    build()
