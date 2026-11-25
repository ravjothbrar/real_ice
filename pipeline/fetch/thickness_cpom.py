"""CPOM CryoSat-2 Arctic sea-ice thickness, NTC monthly, 5 km sparse grid (EPSG:3411 points).

Source page: https://www.cpom.ucl.ac.uk/seaice/download.php?region=Arctic
The brief's EOCIS URL pattern (www.cpom.ucl.ac.uk/eocis/...) returns 404 (checked 25 Nov 2026);
this is the official CPOM sea-ice portal product that is reachable. Individual monthly .nc files
are served by the portal's download_handler (same endpoint as its per-year .tar.gz archives), so we
fetch only the months we need (Nov of W, Apr of W+1) instead of whole-year archives.

Run: python -m pipeline.fetch.thickness_cpom
"""
import tarfile
from urllib.parse import quote
from pipeline import http

BASE = "https://www.cpom.ucl.ac.uk/seaice/download_handler.php"
PAGE = "https://www.cpom.ucl.ac.uk/seaice/download.php?region=Arctic"
NAME = "cpom_ntc_arco_sea_ice_thickness_{ym}_5km_sparse_grid_v001.nc"
WINTERS = range(2011, 2026)  # W = 2011..2025
# Apr 2026 was first fetched inside the 2026 archive while inspecting the product layout.
TAR_2026 = "cpom_ntc_arco_sea_ice_thickness_2026_5km_sparse_grid.tar.gz"


def url_for(ym):
    return f"{BASE}?file={quote(ym[:4] + '/' + NAME.format(ym=ym), safe='')}&type=ntc&region=arco"


def path_for(ym):
    return http.RAW / "cpom" / NAME.format(ym=ym)


def months():
    out = []
    for w in WINTERS:
        out += [f"{w}11", f"{w + 1}04"]
    return out


def fetch():
    s = http.session()
    files, missing = [], []
    for ym in months():
        p = path_for(ym)
        if not p.exists() and ym.startswith("2026"):
            tp = http.RAW / "cpom" / TAR_2026
            if tp.exists():
                with tarfile.open(tp) as t:
                    t.extract(NAME.format(ym=ym), tp.parent, filter="data")
        if not p.exists():
            try:
                http.get(url_for(ym), f"cpom/{p.name}", s=s)
            except Exception as e:  # never invent: record what is missing
                missing.append(f"{ym}: {e}")
                continue
        files.append({"name": p.name, "url": url_for(ym), "sha256": http.sha256(p), "bytes": p.stat().st_size})
    tp = http.RAW / "cpom" / TAR_2026
    if tp.exists():
        files.append({"name": tp.name, "url": f"{BASE}?file=2026%2F{TAR_2026}&type=ntc&region=arco",
                      "sha256": http.sha256(tp), "bytes": tp.stat().st_size})
    http.record(
        "thickness_cpom",
        dataset="CPOM CryoSat-2 Arctic sea ice thickness, NTC (Non-Time-Critical) monthly, 5 km sparse grid, v001",
        url=PAGE,
        doi=None,
        licence=("No licence stated on the CPOM sea-ice portal pages (download.php, methodology.php, contacts.php) "
                 "or in the NetCDF global attributes (checked 2026-11-25). Treat as 'credit CPOM / UCL, ESA CryoSat-2'; "
                 "confirm terms with CPOM before redistribution."),
        institution="Centre for Polar Observation and Modelling (CPOM), UCL; ESA CryoSat-2",
        files=files,
        missing=missing,
        notes=("Brief's EOCIS URL pattern https://www.cpom.ucl.ac.uk/eocis/seaice/data/EOCIS-SEAICE-L3C-SITHICK-CS2-5KM-YYYYMM-fv1.0.nc "
               "returns 404; /eocis/ tree absent. Cryo-TEMPO page redirects to cryosat.mssl.ucl.ac.uk (not allow-listed). "
               "Used CPOM seaice portal NTC monthly files (Warren-99 snow climatology, halved on FYI)."),
    )
    return files, missing


if __name__ == "__main__":
    f, m = fetch()
    print(len(f), "files,", sum(x["bytes"] for x in f) / 1e6, "MB; missing:", m)
