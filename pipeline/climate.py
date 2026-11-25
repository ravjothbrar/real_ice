"""Winter climate fields on the 25 km grid from cached ERA5 daily fields (pipeline/fetch/era5.py).

climate_W.nc  fdd       K day, sum of max(T_f - T, 0), T_f = -1.8 C, 1 Nov W .. 15 May W+1
              fdd_jan   same, 1 Jan W+1 .. 15 May W+1 (flooding window starts in January)
              fdd_mar   same, 1 Jan W+1 .. 31 Mar W+1
              melt_days days with daily-mean T2m > 0 C, 1 May .. 15 Sep W+1 (138 days)
              snowfall  m water equivalent, 1 Nov W .. 30 Apr W+1
cambridge_bay_climate.csv  the same at the approximate Real Ice site 69.05N, 105.10W.

Daily mean T2m = mean of 00 and 12 UTC analyses. Interpolation from the N320 reduced Gaussian
points: linear in longitude along the two bracketing Gaussian rows, then linear in latitude
("bilinear" on the native grid).
"""
import csv, datetime as dt, json, time
import numpy as np, xarray as xr
from scipy import sparse
from pipeline import http, grid
from pipeline.fetch import era5

T_F = -1.8
ROOT = http.RAW.parents[1]
INTERIM = ROOT / "data" / "interim"
FIGS = ROOT / "eval" / "figs"
SITE = (-105.10, 69.05)       # approximate Real Ice site; exact coordinates not public
HAMLET = (-105.06, 69.117)


def weights(lon_t, lat_t):
    """Sparse (n_target x n_native) bilinear weights on the reduced Gaussian north points."""
    lat, lon, n = era5.north_index()
    rows_lat, start = np.unique(-lat, return_index=True)       # ascending in -lat = north->south
    rows_lat = -rows_lat
    order = np.argsort(start); rows_lat = rows_lat[order]; start = start[order]
    nlon = np.diff(np.r_[start, n])
    assert np.allclose(lon[start], 0.0)
    lt = np.asarray(lat_t, float).ravel(); ln = np.mod(np.asarray(lon_t, float).ravel(), 360)
    R, C, V = [], [], []
    # row index: r0 = last row with lat >= target (north side), r1 = r0 + 1 (south side)
    r0 = np.searchsorted(-rows_lat, -lt, side="right") - 1
    for k in range(lt.size):
        a = r0[k]
        if a < 0:                         # north of the first Gaussian row: use that row only
            pairs = [(0, 1.0)]
        elif a >= len(rows_lat) - 1:      # south of the last row we hold (45N): no data
            continue
        else:
            wl = (rows_lat[a] - lt[k]) / (rows_lat[a] - rows_lat[a + 1])
            pairs = [(a, 1 - wl), (a + 1, wl)]
        for r, wr in pairs:
            p = ln[k] / (360.0 / nlon[r]); k0 = int(np.floor(p)) % nlon[r]; k1 = (k0 + 1) % nlon[r]; f = p - np.floor(p)
            R += [k, k]; C += [start[r] + k0, start[r] + k1]; V += [wr * (1 - f), wr * f]
    Wm = sparse.csr_matrix((V, (R, C)), shape=(lt.size, n))
    # rows with no support (south of ~45.1N) must become NaN, not 0 K: scale them by NaN
    ok = np.asarray(Wm.sum(1)).ravel() > 0.999
    return Wm, ok


def _load(var, months):
    days, vals = [], []
    for (y, m) in months:
        p = era5.OUT / var / f"{y}{m:02d}.npz"
        if not p.exists():
            pp = era5.OUT / var / f"{y}{m:02d}_partial.npz"
            if not pp.exists():
                break
            p = pp
        z = np.load(p)
        days += [dt.date.fromisoformat(d) for d in z["days"]]; vals.append(z["v"])
    if not vals:
        return [], None
    return days, np.concatenate(vals)


def _ar_tail():
    ps = sorted((era5.OUT / "ar_t2m").glob("*.npz")) if (era5.OUT / "ar_t2m").exists() else []
    if not ps:
        return [], None
    z = np.load(ps[-1])
    from scipy.interpolate import RegularGridInterpolator
    lat = z["lat"][::-1]; lon = np.r_[z["lon"], 360.0]
    out = []
    pts_g = np.c_[grid.LAT.ravel(), np.mod(grid.LON.ravel(), 360)]
    pts_s = np.array([[SITE[1], SITE[0] % 360]])
    for v in z["v"]:
        a = np.concatenate([v, v[:, :1]], 1)[::-1]
        f = RegularGridInterpolator((lat, lon), a, bounds_error=False, fill_value=np.nan)
        out.append(np.r_[f(pts_g), f(pts_s)])
    return [dt.date.fromisoformat(d) for d in z["days"]], np.array(out)


