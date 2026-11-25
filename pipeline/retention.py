"""P5: September presence and Lagrangian retention R (brief 5.5).

For winter W: seed 4 particles per cell (2x2 stratified, jittered inside each quadrant) at every cell with
SIC >= 0.15 on 1 Nov W (12 UTC). Advect day by day with OSI SAF daily drift (bilinear interpolation of the
displacement on its native 75 km EASE2 grid, midpoint RK2 with daily steps) to 15 Sep W+1 (12 UTC).
R(cell) = fraction of the cell's particles that end inside the drift domain on a cell with SIC >= 0.15.
Only the endpoint matters: a particle crossing low-SIC water mid-season is not killed.

Missing drift: bilinear weights are renormalised over the valid corners; where none of the four corners has a
vector the particle is held still for that day (counted in `held_frac`). OSI-455/435 summers are already
gap-filled with OSI SAF's wind-driven free-drift model; OSI-405 (2026) is not, so winter 2025 holds more particles.
A particle that leaves the drift domain (+/-3562.5 km, centres of the 96x96 crop) is frozen and counts as not retained.

Usage: python -m pipeline.retention [W ...]   (defaults: every winter whose data are cached)
"""
import datetime as dt
import json
import pathlib
import sys

import numpy as np

from pipeline import grid

ROOT = pathlib.Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
FIGS = ROOT / "eval" / "figs"
THRESH = 0.15
N_PER = 4
WIND_FLAGS = (23, 24, 25)  # OSI-455/435 status_flag: wind drift gap-filled / replaced / blended

BOXES = {  # name: (lat0, lat1, lon0, lon1)
    "Fram Strait (78-81N, 10W-10E)": (78, 81, -10, 10),
    "N Greenland / CAA (83-87N, 60-100W)": (83, 87, -100, -60),
    "Beaufort (72-77N, 130-150W)": (72, 77, -150, -130),
    "Laptev (73-78N, 110-135E)": (73, 78, 110, 135),
}


# ----------------------------------------------------------------------------- core numerics (pure numpy)
def bilinear(field, gx, gy, px, py):
    """NaN-aware bilinear sample of field[(y, x)] on a regular grid with 1-D centres gx, gy (either order).
    Returns (values, ok); ok False where no corner is valid (values then 0)."""
    ny, nx = field.shape
    fj = (px - gx[0]) / (gx[1] - gx[0])
    fi = (py - gy[0]) / (gy[1] - gy[0])
    j0 = np.clip(np.floor(fj).astype(int), 0, nx - 2)
    i0 = np.clip(np.floor(fi).astype(int), 0, ny - 2)
    tj = np.clip(fj - j0, 0.0, 1.0)
    ti = np.clip(fi - i0, 0.0, 1.0)
    num = np.zeros(px.shape)
    den = np.zeros(px.shape)
    for di, dj, w in ((0, 0, (1 - ti) * (1 - tj)), (0, 1, (1 - ti) * tj), (1, 0, ti * (1 - tj)), (1, 1, ti * tj)):
        v = field[i0 + di, j0 + dj]
        good = np.isfinite(v)
        num += np.where(good, w * np.where(good, v, 0.0), 0.0)
        den += np.where(good, w, 0.0)
    ok = den > 1e-9
    return np.where(ok, num / np.where(ok, den, 1.0), 0.0), ok


def advect(px, py, DX, DY, gx, gy, method="rk2", count_days=None):
    """Advect particles (metres) through daily displacement fields DX, DY [m/day], shape (ndays, ny, nx).
    Returns final px, py, inside (never left the domain), held (particle-days with no drift; only days where
    count_days[k] is True if given)."""
    px, py = np.array(px, float), np.array(py, float)
    xmin, xmax = min(gx[0], gx[-1]), max(gx[0], gx[-1])
    ymin, ymax = min(gy[0], gy[-1]), max(gy[0], gy[-1])
    inside = (px >= xmin) & (px <= xmax) & (py >= ymin) & (py <= ymax)
    held = np.zeros(px.shape, int)
    for k in range(DX.shape[0]):
        a = np.where(inside)[0]
        if a.size == 0:
            break
        x, y = px[a], py[a]
        u, oku = bilinear(DX[k], gx, gy, x, y)
        v, _ = bilinear(DY[k], gx, gy, x, y)
        if method == "rk2":
            xm, ym = x + 0.5 * u, y + 0.5 * v
            u2, ok2 = bilinear(DX[k], gx, gy, xm, ym)
            v2, _ = bilinear(DY[k], gx, gy, xm, ym)
            u, v = np.where(ok2, u2, u), np.where(ok2, v2, v)
        if count_days is None or count_days[k]:
            held[a] += ~oku
        px[a], py[a] = x + u, y + v
        inside[a] = (px[a] >= xmin) & (px[a] <= xmax) & (py[a] >= ymin) & (py[a] <= ymax)
    return px, py, inside, held


