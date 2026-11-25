"""Start-of-winter sea-ice thickness layers on the 25 km EASE2 grid (brief section 5 step 1).

Inputs (fetched by pipeline.fetch.thickness_*):
  CPOM  CryoSat-2 NTC monthly 5 km sparse points (EPSG:3411)  -> bin mean onto 25 km
  Petty IS2SMGPSIT-V1 daily 25 km on EPSG:3411 grid          -> monthly mean, nearest-neighbour
  AWI   CS2SMOS weekly L4                                       -> unreachable here (see fetcher)

h0    = November mean of winter W (start of winter). October retrievals are biased thin
        (brief section 4), so October is not used.
h_apr = April mean of W+1 (end of growth season).
h0_unc = product's own uncertainty, regridded (mean); see per-file attrs for what that is.

Outputs data/interim/thick_{cpom,petty}_W.nc, thick_disagreement.nc; figures eval/figs/thick_*.png.
Run: python -m pipeline.thickness
"""
import pathlib, time
import numpy as np
import xarray as xr
import pyproj
from scipy.interpolate import RegularGridInterpolator
from pipeline import grid

ROOT = pathlib.Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
FIGS = ROOT / "eval" / "figs"
MIN_PTS_CPOM = 3        # 5 km CPOM points required per 25 km cell (of ~25 possible)
MIN_DAYS_PETTY = 0.5    # fraction of sampled days that must be valid for a monthly mean
H_MAX = 8.0             # 25 km cell means above this are treated as retrieval artefacts (coast/land contamination)
H0_CHOICE = "November mean (month 11 of W); October excluded as thin-ice retrievals are biased thin"
TODAY = time.strftime("%Y-%m-%d")


def _coords():
    return dict(lat=(("y", "x"), grid.LAT.astype("float32")), lon=(("y", "x"), grid.LON.astype("float32")),
                y=("y", grid.y), x=("x", grid.x))


def _qc(data, attrs):
    """Drop physically implausible cell means (> H_MAX m) and log how many were dropped."""
    for k in ("h0", "h_apr"):
        if k in data:
            neg = data[k] < 0  # retrieval noise (CPOM) / GP undershoot (Petty) around zero
            attrs[f"qc_{k}_cells_negative_clipped_to_0"] = int(neg.sum())
            data[k] = np.where(neg, 0.0, data[k])
            bad = data[k] > H_MAX
            attrs[f"qc_{k}_cells_above_{H_MAX:g}m_set_nan"] = int(bad.sum())
            data[k] = np.where(bad, np.nan, data[k])
            if k == "h0" and "h0_unc" in data:
                data["h0_unc"] = np.where(np.isfinite(data["h0"]), data["h0_unc"], np.nan)
    return data


def _write(path, data, attrs, var_attrs):
    data = _qc(dict(data), attrs)
    ds = xr.Dataset({k: (("y", "x"), v.astype("float32")) for k, v in data.items()}, coords=_coords())
    for k, a in var_attrs.items():
        if k in ds:
            ds[k].attrs.update(a)
    ds.attrs.update(attrs)
    ds.attrs.update(grid="EASE2-N 25 km (EPSG:6931), 360x360, see pipeline/grid.py", created=TODAY)
    path.parent.mkdir(parents=True, exist_ok=True)
    enc = {k: {"zlib": True, "complevel": 4, "_FillValue": np.float32(np.nan)} for k in data}
    ds.to_netcdf(path, encoding=enc)
    return ds


# ---------------------------------------------------------------- CPOM
def _cpom_month(p):
    with xr.open_dataset(p) as ds:
        lon, lat = ds.longitude.values, ds.latitude.values
        th, sd = ds.thickness.values.astype(float), ds.thk_stdev.values.astype(float)
    cnt = _count(lon, lat)
    h = grid.regrid_points(lon, lat, th)
    u = grid.regrid_points(lon, lat, sd)
    bad = ~(cnt >= MIN_PTS_CPOM)
    h[bad] = np.nan; u[bad] = np.nan
    return h, u, cnt


def _count(lon, lat):
    i, j = grid.lonlat_to_ij(lon, lat)
    i = np.rint(i).astype(int); j = np.rint(j).astype(int)
    ok = (i >= 0) & (i < grid.CROP) & (j >= 0) & (j < grid.CROP)
    return np.bincount(i[ok] * grid.CROP + j[ok], minlength=grid.CROP ** 2).reshape(grid.CROP, grid.CROP)