def _sum_window(days, arr, d0, d1, fn):
    idx = [i for i, d in enumerate(days) if d0 <= d <= d1]
    return (fn(arr[idx]).sum(0) if idx else None), len(idx)


def winter(W, Wg, Ws, log=print):
    tm, sm = era5.months_for(W)
    tdays, t = _load("t2m", tm)
    sdays, s = _load("sf", sm)
    src = "co"
    if W >= 2026 and (not tdays or tdays[-1] < dt.date(W, 11, 30)):
        ad, av = _ar_tail()
        if ad:
            # combine any co days with AR tail days (AR values already on grid + site)
            co_g = (t @ Wg.T) if t is not None else np.zeros((0, grid.CROP * grid.CROP))
            co_s = (t @ Ws.T) if t is not None else np.zeros((0, 1))
            full = np.r_[np.c_[co_g, co_s], av] if t is not None else av
            tdays = (tdays or []) + ad
            TC = full - 273.15
            src = "co+ar" if t is not None else "ar"
        else:
            TC = None
    else:
        TC = None if t is None else np.c_[t @ Wg.T, t @ Ws.T] - 273.15
    if TC is None:
        return None
    fdd_f = lambda x: np.maximum(T_F - x, 0)
    out, counts = {}, {}
    out["fdd"], counts["fdd"] = _sum_window(tdays, TC, dt.date(W, 11, 1), dt.date(W + 1, 5, 15), fdd_f)
    out["fdd_jan"], counts["fdd_jan"] = _sum_window(tdays, TC, dt.date(W + 1, 1, 1), dt.date(W + 1, 5, 15), fdd_f)
    out["fdd_mar"], counts["fdd_mar"] = _sum_window(tdays, TC, dt.date(W + 1, 1, 1), dt.date(W + 1, 3, 31), fdd_f)
    out["melt_days"], counts["melt_days"] = _sum_window(tdays, TC, dt.date(W + 1, 5, 1), dt.date(W + 1, 9, 15), lambda x: (x > 0).astype(float))
    if s is not None:
        S = np.c_[s @ Wg.T, s @ Ws.T]
        out["snowfall"], counts["snowfall"] = _sum_window(sdays, S, dt.date(W, 11, 1), dt.date(W + 1, 4, 30), lambda x: x)
    else:
        out["snowfall"], counts["snowfall"] = None, 0
    full_n = {"fdd": 196, "fdd_jan": 135, "fdd_mar": 90, "melt_days": 138, "snowfall": 181}
    if (W + 1) % 4 == 0:
        full_n.update(fdd=197, fdd_jan=136, fdd_mar=91, snowfall=182)
    partial = {k: counts[k] < full_n[k] for k in full_n}
    return out, counts, partial, tdays[-1], src