def seed(sic0, sx, sy, n_per=N_PER, rng=None):
    """Particles in every cell with sic0 >= THRESH: 2x2 stratified quadrants, uniform jitter in each.
    Returns px, py, cell (flat index into sic0)."""
    rng = np.random.default_rng(0) if rng is None else rng
    ii, jj = np.nonzero(np.nan_to_num(sic0, nan=0.0) >= THRESH)
    res_x, res_y = abs(sx[1] - sx[0]), abs(sy[1] - sy[0])
    q = [(-0.25, -0.25), (-0.25, 0.25), (0.25, -0.25), (0.25, 0.25)]
    px, py, cell = [], [], []
    for k in range(n_per):
        ox, oy = q[k % 4]
        jx = rng.uniform(-0.24, 0.24, ii.size)
        jy = rng.uniform(-0.24, 0.24, ii.size)
        px.append(sx[jj] + (ox + jx) * res_x)
        py.append(sy[ii] + (oy + jy) * res_y)
        cell.append(ii * sic0.shape[1] + jj)
    return np.concatenate(px), np.concatenate(py), np.concatenate(cell)


def cell_of(px, py, sx, sy):
    j = np.floor((px - (sx[0] - 0.5 * (sx[1] - sx[0]))) / (sx[1] - sx[0])).astype(int)
    i = np.floor((py - (sy[0] - 0.5 * (sy[1] - sy[0]))) / (sy[1] - sy[0])).astype(int)
    return i, j


def retention_core(sic0, sic_end, sx, sy, DX, DY, gx, gy, n_per=N_PER, rng=None, method="rk2", winter_days=None):
    """Return R (fraction retained per seed cell, NaN unseeded), R_n (particles per cell), extras dict."""
    px, py, cell = seed(sic0, sx, sy, n_per, rng)
    # seeds outside the drift domain (a few lake / Hudson Bay / Caspian cells) are not tracked: R = NaN there
    x0, x1, y0, y1 = min(gx[0], gx[-1]), max(gx[0], gx[-1]), min(gy[0], gy[-1]), max(gy[0], gy[-1])
    keep = (px >= x0) & (px <= x1) & (py >= y0) & (py <= y1)
    bad = np.bincount(cell[~keep], minlength=sic0.size) > 0
    keep &= ~bad[cell]
    px, py, cell = px[keep], py[keep], cell[keep]
    ex, ey, inside, held = advect(px, py, DX, DY, gx, gy, method)
    held_w = None
    if winter_days is not None:
        held_w = advect(px, py, DX, DY, gx, gy, method, count_days=winter_days)[3]
    i, j = cell_of(ex, ey, sx, sy)
    ing = inside & (i >= 0) & (i < sic_end.shape[0]) & (j >= 0) & (j < sic_end.shape[1])
    endsic = np.full(ex.shape, np.nan)
    endsic[ing] = sic_end[i[ing], j[ing]]
    ok = ing & (np.nan_to_num(endsic, nan=0.0) >= THRESH)
    n = np.bincount(cell, minlength=sic0.size).astype(float)
    r = np.bincount(cell, weights=ok, minlength=sic0.size)
    with np.errstate(invalid="ignore", divide="ignore"):
        R = np.where(n > 0, r / n, np.nan).reshape(sic0.shape)
        out = np.where(n > 0, np.bincount(cell, weights=~inside, minlength=sic0.size) / n, np.nan).reshape(sic0.shape)
        hd = np.where(n > 0, np.bincount(cell, weights=held, minlength=sic0.size) / n, np.nan).reshape(sic0.shape)
        disp = np.hypot(ex - px, ey - py)
        dkm = np.where(n > 0, np.bincount(cell, weights=disp, minlength=sic0.size) / n / 1e3, np.nan).reshape(sic0.shape)
    extras = dict(n_untracked_cells=int(bad.sum()), exit_frac=out, held_days=hd, disp_km=dkm, n_particles=int(px.size),
                  held_particle_day_frac=float(held.sum() / max(px.size * DX.shape[0], 1)),
                  held_winter_frac=(float(held_w.sum() / max(px.size * winter_days.sum(), 1)) if held_w is not None else None))
    return R.astype("f4"), n.reshape(sic0.shape).astype("f4"), extras


