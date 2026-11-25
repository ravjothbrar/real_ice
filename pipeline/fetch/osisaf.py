"""OSI SAF sea-ice concentration and drift from MET Norway THREDDS (OPeNDAP subsets).

Products (all on thredds.met.no, chosen 25 Nov 2026):
  SIC   2011-01..2020-12  OSI-450-a1 CDR v3.1   (DOI 10.15770/EUM_SAF_OSI_0023)  EASE2-N 25 km, 432x432
        2021-01..2025-09  OSI-430-a  ICDR v3.0 (continuation of OSI-450-a; production stopped 2025-09-30)
        2025-10..         OSI-438    ICDR v3.0 AMSR2 (only OSI SAF EASE2 25 km climate-grade SIC after 430-a stopped)
  Drift 1991..2020-12-31  OSI-455 CDR v1.0      (DOI 10.15770/EUM_SAF_OSI_0012)  EASE2-N 75 km, 144x144, 24 h
        2021-01..2025-12  OSI-435 ICDR v0.1 "demonstrational" (same algorithm/grid as OSI-455, incl. summer free drift)
        2026-01..         OSI-405-d NRT v3.1 low-res drift, 62.5 km polar stereographic, 48 h, no free-drift gap filling

The OSI SAF 25 km EASE2 SIC grid is the full NH EASE2 grid (+/-5400 km, xc[0] = -5387.5 km); our grid
(pipeline.grid) is the central +/-4500 km block, i.e. SIC[36:396, 36:396] maps exactly cell for cell
(asserted on the x/y coordinate values below). Drift is cropped to +/-3600 km (75 km cells 24..119),
which holds every cell that carries ice on 1 Nov or 15 Sep; a particle that leaves that box counts as exported.

Politeness: identified UA (written to ~/.dodsrc for netCDF-C OPeNDAP, requests for catalogs), one request at a
time, >= 1 s between requests, every subset cached under data/raw/osisaf/ and never re-fetched, a byte ledger
that refuses to go past 1 GB.
"""
import datetime as dt
import json
import os
import pathlib
import re
import sys
import time

import numpy as np
import netCDF4

from pipeline import http
from pipeline import grid

THREDDS = "https://thredds.met.no/thredds"
CAT = THREDDS + "/catalog/osisaf/met.no/"
DAP = THREDDS + "/dodsC/"
RAWD = http.RAW / "osisaf"
LEDGER = RAWD / "_ledger.json"
BUDGET = 1_000_000_000
SIC_OFF = 36                     # 432-cell OSI grid -> our 360 crop
DR_LO, DR_HI = 24, 120           # 75 km drift crop (96 cells, +/-3600 km)

LICENCE_SIC = ("CC BY 4.0 (http://creativecommons.org/licenses/by/4.0/, file attribute 'license'); "
               "credit 'EUMETSAT OSI SAF'.")
LICENCE_DRIFT_CDR = ("EUMETSAT OSI SAF terms (file attribute 'license'): free of charge to every user; 'Copyright "
                     "EUMETSAT' must be displayed under each product shown; no warranty.")
LICENCE_405 = "CC BY 4.0 (file attribute 'license')."


# ----------------------------------------------------------------------------- plumbing
def _dodsrc():
    """netCDF-C reads HTTP.USERAGENT from ~/.dodsrc (or ./.dodsrc); make sure our UA is there."""
    line = f"HTTP.USERAGENT={http.UA}\n"
    for p in (pathlib.Path.home() / ".dodsrc",):
        txt = p.read_text() if p.exists() else ""
        if line.strip() not in txt:
            p.write_text("".join(l + "\n" for l in txt.splitlines() if not l.startswith("HTTP.USERAGENT")) + line)


def _wait():
    w = 1.0 - (time.time() - http._last[0])
    if w > 0:
        time.sleep(w)


def _done():
    http._last[0] = time.time()


def _ledger():
    return json.loads(LEDGER.read_text()) if LEDGER.exists() else {}


def _charge(key, nbytes):
    led = _ledger()
    led[key] = int(nbytes)
    tot = sum(led.values())
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(led, indent=0))
    if tot > BUDGET:
        raise RuntimeError(f"OSI SAF transfer ledger at {tot/1e6:.0f} MB > 1 GB budget; stop and ask")
    return tot