def build(winters=range(2011, 2027), log=print):
    INTERIM.mkdir(parents=True, exist_ok=True)
    Wg, okg = weights(grid.LON, grid.LAT)
    Ws, _ = weights([SITE[0]], [SITE[1]])
    rows = []
    for W in winters:
        r = winter(W, Wg, Ws, log)
        if r is None:
            log(f"winter {W}: no data cached"); continue
        out, counts, partial, last, src = r
        any_full = not partial["fdd"]
        if W < 2026 and partial["fdd"]:
            log(f"winter {W}: incomplete ({counts}); skipped"); continue
        units = {"fdd": "K day", "fdd_jan": "K day", "fdd_mar": "K day", "melt_days": "days", "snowfall": "m water equivalent"}
        longn = {"fdd": "freezing degree days, 1 Nov W - 15 May W+1, T_f = -1.8 C",
                 "fdd_jan": "freezing degree days, 1 Jan - 15 May W+1", "fdd_mar": "freezing degree days, 1 Jan - 31 Mar W+1",
                 "melt_days": "days with daily-mean T2m > 0 C, 1 May - 15 Sep W+1",
                 "snowfall": "total snowfall 1 Nov W - 30 Apr W+1 (from 4 hourly samples/day x 6)"}
        dv = {}
        for k, v in out.items():
            if v is None or partial[k] and W < 2026:
                arr = np.full(grid.CROP * grid.CROP, np.nan)
            elif partial[k] and counts[k] == 0:
                arr = np.full(grid.CROP * grid.CROP, np.nan)
            else:
                arr = v[:-1].astype(float).copy()
                arr[~okg] = np.nan
            dv[k] = (("y", "x"), arr.reshape(grid.CROP, grid.CROP).astype(np.float32),
                     {"units": units[k], "long_name": longn[k], "n_days": counts[k], "partial": int(partial[k])})
        ds = xr.Dataset(dv, coords={"lat": (("y", "x"), grid.LAT.astype(np.float32)), "lon": (("y", "x"), grid.LON.astype(np.float32))},
                        attrs={"winter": W, "source": "ERA5 (ECMWF/C3S) via Google ARCO-ERA5, co/ native N320 store" + (" + ar/ 0.25 deg store for the ERA5T tail" if "ar" in src else ""),
                               "t2m_sampling": "daily mean = mean of 00 and 12 UTC analyses for 1 Nov-15 May; 16 May-15 Sep "
                               + ("also 00+12 UTC" if W == 2024 else "one analysis per day alternating 00/12 UTC (transfer budget)"),
                               "snowfall_sampling": "24 x one hourly accumulation per day, valid hour rotating through 24 h; per-point monthly totals within about +/-20% (IQR) of a 4-sample/day estimate, unbiased (Nov 2024 check)", "T_f_C": T_F,
                               "last_day": str(last), "partial_winter": int(any(partial.values())),
                               "south_limit": "NaN south of the last Gaussian row held (~45.1N)",
                               "bias_note": "ERA5 has a warm bias over sea ice in cold, clear conditions (Wang et al. 2019, The Cryosphere 13, 1661-1679, doi:10.5194/tc-13-1661-2019, up to several K) -> FDD likely biased low.",
                               "built": time.strftime("%Y-%m-%d")})
        enc = {v: {"zlib": True, "complevel": 4} for v in ds.data_vars}
        ds.to_netcdf(INTERIM / f"climate_{W}.nc", encoding=enc)
        site = {k: (None if (v is None or counts[k] == 0 or (partial[k] and W < 2026)) else float(v[-1])) for k, v in out.items()}
        rows.append({"winter": W, "label": f"{W}/{str(W + 1)[2:]}", **{k: (round(x, 4) if k == "snowfall" and x is not None else (round(x, 1) if x is not None else "")) for k, x in site.items()},
                     "partial": int(any(partial.values())), "last_day": str(last),
                     "fdd_days": counts["fdd"]})
        log(f"winter {W}: site fdd {site['fdd']}, fdd_jan {site['fdd_jan']}, melt {site['melt_days']}, snow {site['snowfall']}, partial={partial}")
    p = INTERIM / "cambridge_bay_climate.csv"
    with open(p, "w", newline="") as f:
        f.write(f"# ERA5 (ARCO-ERA5) at approx. Real Ice site {SITE[1]}N {abs(SITE[0])}W (~7 km from hamlet {HAMLET[1]}N {abs(HAMLET[0])}W; exact site coordinates not public). fdd K day T_f=-1.8C; snowfall m w.e. Built {time.strftime('%Y-%m-%d')}\n")
        w = csv.DictWriter(f, fieldnames=["winter", "label", "fdd", "fdd_jan", "fdd_mar", "melt_days", "snowfall", "partial", "last_day", "fdd_days"])
        w.writeheader(); w.writerows(rows)
    return rows