# ----------------------------------------------------------------------------- data assembly
def _dates(W):
    d, out = dt.date(W, 11, 2), []
    while d <= dt.date(W + 1, 9, 15):
        out.append(d); d += dt.timedelta(days=1)
    return out


def _405_to_ease(path, gxm, gym):
    """Half of a 48 h OSI-405 displacement, moved from polar stereo to EASE2 metres and linearly gridded
    onto the 75 km EASE2 crop (cells > 80 km from any valid 405 vector stay NaN)."""
    import netCDF4, pyproj
    from scipy.interpolate import griddata
    from scipy.spatial import cKDTree
    with netCDF4.Dataset(path) as ds:
        xs, ys = ds["x"][:], ds["y"][:]
        dX = np.ma.filled(ds["dX"][:], np.nan) * 1000.0
        dY = np.ma.filled(ds["dY"][:], np.nan) * 1000.0
        proj = ds.proj4
    tr = pyproj.Transformer.from_crs(pyproj.CRS.from_proj4(proj), "EPSG:6931", always_xy=True)
    XS, YS = np.meshgrid(xs, ys)
    ok = np.isfinite(dX) & np.isfinite(dY)
    x0, y0 = tr.transform(XS[ok], YS[ok])
    x1, y1 = tr.transform(XS[ok] + dX[ok], YS[ok] + dY[ok])
    u, v = 0.5 * (x1 - x0), 0.5 * (y1 - y0)
    GX, GY = np.meshgrid(gxm, gym)
    pts = np.c_[GX.ravel(), GY.ravel()]
    U = griddata(np.c_[x0, y0], u, pts, method="linear").reshape(GX.shape)
    V = griddata(np.c_[x0, y0], v, pts, method="linear").reshape(GX.shape)
    far = cKDTree(np.c_[x0, y0]).query(pts)[0].reshape(GX.shape) > 80e3
    U[far] = np.nan; V[far] = np.nan
    return U, V


def load_drift(W):
    """Daily displacement stack (m/day) on the 75 km EASE2 crop for winter W, plus a per-day source log."""
    import netCDF4
    from pipeline.fetch import osisaf as o
    gx, gy = o.DR_X, o.DR_Y
    days = _dates(W)
    DX = np.full((len(days), gy.size, gx.size), np.nan, "f4")
    DY = DX.copy()
    src = []
    wind = np.full(len(days), np.nan)
    if W <= 2020:
        p = o.RAWD / "drift455" / f"drift455_{days[0]:%Y%m%d}_{min(days[-1], dt.date(2020, 12, 31)):%Y%m%d}.nc"
        with netCDF4.Dataset(p) as ds:
            t = ds["time"][:]
            n = len(t)
            assert (dt.date(1970, 1, 1) + dt.timedelta(days=int(t[0]))) == days[0]
            DX[:n] = np.ma.filled(ds["dX"][:], np.nan) * 1000.0
            DY[:n] = np.ma.filled(ds["dY"][:], np.nan) * 1000.0
            fl = ds["status_flag"][:]
        for k in range(n):
            val = np.isfinite(DX[k])
            wind[k] = np.isin(fl[k][val], WIND_FLAGS).mean() if val.any() else np.nan
        src += ["OSI-455"] * n
    for k in range(len(src), len(days)):
        d = days[k]
        if d <= dt.date(2025, 12, 31):
            p = o.RAWD / "drift435" / f"drift435_{d:%Y%m%d}.nc"
            if p.exists():
                with netCDF4.Dataset(p) as ds:
                    DX[k] = np.ma.filled(ds["dX"][:], np.nan) * 1000.0
                    DY[k] = np.ma.filled(ds["dY"][:], np.nan) * 1000.0
                    fl = ds["status_flag"][:]
                val = np.isfinite(DX[k])
                wind[k] = np.isin(fl[val], WIND_FLAGS).mean() if val.any() else np.nan
                src.append("OSI-435")
            else:
                src.append("missing")
        else:
            p = o.RAWD / "drift405" / f"drift405_{d - dt.timedelta(days=1):%Y%m%d}.nc"
            if p.exists():
                DX[k], DY[k] = _405_to_ease(p, gx, gy)
                wind[k] = 0.0
                src.append("OSI-405")
            else:
                src.append("missing")
    return days, DX, DY, gx, gy, src, wind