def build_cpom():
    from pipeline.fetch import thickness_cpom as fc
    fc.fetch()
    out = []
    nrt = fc.http.RAW / "cpom" / fc.NRT_2026
    for w in list(fc.WINTERS) + [2026]:
        partial = w == 2026
        pn = nrt if partial else fc.path_for(f"{w}11")
        pa = fc.path_for(f"{w + 1}04")
        if not pn.exists():
            continue
        h0, u0, c0 = _cpom_month(pn)
        ha = _cpom_month(pa)[0] if pa.exists() else np.full_like(h0, np.nan)
        extra = {}
        if partial:
            extra = dict(partial=1, h0_month="2026-11-02..2026-11-15 (NRT 14-day product)", h_apr_month="not yet observed",
                         source="CPOM CryoSat-2 Arctic sea ice thickness, NRT 14-day 5 km sparse grid v001 (initial orbit, "
                                "not final quality; UCL/CPOM, ESA)",
                         nrt_file=fc.NRT_2026)
        attrs = dict(
            source="CPOM CryoSat-2 Arctic sea ice thickness, NTC monthly, 5 km sparse grid v001 (UCL/CPOM, ESA)",
            source_url="https://www.cpom.ucl.ac.uk/seaice/download.php?region=Arctic",
            winter=w, h0_choice=H0_CHOICE, h0_month=f"{w}-11", h_apr_month=f"{w + 1}-04",
            regrid=f"bin mean of 5 km points per 25 km cell, cells with < {MIN_PTS_CPOM} points set NaN; "
                   "negative cell means clipped to 0 (see qc_* attrs)",
            snow="Warren-99 climatology (halved on first-year ice), as in the CPOM product",
            caveats="CryoSat-2 pole hole north of ~88N is NaN; radar thickness over thin/young ice is noisy in November",
            partial=0)
        attrs.update(extra)
        va = dict(h0=dict(units="m", long_name="start-of-winter sea ice thickness (November mean)"),
                  h0_unc=dict(units="m", long_name="mean within-cell standard deviation of thickness (CPOM thk_stdev)",
                              comment="CPOM provides no retrieval-uncertainty variable; thk_stdev is the spread of "
                                      "thickness measurements at each 5 km point. It is a variability proxy, not a "
                                      "formal uncertainty, and excludes systematic snow-depth error."),
                  h_apr=dict(units="m", long_name="April mean sea ice thickness (end of growth season)"))
        p = INTERIM / f"thick_cpom_{w}.nc"
        _write(p, dict(h0=h0, h0_unc=u0, h_apr=ha), attrs, va)
        out.append(w)
    return out


# ---------------------------------------------------------------- Petty
# ice_thickness in IS2SMGPSIT is the grid-cell mean (open water counts as 0); ice_volume_per_grid_cell_area is
# ice_thickness / sea_ice_conc masked where SIC < 0.15, i.e. the thickness of the ice itself, which is what CPOM
# reports (CPOM only uses echoes where SIC > 75%). We use the latter for h0/h_apr so the products are comparable.
PETTY_VARS = ["ice_thickness", "ice_thickness_unc", "ice_volume_per_grid_cell_area"]
PETTY_H = "ice_volume_per_grid_cell_area"


def _petty_floe_unc(d):
    """GP thickness s.d. scaled from cell-mean to ice-only thickness (x 1/SIC), per day."""
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.where(d["ice_thickness"] > 0.01, d[PETTY_H] / d["ice_thickness"], np.nan)
    return dict(u=d["ice_thickness_unc"] * r)


def _petty_sampler(xs, ys, proj4):
    """Nearest-neighbour sampler from the source EPSG:3411 25 km grid to our cell centres."""
    t = pyproj.Transformer.from_crs(grid.EPSG, pyproj.CRS.from_proj4(proj4), always_xy=True)
    px, py = t.transform(grid.XX, grid.YY)
    sx, sy = np.asarray(xs, float), np.asarray(ys, float)
    flip = sy[0] > sy[-1]
    if flip:
        sy = sy[::-1]
    pts = np.stack([py.ravel(), px.ravel()], -1)

    def f(v):
        v = v[::-1] if flip else v
        r = RegularGridInterpolator((sy, sx), v, method="nearest", bounds_error=False, fill_value=np.nan)
        return r(pts).reshape(grid.CROP, grid.CROP)
    return f


def _petty_mean(d, v):
    a = d[v]
    nvalid = np.isfinite(a).sum(0)
    with np.errstate(invalid="ignore"):
        m = np.nanmean(a, 0) if a.ndim == 3 else a
    if a.ndim == 3:
        m[nvalid < MIN_DAYS_PETTY * a.shape[0]] = np.nan
    return m