def plots(W=2024):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIGS.mkdir(parents=True, exist_ok=True)
    st = xr.open_dataset(INTERIM / "static.nc")
    land = st.land.values == 1
    def show(ax, a, title, cmap, vmin=None, vmax=None):
        a = np.where(land, np.nan, a)
        im = ax.imshow(a, cmap=cmap, vmin=vmin, vmax=vmax); ax.contour(land, [0.5], colors="k", linewidths=0.3)
        ax.set_title(title, fontsize=8); ax.set_xticks([]); ax.set_yticks([]); plt.colorbar(im, ax=ax, shrink=0.7)
    c = xr.open_dataset(INTERIM / f"climate_{W}.nc")
    fig, axs = plt.subplots(2, 2, figsize=(10, 10))
    show(axs[0, 0], c.fdd.values, f"FDD (K day) 1 Nov {W}-15 May {W+1}", "Blues", 0)
    show(axs[0, 1], c.fdd_jan.values, f"FDD (K day) 1 Jan-15 May {W+1}", "Blues", 0)
    show(axs[1, 0], c.melt_days.values, f"melt days (T2m>0C) 1 May-15 Sep {W+1}", "Reds", 0, 138)
    show(axs[1, 1], c.snowfall.values, f"snowfall (m w.e.) 1 Nov {W}-30 Apr {W+1}", "Purples", 0, 0.5)
    i, j = grid.lonlat_to_ij(*SITE)
    for ax in axs.ravel(): ax.plot(j, i, "r+", ms=8)
    fig.suptitle(f"ERA5 (C3S/ECMWF, via ARCO-ERA5), winter {W}/{W+1}; red + = approx. Cambridge Bay site. Built {time.strftime('%Y-%m-%d')}", fontsize=9)
    fig.tight_layout(); fig.savefig(FIGS / f"climate_{W}.png", dpi=110); plt.close(fig)
    # static
    fig, axs = plt.subplots(1, 3, figsize=(15, 5.2))
    axs[0].imshow(st.land_frac.values, cmap="Greys"); axs[0].set_title("land fraction (Natural Earth 50m)", fontsize=8)
    ex = st.excl_settlement.values + 2 * st.excl_shipping.values
    axs[1].imshow(np.where(ex > 0, ex, np.nan), cmap="autumn"); axs[1].contour(land, [0.5], colors="k", linewidths=0.3)
    axs[1].set_title("exclusions: settlements 50 km (NE 10m) / shipping 50 km (hand-curated, not ASTD)", fontsize=8)
    im = axs[2].imshow(np.where(st.region.values > 0, st.region.values, np.nan), cmap="tab10", vmin=0.5, vmax=10.5)
    axs[2].contour(land, [0.5], colors="k", linewidths=0.3); axs[2].set_title("atlas regions 1-7 (lon/lat boxes)", fontsize=8)
    plt.colorbar(im, ax=axs[2], shrink=0.7)
    for ax in axs: ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle(f"static.nc: Natural Earth (public domain); hand-curated corridors. Built {time.strftime('%Y-%m-%d')}", fontsize=9)
    fig.tight_layout(); fig.savefig(FIGS / "static.png", dpi=110); plt.close(fig)
    # piomas
    pw = min(W, 2024)
    pm = xr.open_dataset(INTERIM / f"piomas_{pw}.nc")
    fig, axs = plt.subplots(1, 3, figsize=(15, 5.2))
    show(axs[0], pm.h_nov.values, f"PIOMAS h Nov {pw} (m)", "viridis", 0, 4)
    show(axs[1], pm.h_apr.values, f"PIOMAS h Apr {pw+1} (m)", "viridis", 0, 4)
    show(axs[2], pm.snow_apr.values, f"PIOMAS snow Apr {pw+1} (m)", "magma", 0, 0.3)
    fig.suptitle(f"PIOMAS v2.1 (PSC/APL-UW) MODEL output, regridded. Built {time.strftime('%Y-%m-%d')}", fontsize=9)
    fig.tight_layout(); fig.savefig(FIGS / f"piomas_{pw}.png", dpi=110); plt.close(fig)
    # Cambridge Bay series
    import csv as _c
    rows = [r for r in _c.DictReader(l for l in open(INTERIM / "cambridge_bay_climate.csv") if not l.startswith("#"))]
    ws = [int(r["winter"]) for r in rows if r["fdd"] and r["partial"] == "0"]
    fd = [float(r["fdd"]) for r in rows if r["fdd"] and r["partial"] == "0"]
    fj = [float(r["fdd_jan"]) for r in rows if r["fdd"] and r["partial"] == "0"]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(ws, fd, color="#4a7bb7", label="FDD 1 Nov-15 May"); ax.bar(ws, fj, color="#a6c8e8", label="FDD 1 Jan-15 May")
    if 2024 in ws: ax.annotate("2024/25 paper winter", (2024, fd[ws.index(2024)]), ha="center", va="bottom", fontsize=8)
    ax.set_xlabel("winter W (starts Nov W)"); ax.set_ylabel("K day"); ax.legend(fontsize=8)
    ax.set_title(f"ERA5 FDD at approx. Cambridge Bay site {SITE[1]}N {abs(SITE[0])}W (site approximate). Built {time.strftime('%Y-%m-%d')}", fontsize=8)
    fig.tight_layout(); fig.savefig(FIGS / "cambridge_bay_fdd.png", dpi=110); plt.close(fig)


if __name__ == "__main__":
    import sys
    build()
    plots()