def load_sic(d, monthly=False):
    from pipeline.fetch import osisaf as o
    return o.sic_field(d, monthly=True) if monthly else o.sic_nearest(d)


def _write_nc(path, data, coords_extra=None, attrs=None):
    import xarray as xr
    ds = xr.Dataset({k: (dims, v) for k, (dims, v) in data.items()},
                    coords=dict(y=grid.y, x=grid.x, lat=(("y", "x"), grid.LAT.astype("f4")),
                                lon=(("y", "x"), grid.LON.astype("f4")), **(coords_extra or {})))
    ds.attrs.update({k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in (attrs or {}).items()})
    ds.attrs.update(crs="EPSG:6931", grid="EASE2-N 25 km, 360x360 crop (pipeline.grid)")
    enc = {k: {"zlib": True, "complevel": 4, "dtype": "float32"} for k in data}
    path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(path, encoding=enc)
    return path


def run_winter(W):
    d0, d1 = dt.date(W, 11, 1), dt.date(W + 1, 9, 15)
    sic0, m0 = load_sic(d0)
    sic1, m1 = load_sic(d1)
    days, DX, DY, gx, gy, src, wind = load_drift(W)
    wd = np.array([d.month in (11, 12, 1, 2, 3, 4) for d in days])
    R, Rn, ex = retention_core(sic0, sic1, grid.x, grid.y, DX, DY, gx, gy, rng=np.random.default_rng(W), winter_days=wd)
    from collections import Counter
    cnt = Counter(src)
    summer = np.array([d.month in (6, 7, 8) for d in days])
    attrs = dict(
        winter=W, seed_date=str(d0), end_date=str(d1), threshold=THRESH, particles_per_cell=N_PER,
        integrator="midpoint RK2, daily steps, bilinear (NaN-renormalised) on native 75 km EASE2 drift grid",
        sic_seed=f"{m0['product']} {m0['date_used']} {m0['source_url']}",
        sic_end=f"{m1['product']} {m1['date_used']} {m1['source_url']}",
        drift_days=dict(cnt), n_particles=ex["n_particles"], n_seed_cells_outside_drift_domain=ex["n_untracked_cells"],
        held_particle_day_frac=round(ex["held_particle_day_frac"], 4),
        held_particle_day_frac_NovApr=round(ex["held_winter_frac"], 4),
        retained_frac_all=round(float(np.nansum(R * Rn) / np.nansum(Rn)), 4),
        wind_vector_frac_JJA=round(float(np.nanmean(wind[summer])), 3) if np.isfinite(wind[summer]).any() else -1,
        note="R is endpoint-only: SIC>=0.15 at the particle's 25 km cell on 15 Sep W+1; leaving the +/-3562.5 km "
             "drift domain = not retained. Days with no drift vector at a particle: held still.",
    )
    if W == 2025:
        attrs["quality"] = ("LOWER: Jan-Sep 2026 drift is OSI-405-d NRT (48 h, 62.5 km, no free-drift gap filling, "
                            "regridded to EASE2 75 km); end SIC is OSI-438 AMSR2 ICDR")
    p = _write_nc(INTERIM / f"retention_{W}.nc",
                  {"R": (("y", "x"), R), "R_n": (("y", "x"), Rn), "exit_frac": (("y", "x"), ex["exit_frac"].astype("f4")),
                   "held_days": (("y", "x"), ex["held_days"].astype("f4")), "disp_km": (("y", "x"), ex["disp_km"].astype("f4"))},
                  attrs=attrs)
    print(f"W={W}: seeded {int(np.isfinite(R).sum())} cells, mean R {np.nanmean(R):.3f}, drift {dict(cnt)}, "
          f"held {attrs['held_particle_day_frac']:.3f} (Nov-Apr {attrs['held_particle_day_frac_NovApr']:.3f}), JJA wind-vector frac {attrs['wind_vector_frac_JJA']}", flush=True)
    return p