def build_petty():
    from pipeline.fetch import thickness_petty as fp
    months = [m for w in fp.WINTERS for m in (f"{w}11", f"{w + 1}04")]
    data, missing, _ = fp.fetch(PETTY_VARS, months)
    proj4 = "+proj=stere +lat_0=90 +lat_ts=70 +lon_0=-45 +k=1 +x_0=0 +y_0=0 +a=6378273 +b=6356889.449 +units=m +no_defs"
    out = []
    for w in fp.WINTERS:
        dn, da = data.get(f"{w}11"), data.get(f"{w + 1}04")
        if dn is None:
            continue
        samp = _petty_sampler(dn["x"], dn["y"], proj4)
        h0 = samp(_petty_mean(dn, PETTY_H))
        u0 = samp(_petty_mean(_petty_floe_unc(dn), "u"))
        u0[~np.isfinite(h0)] = np.nan
        ha = samp(_petty_mean(da, PETTY_H)) if da is not None else np.full_like(h0, np.nan)
        days = [k + 1 for k in dn["_days_read"]]
        attrs = dict(
            source="IS2SMGPSIT-V1 (v0.1): daily 25 km Arctic sea ice thickness from fused ICESat-2 and SMOS/SMAP, "
                   "Petty, Cardinale, Tsamados, Gregory, Cabaj",
            doi="10.5281/zenodo.22147361", licence="cc-by-4.0",
            winter=w, h0_choice=H0_CHOICE, h0_month=f"{w}-11", h_apr_month=f"{w + 1}-04",
            days_sampled=f"days {days} of each month (every {fp.DAY_STRIDE}rd day, read via HTTP Range)",
            variable=f"h0/h_apr from {PETTY_H} (ice_thickness / sea_ice_conc, masked SIC < 0.15): thickness of the "
                     "ice itself, comparable with CPOM; NOT the cell-mean ice_thickness",
            regrid="monthly mean of sampled daily fields (NaN where < 50% of days valid), then nearest "
                   "neighbour from NSIDC polar stereographic 25 km (EPSG:3411) to EASE2 25 km",
            caveats="Canadian Arctic Archipelago has elevated uncertainty (provider note); April is at the edge of "
                    "the GP training window (provider note)")
        va = dict(h0=dict(units="m", long_name="start-of-winter sea ice thickness (November mean)"),
                  h0_unc=dict(units="m", long_name="mean GP posterior standard deviation of thickness (ice_thickness_unc)",
                              comment="ice_thickness_unc is for the cell-mean thickness; scaled by 1/SIC per day "
                                      "(= ice_volume_per_grid_cell_area / ice_thickness) to match ice-only h0"),
                  h_apr=dict(units="m", long_name="April mean sea ice thickness (end of growth season)"))
        _write(INTERIM / f"thick_petty_{w}.nc", dict(h0=h0, h0_unc=u0, h_apr=ha), attrs, va)
        out.append(w)
    return out, missing


# ---------------------------------------------------------------- AWI
def build_awi():
    from pipeline.fetch import thickness_awi as fa
    url, log = fa.fetch()
    if url is None:
        print("AWI CS2SMOS unreachable; thick_awi_W.nc not written:\n  " + "\n  ".join(log))
        return []
    # A reachable listing has not been seen from this environment, so no reader is written against an
    # unverified layout. Fail loudly instead of guessing.
    raise NotImplementedError(f"AWI listing reachable at {url}: write the CS2SMOS reader against the real layout")


# ---------------------------------------------------------------- disagreement
def _load(prod):
    out = {}
    for p in sorted(INTERIM.glob(f"thick_{prod}_*.nc")):
        w = int(p.stem.rsplit("_", 1)[1])
        with xr.open_dataset(p) as ds:
            out[w] = ds.h0.values
    return out