def total_mb():
    return sum(_ledger().values()) / 1e6


def catalog(path):
    """List dataset urlPaths in a THREDDS catalog directory (NH files only); cached."""
    dest = f"osisaf/catalog/{path.strip('/').replace('/', '_')}.xml"
    p = http.get(CAT + path.strip("/") + "/catalog.xml", dest)
    _charge(dest, p.stat().st_size)
    return sorted(set(re.findall(r'urlPath="([^"]+_nh_[^"]+\.nc)"', p.read_text())))


def _open(urlpath, tries=4):
    _dodsrc()
    for k in range(tries):
        _wait()
        try:
            return netCDF4.Dataset(DAP + urlpath)
        except OSError as e:
            _done()
            if k == tries - 1:
                raise
            print("  retry", urlpath, e, file=sys.stderr)
            time.sleep(10 * (k + 1))


def _write(path, coords, data, attrs):
    """Write a small local NetCDF (zlib) from dicts of numpy arrays."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    with netCDF4.Dataset(tmp, "w") as o:
        for k, v in coords.items():
            o.createDimension(k, len(v))
            o.createVariable(k, "f8", (k,))[:] = v
        for k, (dims, v) in data.items():
            fill = -1e10 if np.issubdtype(v.dtype, np.floating) else None
            var = o.createVariable(k, v.dtype, dims, zlib=True, complevel=4, fill_value=fill)
            var[:] = v
        o.setncatts({k: str(v) for k, v in attrs.items()})
    tmp.rename(path)
    return path


# ----------------------------------------------------------------------------- SIC
def _sic_dir(d, monthly=False):
    """THREDDS directory + product label for a date."""
    if d <= dt.date(2020, 12, 31):
        base, prod = "reprocessed/ice/conc_450a1_files", "OSI-450-a1 v3.1"
    elif d <= dt.date(2025, 9, 30):
        base, prod = "reprocessed/ice/conc_cra_files", "OSI-430-a v3.0"
    else:
        base, prod = "reprocessed/ice/conc_438_files", "OSI-438 v3.0 (AMSR2)"
    return (f"{base}/monthly/{d.year}" if monthly else f"{base}/{d.year}/{d.month:02d}"), prod


def _pick(files, stamp):
    hits = [f for f in files if f.endswith(stamp + ".nc") or (stamp + "1200.nc") in f]
    hits.sort(key=lambda f: "icdrft" in f)  # prefer final over fast-track
    return hits[0] if hits else None


def _crop_sic(ds):
    xc, yc = ds["xc"][:], ds["yc"][:]
    s = slice(SIC_OFF, SIC_OFF + grid.CROP)
    fac = 1000.0 if str(ds["xc"].units).strip() == "km" else 1.0
    assert np.allclose(xc[s] * fac, grid.x) and np.allclose(yc[s] * fac, grid.y), "SIC grid offset mismatch"
    v = ds["ice_conc"][0, s, s]                       # scale_factor applied -> percent
    return (np.ma.filled(v.astype("f4"), np.nan) / 100.0).clip(0, 1).astype("f4")


def sic_field(d, monthly=False, product=None):
    """SIC (0-1) on our 360x360 grid for a date (daily at 12 UTC) or a month. Cached. Returns (array, meta)."""
    d = dt.date(d.year, d.month, 1 if monthly else d.day)
    folder, prod = _sic_dir(d, monthly)
    if product == "438":
        folder, prod = (f"reprocessed/ice/conc_438_files/monthly/{d.year}" if monthly else
                        f"reprocessed/ice/conc_438_files/{d.year}/{d.month:02d}"), "OSI-438 v3.0 (AMSR2)"
    tag = d.strftime("%Y%m") if monthly else d.strftime("%Y%m%d")
    sfx = "_438" if product == "438" else ""
    dest = RAWD / ("sic_monthly" if monthly else "sic_daily") / f"sic_{tag}{sfx}.nc"
    if not dest.exists():
        f = _pick(catalog(folder), tag)
        if f is None and monthly:
            # e.g. Sep 2025: OSI-430-a stopped 2025-09-30 and no monthly file was issued -> mean of the dailies
            n = (dt.date(d.year + d.month // 12, d.month % 12 + 1, 1) - d).days
            fs = []
            for k in range(n):
                try:
                    fs.append(sic_field(d + dt.timedelta(days=k), product=product))
                except FileNotFoundError:
                    pass  # gaps in the daily record (e.g. 25-28 Sep 2025)
            with np.errstate(invalid="ignore"):
                a = np.nanmean(np.stack([x[0] for x in fs]), 0).astype("f4")
            attrs = dict(fs[0][1], product=fs[0][1]["product"] +
                         f" (monthly mean of {len(fs)}/{n} available daily files; no monthly file issued)",
                         source_url=fs[0][1]["source_url"] + f" ... {len(fs)} daily files")
            _write(dest, {"y": grid.y, "x": grid.x}, {"sic": (("y", "x"), a)}, attrs)
            return a, attrs
        if f is None:
            raise FileNotFoundError(f"no NH SIC file for {tag} in {folder}")
        ds = _open(f)
        try:
            a = _crop_sic(ds)
            attrs = dict(source_url=DAP + f, product=prod, product_id=getattr(ds, "product_id", ""),
                         product_version=getattr(ds, "product_version", ""), doi=getattr(ds, "doi", ""),
                         license=getattr(ds, "license", ""))
        finally:
            ds.close(); _done()
        _write(dest, {"y": grid.y, "x": grid.x}, {"sic": (("y", "x"), a)}, attrs)
        _charge(str(dest.relative_to(http.RAW)), grid.CROP ** 2 * 4)
    with netCDF4.Dataset(dest) as ds:
        return np.ma.filled(ds["sic"][:], np.nan).astype("f4"), {k: ds.getncattr(k) for k in ds.ncattrs()}


def sic_nearest(d, maxlag=5, product=None):
    """Daily SIC on date d, or the nearest available day within +/-maxlag (earlier day wins ties).
    The record has gaps (e.g. OSI-430-a 12-17 Sep 2024, 25-28 Sep 2025). meta['date_used'] says which."""
    for lag in [0] + [s * k for k in range(1, maxlag + 1) for s in (-1, 1)]:
        e = d + dt.timedelta(days=lag)
        try:
            a, m = sic_field(e, product=product)
        except FileNotFoundError:
            continue
        return a, dict(m, date_used=str(e), date_requested=str(d))
    raise FileNotFoundError(f"no SIC within {maxlag} days of {d}")


# ----------------------------------------------------------------------------- drift
DRIFT_455_AGG = "osisaf/met.no/reprocessed/ice/drift_455m_nh_agg"
DR_X = (-5362.5 + 75.0 * np.arange(DR_LO, DR_HI)) * 1000.0    # metres, EASE2 (EPSG:6931)
DR_Y = (5362.5 - 75.0 * np.arange(DR_LO, DR_HI)) * 1000.0


def _check_drift_xy(ds):
    xc, yc = ds["xc"][DR_LO:DR_HI] * 1000.0, ds["yc"][DR_LO:DR_HI] * 1000.0
    assert np.allclose(xc, DR_X) and np.allclose(yc, DR_Y), "drift grid mismatch"


def drift_455(W):
    """OSI-455 daily drift slice for winter W (end-of-motion dates 2 Nov W .. min(15 Sep W+1, 31 Dec 2020))."""
    d0, d1 = dt.date(W, 11, 2), min(dt.date(W + 1, 9, 15), dt.date(2020, 12, 31))
    dest = RAWD / "drift455" / f"drift455_{d0:%Y%m%d}_{d1:%Y%m%d}.nc"
    if not dest.exists():
        ds = _open(DRIFT_455_AGG)
        try:
            _check_drift_xy(ds)
            t = netCDF4.num2date(ds["time"][:], ds["time"].units)
            days = np.array([dt.date(x.year, x.month, x.day) for x in t])
            i0, i1 = int(np.where(days == d0)[0][0]), int(np.where(days == d1)[0][0]) + 1
            out = {}
            for v in ("dX", "dY", "status_flag"):
                _wait()
                a = ds[v][i0:i1, DR_LO:DR_HI, DR_LO:DR_HI]
                _done()
                out[v] = (("time", "y", "x"), np.ma.filled(a.astype("f4"), np.nan) if v != "status_flag"
                          else np.ma.filled(a, -1).astype("i1"))
            tt = np.array([(x - dt.date(1970, 1, 1)).days for x in days[i0:i1]], "f8")
            attrs = dict(source_url=DAP + DRIFT_455_AGG, product_id=ds.product_id, product_version=ds.product_version,
                         doi=ds.doi, license=ds.license, time_units="days since 1970-01-01 (end of 24 h motion, 12 UTC)",
                         dX_units="km")
        finally:
            ds.close(); _done()
        _write(dest, {"time": tt, "y": DR_Y, "x": DR_X}, out, attrs)
        _charge(str(dest.relative_to(http.RAW)), (i1 - i0) * 96 * 96 * 9)
    return dest


def drift_435_day(d):
    """OSI-435 ICDR daily drift with end of motion on date d (12 UTC). None if no file."""
    dest = RAWD / "drift435" / f"drift435_{d:%Y%m%d}.nc"
    miss = dest.with_suffix(".missing")
    if miss.exists():
        return None
    if not dest.exists():
        f = _pick(catalog(f"ice/drift/435/merged/{d.year}/{d.month:02d}"), d.strftime("%Y%m%d") + "1200")
        if f is None:
            miss.parent.mkdir(parents=True, exist_ok=True); miss.write_text("no file in catalog\n")
            return None
        ds = _open(f)
        try:
            _check_drift_xy(ds)
            out = {v: (("y", "x"), np.ma.filled(ds[v][0, DR_LO:DR_HI, DR_LO:DR_HI].astype("f4"), np.nan))
                   for v in ("dX", "dY")}
            out["status_flag"] = (("y", "x"), np.ma.filled(ds["status_flag"][0, DR_LO:DR_HI, DR_LO:DR_HI], -1).astype("i1"))
            attrs = dict(source_url=DAP + f, product_id=ds.product_id, product_version=ds.product_version,
                         license=ds.license, dX_units="km")
        finally:
            ds.close(); _done()
        _write(dest, {"y": DR_Y, "x": DR_X}, out, attrs)
        _charge(str(dest.relative_to(http.RAW)), 96 * 96 * 9)
    return dest


def drift_405_file(d):
    """OSI-405-d 48 h drift starting 12 UTC on date d (ends d+2). Full 119x177 polar-stereo field. None if absent."""
    dest = RAWD / "drift405" / f"drift405_{d:%Y%m%d}.nc"
    miss = dest.with_suffix(".missing")
    if miss.exists():
        return None
    if not dest.exists():
        e = d + dt.timedelta(days=2)
        f = _pick(catalog(f"ice/drift_lr/merged/{e.year}/{e.month:02d}"),
                  f"{d:%Y%m%d}1200-{e:%Y%m%d}1200")
        if f is None:
            miss.parent.mkdir(parents=True, exist_ok=True); miss.write_text("no file in catalog\n")
            return None
        ds = _open(f)
        try:
            xc, yc = ds["xc"][:] * 1000.0, ds["yc"][:] * 1000.0
            out = {v: (("y", "x"), np.ma.filled(ds[v][0].astype("f4"), np.nan)) for v in ("dX", "dY")}
            out["status_flag"] = (("y", "x"), np.ma.filled(ds["status_flag"][0], -1).astype("i1"))
            attrs = dict(source_url=DAP + f, product_id=ds.product_id, product_version=ds.product_version,
                         license=ds.license, proj4=ds["Polar_Stereographic_Grid"].proj4_string, dX_units="km",
                         span="48 h")
        finally:
            ds.close(); _done()
        _write(dest, {"y": yc, "x": xc}, out, attrs)
        _charge(str(dest.relative_to(http.RAW)), out["dX"][1].size * 9 + 3000)
    return dest


# ----------------------------------------------------------------------------- driver
WINTERS = list(range(2011, 2026))


def fetch_all(winters=WINTERS):
    # SIC: monthly Septembers 2011..2025 (+2026 from OSI-438), daily 1 Nov and 15 Sep endpoints
    for y in range(2011, 2027):
        sic_field(dt.date(y, 9, 1), monthly=True)
    for W in winters:
        sic_nearest(dt.date(W, 11, 1))
        sic_nearest(dt.date(W + 1, 9, 15))
    # overlap check of the OSI-438 AMSR2 record against OSI-430-a (Sep 2025)
    sic_field(dt.date(2025, 9, 15), product="438")
    sic_field(dt.date(2025, 9, 1), monthly=True, product="438")
    print(f"SIC done, ledger {total_mb():.1f} MB", flush=True)
    for W in winters:
        if W <= 2020:
            drift_455(W)
        d = max(dt.date(W, 11, 2), dt.date(2021, 1, 1))
        while d <= dt.date(W + 1, 9, 15):
            if d <= dt.date(2025, 12, 31):
                drift_435_day(d)
            else:
                drift_405_file(d - dt.timedelta(days=1))
            d += dt.timedelta(days=1)
        print(f"drift W={W} done, ledger {total_mb():.1f} MB", flush=True)
    write_provenance()


def _manifest(sub):
    rows = []
    for p in sorted((RAWD / sub).glob("*.nc")):
        rows.append(dict(name=str(p.relative_to(http.RAW)), sha256=http.sha256(p), bytes=p.stat().st_size))
    return rows


def write_provenance():
    led = _ledger()
    sic = _manifest("sic_daily") + _manifest("sic_monthly")
    http.record(
        "osisaf_sic",
        dataset="EUMETSAT OSI SAF sea-ice concentration: OSI-450-a1 CDR v3.1 (2011-2020), OSI-430-a ICDR v3.0 "
                "(2021-01..2025-09), OSI-438 ICDR v3.0 AMSR2 (2025-10..2026-09); EASE2-N 25 km",
        url=[CAT + "reprocessed/ice/conc_450a1_files/catalog.html", CAT + "reprocessed/ice/conc_cra_files/catalog.html",
             CAT + "reprocessed/ice/conc_438_files/catalog.html"],
        doi="10.15770/EUM_SAF_OSI_0023 (OSI-450-a1); OSI-430-a / OSI-438 ICDRs: see osi-saf.eumetsat.int",
        licence=LICENCE_SIC,
        files=sic,
        notes="OPeNDAP subsets of ice_conc cropped [36:396,36:396] to the atlas grid (exact cell match, asserted). "
              "Monthly means are OSI SAF monthly files. Daily = 12 UTC fields on 1 Nov and 15 Sep.",
        transfer_mb=round(sum(v for k, v in led.items() if "sic" in k or "conc" in k) / 1e6, 2),
    )
    files = []
    for sub in ("drift455", "drift435", "drift405"):
        m = _manifest(sub)
        mp = RAWD / f"{sub}_MANIFEST.json"
        mp.write_text(json.dumps(m, indent=0))
        files.append(dict(name=str(mp.relative_to(http.RAW)), sha256=http.sha256(mp), bytes=mp.stat().st_size,
                          n_files=len(m), total_bytes=sum(r["bytes"] for r in m)))
    http.record(
        "osisaf_drift",
        dataset="EUMETSAT OSI SAF sea-ice drift: OSI-455 CDR v1.0 (to 2020-12-31), OSI-435 ICDR v0.1 demonstrational "
                "(2021-01..2025-12), OSI-405-d NRT LR v3.1 (2026)",
        url=[DAP + DRIFT_455_AGG, CAT + "ice/drift/435/catalog.html", CAT + "ice/drift_lr/merged/catalog.html"],
        doi="10.15770/EUM_SAF_OSI_0012 (OSI-455); OSI-435 and OSI-405 have no DOI in file metadata",
        licence=f"OSI-455/OSI-435: {LICENCE_DRIFT_CDR} OSI-405-d: {LICENCE_405}",
        files=files,
        notes="dX, dY, status_flag only. OSI-455/435 cropped to 75 km cells 24..119 (+/-3600 km, EASE2). "
              "OSI-405 full 62.5 km polar-stereographic field. Per-file sha256 in the *_MANIFEST.json files.",
        transfer_mb=round(sum(v for k, v in led.items() if "drift" in k) / 1e6, 2),
    )
    print(f"total OSI SAF transfer {total_mb():.1f} MB")


if __name__ == "__main__":
    ws = [int(a) for a in sys.argv[1:]] or WINTERS
    fetch_all(ws)