def build_september():
    years = list(range(2011, 2026))
    arr, meta = [], []
    for y in years:
        a, m = load_sic(dt.date(y, 9, 1), monthly=True)
        arr.append(a); meta.append(f"{y}: {m['product']} ({m.get('product_id','')} v{m.get('product_version','')})")
    S = np.stack(arr).astype("f4")
    _write_nc(INTERIM / "sic_sept.nc", {"sic_sept": (("year", "y", "x"), S)}, {"year": np.array(years)},
              attrs=dict(source="EUMETSAT OSI SAF SIC (Copyright EUMETSAT; CC BY 4.0)", per_year=meta,
                         units="fraction 0-1", note="OSI SAF monthly mean files; Sep 2025 = mean of available dailies"))
    sel = (np.array(years) >= 2012)
    ice = (np.nan_to_num(S[sel], nan=0.0) >= THRESH)
    freq = ice.mean(0).astype("f4")
    freq[np.isnan(S[sel]).all(0)] = np.nan
    _write_nc(INTERIM / "sept_presence.nc", {"freq": (("y", "x"), freq)},
              attrs=dict(years="2012-2025", threshold=THRESH, n_years=int(sel.sum()),
                         source="EUMETSAT OSI SAF SIC monthly September means (Copyright EUMETSAT)"))
    # daily endpoint fields used by retention, for other stages
    dates, D, used = [], [], []
    for W in range(2011, 2026):
        for d in (dt.date(W, 11, 1), dt.date(W + 1, 9, 15)):
            try:
                a, m = load_sic(d)
            except Exception:
                continue
            dates.append(str(d)); D.append(a); used.append(m["date_used"])
    _write_nc(INTERIM / "sic_daily_keydates.nc", {"sic": (("date", "y", "x"), np.stack(D))}, {"date": np.array(dates)},
              attrs=dict(note="OSI SAF daily SIC 12 UTC on the retention seed (1 Nov) and end (15 Sep) dates; "
                         "nearest available day used where the record has a gap", date_used=used))
    print(f"sept presence: marginal (0.2-0.8) cells {int(((freq > 0.2) & (freq < 0.8)).sum())}, always {int((freq == 1).sum())}")


def box_means(winters):
    import xarray as xr
    lon = grid.LON
    rows = {}
    for name, (a0, a1, o0, o1) in BOXES.items():
        m = (grid.LAT >= a0) & (grid.LAT <= a1) & (lon >= o0) & (lon <= o1)
        vals = []
        for W in winters:
            R = xr.open_dataset(INTERIM / f"retention_{W}.nc")["R"].values
            vals.append(float(np.nanmean(R[m])) if np.isfinite(R[m]).any() else np.nan)
        rows[name] = (vals, int(m.sum()))
    return rows