def build_disagreement():
    prods = {k: _load(k) for k in ("cpom", "petty", "awi")}
    data, attrs, summary = {}, {}, {}
    for a, b in (("cpom", "petty"), ("cpom", "awi"), ("petty", "awi")):
        common = sorted(set(prods[a]) & set(prods[b]))
        key = f"{a}_{b}"
        if not common:
            attrs[f"{key}_winters"] = "none (product missing)"
            continue
        d = np.stack([np.abs(prods[a][w] - prods[b][w]) for w in common])
        n = np.isfinite(d).sum(0)
        with np.errstate(invalid="ignore"):
            m = np.nanmean(d, 0)
        m[n == 0] = np.nan
        data[f"absdiff_{key}"] = m
        data[f"n_{key}"] = n.astype("float32")
        v = m[np.isfinite(m)]
        s = dict(winters=common, n_cells=int(v.size), median_m=float(np.median(v)), p90_m=float(np.percentile(v, 90)),
                 mean_m=float(v.mean()))
        # signed bias over all cell-winters, for context
        sd = np.stack([prods[a][w] - prods[b][w] for w in common])
        s["mean_signed_diff_m"] = float(np.nanmean(sd))
        summary[key] = s
        attrs[f"{key}_winters"] = ",".join(map(str, common))
        attrs[f"{key}_median_abs_diff_m"] = round(s["median_m"], 4)
        attrs[f"{key}_p90_abs_diff_m"] = round(s["p90_m"], 4)
    attrs.update(description="Per pair of thickness products: mean over common winters of |h0_a - h0_b| per cell "
                             "(h0 = November mean), and n = number of winters with both valid. Summary numbers are "
                             "the median and 90th percentile over cells with n >= 1.", h0_choice=H0_CHOICE)
    va = {k: dict(units="m" if k.startswith("absdiff") else "1") for k in data}
    if data:
        _write(INTERIM / "thick_disagreement.nc", data, attrs, va)
    return summary


# ---------------------------------------------------------------- figures
def _plot(arr, title, path, vmax=4.0, cmap="viridis", label="m"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 6))
    land = None
    p = INTERIM / "static.nc"
    if p.exists():
        with xr.open_dataset(p) as ds:
            land = ds.land.values if "land" in ds else None
    if land is not None:
        ax.imshow(np.where(land > 0, 1, np.nan), cmap="Greys", vmin=0, vmax=2, interpolation="nearest")
    im = ax.imshow(arr, vmin=0, vmax=vmax, cmap=cmap, interpolation="nearest")
    ax.contour(grid.LAT, levels=[60, 70, 80], colors="0.6", linewidths=0.5)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(title, fontsize=9)
    fig.colorbar(im, ax=ax, shrink=0.8, label=label)
    fig.text(0.01, 0.01, "EASE2-N 25 km polar view; lat circles 60/70/80N", fontsize=7, color="0.4")
    FIGS.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)


def figures(cpom_w, petty_w):
    if cpom_w:
        w = max(cpom_w)
        with xr.open_dataset(INTERIM / f"thick_cpom_{w}.nc") as ds:
            kind = "NRT 14-day, partial season" if ds.attrs.get("partial") else "NTC monthly"
            _plot(ds.h0.values, f"CPOM CryoSat-2 {kind}: h0 = {ds.attrs['h0_month']} mean thickness\n"
                                f"(accessed {TODAY})", FIGS / f"thick_cpom_{w}.png")
        w = max(x for x in cpom_w if x < 2026)
        with xr.open_dataset(INTERIM / f"thick_cpom_{w}.nc") as ds:
            _plot(ds.h0.values, f"CPOM CryoSat-2 NTC monthly: h0 = Nov {w} mean thickness\n(accessed {TODAY})",
                  FIGS / "thick_cpom.png")
    if petty_w:
        w = max(petty_w)
        with xr.open_dataset(INTERIM / f"thick_petty_{w}.nc") as ds:
            _plot(ds.h0.values, f"IS2SMGPSIT-V1 (Petty et al.): h0 = Nov {w} mean thickness\n"
                                f"doi:10.5281/zenodo.22147361 (accessed {TODAY})", FIGS / "thick_petty.png")
    p = INTERIM / "thick_disagreement.nc"
    if p.exists():
        with xr.open_dataset(p) as ds:
            for k in [v for v in ds.data_vars if v.startswith("absdiff_")]:
                pair = k[len("absdiff_"):]
                _plot(ds[k].values, f"|h0 {pair.replace('_', ' - ')}| mean over winters "
                                    f"{ds.attrs.get(pair + '_winters')}\nNov thickness (accessed {TODAY})",
                      FIGS / f"thick_disagreement_{pair}.png", vmax=2.0, cmap="magma")


def main():
    cw = build_cpom()
    print("CPOM winters:", cw)
    pw, miss = build_petty()
    print("Petty winters:", pw, "missing months:", miss)
    aw = build_awi()
    print("AWI winters:", aw)
    s = build_disagreement()
    for k, v in s.items():
        print(f"{k}: winters {v['winters'][0]}-{v['winters'][-1]} ({len(v['winters'])}), cells {v['n_cells']}, "
              f"median |dh0| {v['median_m']:.3f} m, p90 {v['p90_m']:.3f} m, mean signed {v['mean_signed_diff_m']:+.3f} m")
    figures(cw, pw)
    return cw, pw, aw, s


if __name__ == "__main__":
    main()
