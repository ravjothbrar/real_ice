"""Polite, cached HTTP for all fetchers: identified UA, single thread, rate-limited, never re-download."""
import time, hashlib, json, pathlib, requests

UA = "SurvivalGapAtlas/0.1 (independent student project; https://ravjothbrar.com)"
RAW = pathlib.Path(__file__).resolve().parents[1] / "data" / "raw"
_last = [0.0]
MAX_BYTES = 1_000_000_000  # brief rule 4: ask before anything over 1 GB


def session():
    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s


def get(url, dest, min_interval=1.0, max_bytes=MAX_BYTES, s=None):
    """Download url to data/raw/<dest> once. Returns path. Refuses files over max_bytes."""
    dest = RAW / dest
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    wait = min_interval - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    s = s or session()
    with s.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        size = int(r.headers.get("Content-Length", 0))
        if size > max_bytes:
            raise RuntimeError(f"{url} is {size/1e9:.2f} GB; over limit, ask Ravjoth first")
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        tmp.rename(dest)
    _last[0] = time.time()
    return dest


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def record(name, **meta):
    """Write data/provenance/<name>.json (merged into data/PROVENANCE.json by pipeline.provenance)."""
    p = RAW.parent / "provenance" / f"{name}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    meta.setdefault("access_date", time.strftime("%Y-%m-%d"))
    p.write_text(json.dumps(meta, indent=2))
    return p