# ----------------------------------------------------------------------------- figures
def _polar(ax, field, title, cmap, vmin, vmax, label, land=None):
    import matplotlib.pyplot as plt
    ext = [grid.x[0] / 1e3 - 12.5, grid.x[-1] / 1e3 + 12.5, grid.y[-1] / 1e3 - 12.5, grid.y[0] / 1e3 + 12.5]
    if land is not None:
        ax.imshow(np.where(land, 1.0, np.nan), extent=ext, cmap="Greys", vmin=0, vmax=2, interpolation="nearest")
    im = ax.imshow(field, extent=ext, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
    for latc in (60, 70, 80):
        th = np.linspace(0, 2 * np.pi, 361)
        r = 2 * 6371.0 * np.sin(np.radians(90 - latc) / 2)
        ax.plot(r * np.cos(th), r * np.sin(th), lw=0.4, color="0.5")
    ax.set_xlim(-3600, 3600); ax.set_ylim(-3600, 3600)
    ax.set_xticks([]); ax.set_yticks([]); ax.set_title(title, fontsize=9)
    plt.colorbar(im, ax=ax, shrink=0.8, label=label)


def figures(winters):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import xarray as xr
    FIGS.mkdir(parents=True, exist_ok=True)
    land = np.isnan(xr.open_dataset(INTERIM / "sic_sept.nc")["sic_sept"].values).all(0)
    f = xr.open_dataset(INTERIM / "sept_presence.nc")["freq"].values
    fig, ax = plt.subplots(figsize=(6, 5.4))
    _polar(ax, np.where(f > 0, f, np.nan), "September ice presence (SIC>=15%), 2012-2025\nEUMETSAT OSI SAF SIC "
           "(OSI-450-a1/430-a), built 2026-11-25", "viridis", 0, 1, "fraction of years", land)
    fig.savefig(FIGS / "sept_presence.png", dpi=130, bbox_inches="tight"); plt.close(fig)
    show = [w for w in (2012, 2019, 2023) if w in winters]
    fig, axs = plt.subplots(1, len(show), figsize=(5.6 * len(show), 5))
    for ax, W in zip(np.atleast_1d(axs), show):
        R = xr.open_dataset(INTERIM / f"retention_{W}.nc")["R"].values
        _polar(ax, R, f"Retention R, winter {W}/{(W + 1) % 100:02d} (1 Nov -> 15 Sep)\nOSI SAF drift + SIC, "
               "built 2026-11-25", "magma", 0, 1, "R", land)
    fig.savefig(FIGS / "retention_winters.png", dpi=120, bbox_inches="tight"); plt.close(fig)
    Rs = np.stack([xr.open_dataset(INTERIM / f"retention_{W}.nc")["R"].values for W in winters])
    with np.errstate(invalid="ignore"):
        Rm = np.nanmean(Rs, 0)
    fig, ax = plt.subplots(figsize=(6, 5.4))
    _polar(ax, Rm, f"Mean retention R, winters {winters[0]}-{winters[-1]}\nOSI SAF drift (OSI-455/435/405) + SIC, "
           "built 2026-11-25", "magma", 0, 1, "mean R", land)
    for name, (a0, a1, o0, o1) in BOXES.items():
        lo = np.r_[np.linspace(o0, o1, 20), np.full(5, o1), np.linspace(o1, o0, 20), np.full(5, o0)]
        la = np.r_[np.full(20, a0), np.linspace(a0, a1, 5), np.full(20, a1), np.linspace(a1, a0, 5)]
        bx, by = grid._to_xy.transform(lo, la)
        ax.plot(bx / 1e3, by / 1e3, color="cyan", lw=0.8)
    fig.savefig(FIGS / "retention_mean.png", dpi=130, bbox_inches="tight"); plt.close(fig)


def main(winters=None):
    from pipeline.fetch import osisaf as o
    build_september()
    if winters is None:
        winters = []
        for W in range(2011, 2026):
            try:
                load_sic(dt.date(W, 11, 1)); load_sic(dt.date(W + 1, 9, 15))
            except Exception:
                continue
            last = dt.date(W + 1, 9, 15)
            ok = ((o.RAWD / "drift435" / f"drift435_{last:%Y%m%d}.nc").exists() if dt.date(2021, 9, 15) <= last <= dt.date(2025, 12, 31)
                  else (o.RAWD / "drift405" / f"drift405_{last - dt.timedelta(days=1):%Y%m%d}.nc").exists() if last.year >= 2026
                  else (o.RAWD / "drift455").exists())
            if ok:
                winters.append(W)
    for W in winters:
        run_winter(W)
    hist = [w for w in winters if w <= 2024]
    figures(hist)
    rows = box_means(winters)
    print("box means of R (per winter " + ",".join(map(str, winters)) + "):")
    for name, (vals, n) in rows.items():
        v = np.array(vals)
        h = v[[w <= 2024 for w in winters]]
        print(f"  {name}: n_cells={n} mean(2011-2024)={np.nanmean(h):.3f} min={np.nanmin(h):.3f} max={np.nanmax(h):.3f}"
              f" | per winter {' '.join(f'{x:.2f}' for x in v)}")
    return rows


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]] or None)
