"""AWI CryoSat-2/SMOS merged sea-ice thickness (CS2SMOS), weekly L4, 25 km EASE2, winter only.

Docs: https://spaces.awi.de/display/CS2SMOS. Distribution: anonymous FTP ftp.awi.de
(/sea_ice/product/cryosat2_smos/...), and ESA SMOS dissemination (ftps://smos-diss.eo.esa.int, EO Sign-In).

This module probes every route allowed in this environment and records what happened. It never
invents data: if nothing is reachable, it writes a provenance entry with status "unavailable" and
pipeline.thickness skips thick_awi_W.nc.

Probe result 25 Nov 2026 (this environment, via the allow-listing HTTPS proxy):
  - https://ftp.awi.de/...       : proxy CONNECT allowed, TLS handshake reset by the server
                                   (ftp.awi.de does not serve HTTPS)
  - ftp://ftp.awi.de/...         : FTP is not carried by the HTTPS-only proxy (no DNS)
  - http://ftp.awi.de/...        : plain HTTP is not carried by the proxy
  - https://spaces.awi.de/...    : refused by the proxy (403, host not allow-listed)
  - ESA smos-diss.eo.esa.int      : FTPS + EO Sign-In; host not allow-listed, no account configured
  - earth.esa.int catalogue page : reachable (documentation + licence only, no data)

Run: python -m pipeline.fetch.thickness_awi
"""
import re
from pipeline import http

CANDIDATES = [
    "https://ftp.awi.de/sea_ice/product/cryosat2_smos/",
    "https://ftp.awi.de/sea_ice/",
    "ftp://ftp.awi.de/sea_ice/product/cryosat2_smos/",
]
ESA_PAGE = "https://earth.esa.int/eogateway/catalog/smos-cryosat-l4-sea-ice-thickness"
ESA_TC = "https://earth.esa.int/eogateway/documents/20142/1564626/Terms-and-Conditions-for-the-use-of-ESA-Data.pdf"


def probe():
    """Try each candidate once (polite: >=1 s apart). Returns (reachable_url or None, log)."""
    import time
    s = http.session()
    log = []
    for u in CANDIDATES:
        time.sleep(1.0)
        if not u.startswith("https://"):
            log.append(f"{u}: skipped (only HTTPS is carried by this environment's proxy)")
            continue
        try:
            r = s.get(u, timeout=30)
            log.append(f"{u}: HTTP {r.status_code}")
            if r.ok:
                return u, log, r.text
        except Exception as e:
            log.append(f"{u}: {type(e).__name__}: {str(e)[:160]}")
    return None, log, None


def list_files(index_html):
    """*_l4sit.nc names in an Apache-style directory listing (used only if a listing is reachable)."""
    return sorted(set(re.findall(r'href="([^"]*l4sit[^"]*\.nc)"', index_html)))


def fetch():
    url, log, _ = probe()
    http.record(
        "thickness_awi",
        dataset="AWI CryoSat-2/SMOS merged sea ice thickness (CS2SMOS), weekly L4, Northern Hemisphere",
        url="https://spaces.awi.de/display/CS2SMOS",
        doi=None,
        licence=("Not read: AWI data pages unreachable from this environment. ESA catalogue page "
                 f"({ESA_PAGE}) links the ESA data T&C: {ESA_TC}"),
        status="unavailable" if url is None else "reachable-not-fetched",
        files=[],
        probe_log=log,
        notes=("No CS2SMOS data fetched. ftp.awi.de serves FTP only (TLS reset on 443); the proxy carries HTTPS only. "
               "ESA route needs EO Sign-In (FTPS, smos-diss.eo.esa.int, not allow-listed). "
               "thick_awi_W.nc is therefore NOT produced; the 2026/27 current-season thickness is missing."),
    )
    return url, log


if __name__ == "__main__":
    u, log = fetch()
    print("reachable:", u)
    print("\n".join(log))
