"""Petty et al. IS2SMGPSIT-V1 (ICESat-2 + SMOS/SMAP Gaussian-process fusion), daily 25 km, 2018-2025.

Authors credited per the brief: Alek Petty, Cardinale, Tsamados, Gregory, Cabaj (Zenodo record lists
Alek Petty as creator). Zenodo record 22147361, DOI 10.5281/zenodo.22147361, licence read from the
record metadata.

Monthly files GPSat_multivar_YYYYMM.nc are ~150 MB each; we need only Nov (W) and Apr (W+1) and only
the thickness + its uncertainty, so we open the remote file lazily with h5py over HTTP Range requests
(RangeFile below) and read just those variables. Every fetched block is cached in a sparse local file
under data/raw/petty/ so nothing is downloaded twice.

Run: python -m pipeline.fetch.thickness_petty
"""
import io, json, time, pathlib
import numpy as np
from pipeline import http

RECORD = 22147361
DOI = "10.5281/zenodo.22147361"
API = f"https://zenodo.org/api/records/{RECORD}"
FILE_URL = API + "/files/{name}/content"
WINTERS = range(2018, 2025)  # W = 2018..2024 (Nov W .. Apr W+1)
BLOCK = 1 << 20


class RangeFile(io.RawIOBase):
    """Read-only seekable file over HTTP Range requests (polite: UA, single thread, >=1 s spacing,
    backoff on 5xx). Fetched 1 MB blocks persist in <cache>.sparse with a .blocks.json index."""

    def __init__(self, url, cache_path, size=None, session=None, block=BLOCK):
        self.url, self.block = url, block
        self.s = session or http.session()
        self.cache = pathlib.Path(cache_path)
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        self.meta = self.cache.with_suffix(self.cache.suffix + ".blocks.json")
        m = json.loads(self.meta.read_text()) if self.meta.exists() else {}
        self.have = set(m.get("blocks", []))
        self.size = size or m.get("size") or self._head()
        if not self.cache.exists():
            with open(self.cache, "wb") as f:
                f.truncate(self.size)
        self.fh = open(self.cache, "r+b")
        self.pos = 0
        self.bytes_fetched = 0

    def _head(self):
        return int(self._req(0, 0).headers["Content-Range"].split("/")[1])

    def _req(self, a, b):
        err = None
        for k in range(6):
            wait = 1.0 - (time.time() - http._last[0])
            if wait > 0:
                time.sleep(wait)
            try:
                r = self.s.get(self.url, headers={"Range": f"bytes={a}-{b}"}, timeout=180)
                http._last[0] = time.time()
                if r.status_code == 206:
                    return r
                if r.status_code < 500:
                    r.raise_for_status()
                    raise RuntimeError(f"server ignored Range ({r.status_code})")
                err = f"HTTP {r.status_code}"
            except Exception as e:
                http._last[0] = time.time()
                err = e
            time.sleep(2 ** (k + 1))
        raise RuntimeError(f"giving up on {self.url} {a}-{b}: {err}")

    def _ensure(self, a, b):
        need = [i for i in range(a // self.block, (b - 1) // self.block + 1) if i not in self.have]
        runs = []
        for i in need:
            if runs and i == runs[-1][1] + 1 and runs[-1][1] - runs[-1][0] < 31:
                runs[-1][1] = i
            else:
                runs.append([i, i])
        for i0, i1 in runs:
            lo, hi = i0 * self.block, min((i1 + 1) * self.block, self.size) - 1
            r = self._req(lo, hi)
            if len(r.content) != hi - lo + 1:
                raise RuntimeError("short range read")
            self.fh.seek(lo)
            self.fh.write(r.content)
            self.bytes_fetched += len(r.content)
            self.have.update(range(i0, i1 + 1))
            self.fh.flush()
            self.meta.write_text(json.dumps({"url": self.url, "size": self.size, "block": self.block,
                                             "blocks": sorted(self.have)}))

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def readinto(self, buf):
        n = min(len(buf), self.size - self.pos)
        if n <= 0:
            return 0
        self._ensure(self.pos, self.pos + n)
        self.fh.seek(self.pos)
        got = self.fh.readinto(memoryview(buf)[:n])
        self.pos += got
        return got

    def close(self):
        if not self.closed:
            self.fh.close()
        super().close()


def record_meta(s=None):
    p = http.RAW / "petty" / "zenodo_record.json"
    if not p.exists():
        s = s or http.session()
        for k in range(5):
            r = s.get(API, headers={"Accept": "application/json"}, timeout=60)
            if r.ok:
                break
            time.sleep(2 ** (k + 1))
        r.raise_for_status()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(r.text)
    return json.loads(p.read_text())


def open_month(ym, meta, s=None):
    """h5py.File over the remote monthly file (lazy). Returns (h5file, RangeFile) or None if absent."""
    import h5py
    name = f"GPSat_multivar_{ym}.nc"
    f = {x["key"]: x for x in meta["files"]}.get(name)
    if f is None:
        return None
    rf = RangeFile(FILE_URL.format(name=name), http.RAW / "petty" / (name + ".sparse"), size=f["size"], session=s)
    return h5py.File(rf, "r"), rf


VARS = None  # resolved by pipeline.thickness after inspecting the file (thickness + uncertainty)


def fetch(read_vars, months):
    """Read `read_vars` for each YYYYMM in `months` (cached). Returns {ym: {var: array, ...}}."""
    s = http.session()
    meta = record_meta(s)
    out, used, missing, fetched = {}, [], [], 0
    for ym in months:
        o = open_month(ym, meta, s)
        if o is None:
            missing.append(ym)
            continue
        h, rf = o
        d = {}
        for v in read_vars:
            ds = h[v]
            arr = ds[()].astype("float64")
            fv = ds.attrs.get("_FillValue")
            if fv is not None:
                arr[arr == np.asarray(fv).item()] = np.nan
            d[v] = arr
        for c in ("x", "y", "lon", "lat", "time", "longitude", "latitude"):
            if c in h and c not in d:
                d[c] = h[c][()]
        d["_attrs"] = {v: {k: (a.decode() if isinstance(a, bytes) else a) for k, a in h[v].attrs.items()
                           if k not in ("DIMENSION_LIST", "REFERENCE_LIST")} for v in read_vars}
        out[ym] = d
        fetched += rf.bytes_fetched
        name = f"GPSat_multivar_{ym}.nc"
        z = {x["key"]: x for x in meta["files"]}[name]
        used.append({"name": name, "url": FILE_URL.format(name=name), "bytes": z["size"],
                     "zenodo_checksum": z["checksum"],
                     "bytes_read_by_range": len(rf.have) * BLOCK,
                     "sha256": None, "sha256_note": "file read partially via HTTP Range; full-file checksum is the Zenodo md5"})
        h.close(); rf.close()
    m = meta["metadata"]
    http.record(
        "thickness_petty",
        dataset=m["title"] + f" ({m.get('version')})",
        url=f"https://zenodo.org/records/{RECORD}",
        doi=DOI,
        licence=(m.get("license") or {}).get("id"),
        licence_source="Zenodo record metadata 'license' field",
        authors="Alek Petty, Cardinale, Tsamados, Gregory, Cabaj (author list per brief; Zenodo creator: "
                + "; ".join(c["name"] for c in m["creators"]) + "). ESSD preprint essd-2026-700.",
        publication_date=m.get("publication_date"),
        files=used,
        missing=missing,
        variables_read=list(read_vars),
        notes="Only the listed variables were read via HTTP Range requests; no full-file downloads.",
    )
    return out, missing, fetched


if __name__ == "__main__":
    months = [m for w in WINTERS for m in (f"{w}11", f"{w + 1}04")]
    import sys
    vs = sys.argv[1:] or ["sea_ice_thickness"]
    o, miss, n = fetch(vs, months)
    print(len(o), "months; missing", miss, "; fetched", n / 1e6, "MB")
