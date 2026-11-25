"""ERA5 2 m temperature and snowfall north of 45N from Google's public ARCO-ERA5 copy, cheaply.

Route (no CDS key): gs://gcp-public-data-arco-era5/co/ (read over https://storage.googleapis.com).
  * co/single-level-reanalysis.zarr-v2 / t2m : hourly analysis on the native N320 reduced Gaussian
    grid, one zarr chunk = one hour x all 542,080 points, blosc(lz4, byte-shuffle), 512 KB blocks.
  * co/single-level-forecast.zarr-v2 / sf    : snowfall, forecasts from 06 and 18 UTC, steps 0-18 h,
    each step a 1-hour accumulation (verified: not cumulative).
  * ar/full_37-1h-0p25deg-chunk-1.zarr-v3    : 0.25 deg hourly, used only for days the co store
    does not yet hold (ERA5T tail, winter 2026 partial).

Why this is cheap: points are ordered north -> south, so the 81,209 points north of 45N are the
first 62% of the first blosc block. Blosc splits each block into 4 byte-streams (one per byte of
the float32); we fetch, with HTTP Range requests, only the leading part of streams 1-3 and decode
the LZ4 prefix ourselves. Byte 0 (lowest 8 mantissa bits, <= 0.004 K at 250 K; <= 1e-7 relative
for snowfall) is replaced by its midpoint 0x80. Transfer ~110 KB per hourly field instead of
~2.3 MB for a full 0.25 deg chunk.

Sampling (transfer budget < 1.5 GB): T2m daily mean = mean of 00 and 12 UTC for 1 Nov - 15 May (two
samples 12 h apart cancel the first diurnal harmonic at every longitude); 16 May - 15 Sep one analysis
per day alternating 00/12 UTC (winter 2024 summer was cached earlier at 2/day). Snowfall: the store holds
1-hour accumulations per forecast step, so the daily total = 24 x one hourly value whose valid hour
rotates through all 24 hours over 24 days.

Cache: data/raw/era5/<var>/<YYYYMM>.npz (daily fields on the native points), never re-downloaded.
"""
import struct, time, json, pathlib, datetime as dt
import numpy as np
import requests
from pipeline import http

GCS = "https://storage.googleapis.com/gcp-public-data-arco-era5"
CO_T2M = "co/single-level-reanalysis.zarr-v2/t2m"
CO_SF = "co/single-level-forecast.zarr-v2/sf"
AR = "ar/full_37-1h-0p25deg-chunk-1.zarr-v3"
OUT = http.RAW / "era5"
NBLK = 131072          # elements per 512 KB blosc block (float32)
LAT_MIN = 45.0
T0 = dt.datetime(1900, 1, 1)
STATS = {"bytes": 0, "requests": 0}
MIN_INTERVAL = 0.02    # s between requests; single thread, keep-alive session

_S = None


def _sess():
    global _S
    if _S is None:
        _S = http.session()
    return _S


_last = [0.0]


def _range(path, start, end):
    """GET bytes [start, end) of an object (end exclusive). Retries politely."""
    for attempt in range(6):
        w = MIN_INTERVAL - (time.time() - _last[0])
        if w > 0:
            time.sleep(w)
        try:
            r = _sess().get(f"{GCS}/{path}", headers={"Range": f"bytes={start}-{end - 1}"}, timeout=60)
            _last[0] = time.time()
            if r.status_code in (200, 206):
                STATS["bytes"] += len(r.content); STATS["requests"] += 1
                return r.content
            if r.status_code == 416:
                return b""
            if r.status_code == 404:
                raise FileNotFoundError(path)
        except (requests.ConnectionError, requests.Timeout):
            pass
        time.sleep(2 ** attempt)
    raise RuntimeError(f"failed {path} {start}-{end}")


def lz4_prefix(src, nout):
    """Decode an LZ4 *block* stream, stopping after nout output bytes or when the (possibly
    truncated) input runs out. Returns bytearray (may be shorter than nout if input too short)."""
    out = bytearray()
    i, n = 0, len(src)
    while i < n and len(out) < nout:
        tok = src[i]; i += 1
        lit = tok >> 4
        if lit == 15:
            while i < n:
                b = src[i]; i += 1; lit += b
                if b != 255:
                    break
        if i + lit > n:                      # truncated literal run: take what we have
            out += src[i:n]; break
        out += src[i:i + lit]; i += lit
        if len(out) >= nout or i + 2 > n:
            break
        off = src[i] | (src[i + 1] << 8); i += 2
        ml = tok & 15
        if ml == 15:
            ok = False
            while i < n:
                b = src[i]; i += 1; ml += b
                if b != 255:
                    ok = True; break
            if not ok:
                break
        ml += 4
        st = len(out) - off
        if off >= ml:
            out += out[st:st + ml]
        else:                                 # overlapping copy
            for k in range(ml):
                out.append(out[st + k])
    return out[:nout]


_PREV = {}   # (var, stream) -> last compressed size, to size the first range request


def _stream(path, pos, need, key):
    """Read the byte-stream whose 4-byte csize header is at pos. Return (first `need` decoded bytes, csize)."""
    prev = _PREV.get(key, NBLK)
    guess = need if prev >= NBLK else int(prev * need / NBLK * 1.06) + 512
    head = _range(path, pos, pos + 4 + guess)
    csz = struct.unpack("<i", head[:4])[0]
    _PREV[key] = csz
    body = head[4:4 + min(guess, csz)]
    if csz == NBLK:                          # stored raw (incompressible)
        if len(body) < need:
            body = body + _range(path, pos + 4 + len(body), pos + 4 + need)
        return bytes(body[:need]), csz
    have = len(body)
    while True:
        dec = lz4_prefix(body, need)
        if len(dec) >= need or have >= csz:
            return bytes(dec), csz
        nxt = min(csz, have + max(4096, int((need - len(dec)) * csz / NBLK * 1.1) + 1024))
        body = body + _range(path, pos + 4 + have, pos + 4 + nxt); have = nxt


def read_north(path, n):
    """First n float32 values of a blosc chunk (n <= NBLK), byte 0 set to midpoint."""
    hdr = _range(path, 0, 16 + 4 * 5 + 4)
    flags, ts = hdr[2], hdr[3]
    nbytes, bs, cb = struct.unpack("<iii", hdr[4:16])
    assert ts == 4 and bs == NBLK * 4 and (flags & 0x1) and not (flags & 0x2) and not (flags & 0x4), (path, flags, bs)
    nblocks = -(-nbytes // bs)
    b0 = struct.unpack("<i", hdr[16:20])[0]
    assert b0 == 16 + 4 * nblocks
    # stream 0 (low byte) is skipped, only its size is read
    cs0 = struct.unpack("<i", hdr[b0:b0 + 4])[0] if len(hdr) >= b0 + 4 else struct.unpack("<i", _range(path, b0, b0 + 4))[0]
    pos = b0 + 4 + cs0
    planes = [np.full(n, 0x80, np.uint8)]
    for s in (1, 2, 3):
        data, csz = _stream(path, pos, n, (path.split('/')[-2], s))
        if len(data) < n:
            raise RuntimeError(f"short stream {s} in {path}")
        planes.append(np.frombuffer(data, np.uint8))
        pos += 4 + csz
    return np.stack(planes, 1).copy().view("<f4").ravel()


def north_index():
    p = OUT / "co_n320_latlon.npz"
    if not p.exists():
        import xarray as xr
        ds = xr.open_zarr(f"gs://gcp-public-data-arco-era5/{CO_T2M.split('/')[0]}/single-level-reanalysis.zarr-v2",
                          storage_options={"token": "anon"}, chunks=None, consolidated=True)
        np.savez(p, lat=ds.latitude.values, lon=ds.longitude.values)
    z = np.load(p)
    n = int((z["lat"] >= LAT_MIN).sum())
    assert np.all(z["lat"][:n] >= LAT_MIN) and n <= NBLK
    return z["lat"][:n], z["lon"][:n], n


def t2m_daily(day, n):
    """Daily-mean T2m estimate. 1 Nov - 15 May: mean of 00 and 12 UTC. 16 May - 31 Oct (melt season,
    used only for melt_days): ONE analysis per day, alternating 00 / 12 UTC on odd / even days, to stay
    inside the transfer budget. Returns (values, n_samples)."""
    h = int((dt.datetime(day.year, day.month, day.day) - T0).total_seconds() // 3600)
    if (day.month, day.day) >= (5, 16) and day.month <= 10:
        hh = h + (12 if day.toordinal() % 2 == 0 else 0)
        return read_north(f"{CO_T2M}/{hh}.0", n), 1
    a = read_north(f"{CO_T2M}/{h}.0", n); b = read_north(f"{CO_T2M}/{h + 12}.0", n)
    return 0.5 * (a + b), 2


def sf_daily(day, n):
    """Daily snowfall (m w.e.) estimated from ONE hourly accumulation x 24. The co forecast store holds
    1-hour accumulations per step (checked: steps are not cumulative). The sampled valid hour rotates
    through all 24 hours (v = (7 + 5 * ordinal) mod 24) so the seasonal sum has no diurnal bias.
    valid hour v in 07..18 -> 06 UTC run of `day`, step v-6; v in 19..23 -> 18 UTC run, step v-18;
    v in 00..06 -> 18 UTC run of `day`, step v+6 (valid next day; window is 07 UTC day .. 06 UTC day+1)."""
    k = (dt.date(day.year, day.month, day.day) - T0.date()).days * 2   # index of 06 UTC run of `day`
    v = (7 + 5 * day.toordinal()) % 24
    if 7 <= v <= 18:
        run, step = k, v - 6
    elif v >= 19:
        run, step = k + 1, v - 18
    else:
        run, step = k + 1, v + 6
    return np.maximum(read_north(f"{CO_SF}/{run}.{step}.0", n), 0) * 24.0, 1


def co_available():
    z = json.loads(_sess().get(f"{GCS}/co/single-level-reanalysis.zarr-v2/.zattrs", timeout=30).text)
    return dt.date.fromisoformat(z.get("valid_time_stop_era5t", z["valid_time_stop"])[:10])


def month(var, y, m, last_day=None):
    """Daily fields for one month on the native north points, cached as npz."""
    p = OUT / var / f"{y}{m:02d}.npz"
    if p.exists():
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    lat, lon, n = north_index()
    d = dt.date(y, m, 1); days, vals, ns = [], [], []
    while d.month == m and (last_day is None or d <= last_day):
        v, k = (t2m_daily if var == "t2m" else sf_daily)(d, n)
        vals.append(v.astype(np.float32)); ns.append(k)
        days.append(d.isoformat()); d += dt.timedelta(days=1)
    partial = last_day is not None and dt.date(y, m, 28) > last_day and len(days) < 28
    out = p if not partial else p.with_name(p.stem + "_partial.npz")
    np.savez_compressed(out, days=np.array(days), v=np.stack(vals), nsamp=np.array(ns))
    return out


# --- months needed: 1 Nov W .. 15 Sep W+1 (T2m), 1 Nov W .. 30 Apr W+1 (snowfall)
def months_for(W):
    t = [(W, 11), (W, 12)] + [(W + 1, m) for m in range(1, 10)]
    s = [(W, 11), (W, 12)] + [(W + 1, m) for m in range(1, 5)]
    return t, s


# --- 0.25 deg AR fallback for days beyond the co store (winter 2026 partial only)
def ar_north_rows(path):
    """Rows 0..180 (90N..45N) of a 721x1440 AR chunk: fetch only blocks 0-1 fully and decode."""
    import numcodecs
    hdr = _range(path, 0, 16 + 4 * 8)
    nbytes, bs, cb = struct.unpack("<iii", hdr[4:16])
    nb = -(-nbytes // bs)
    starts = np.frombuffer(hdr[16:16 + 4 * nb], "<i4")
    need_el = 181 * 1440
    nblk = -(-need_el // (bs // 4))
    raw = _range(path, 0, int(starts[nblk]))
    # rebuild a valid blosc frame holding only the first nblk blocks
    newn = nblk * bs
    h = bytearray(raw[:16]); h[4:16] = struct.pack("<iii", newn, bs, 0)
    off = 16 + 4 * nblk
    st = [int(s) - int(starts[0]) + off for s in starts[:nblk]]
    body = raw[int(starts[0]):]
    frame = bytes(h) + struct.pack(f"<{nblk}i", *st) + body
    frame = frame[:12] + struct.pack("<i", len(frame)) + frame[16:]
    arr = np.frombuffer(numcodecs.Blosc().decode(frame), "<f4")[:need_el]
    return arr.reshape(181, 1440)


def ar_t2m_daily(day):
    h = int((dt.datetime(day.year, day.month, day.day) - dt.datetime(1900, 1, 1)).total_seconds() // 3600)
    # AR time axis starts 1900-01-01T00 like the co store (checked in fetch_ar_tail)
    a = ar_north_rows(f"{AR}/2m_temperature/{h}.0.0"); b = ar_north_rows(f"{AR}/2m_temperature/{h + 12}.0.0")
    return 0.5 * (a + b)


def ar_tail(first, last):
    """Daily T2m on the 0.25 deg grid rows 90N..45N for first..last (inclusive)."""
    p = OUT / "ar_t2m" / f"{first:%Y%m%d}_{last:%Y%m%d}.npz"
    if p.exists():
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    days, vals, d = [], [], first
    while d <= last:
        vals.append(ar_t2m_daily(d).astype(np.float32)); days.append(d.isoformat()); d += dt.timedelta(days=1)
    np.savez_compressed(p, days=np.array(days), v=np.stack(vals),
                        lat=90 - 0.25 * np.arange(181), lon=0.25 * np.arange(1440))
    return p


def ar_stop():
    z = json.loads(_sess().get(f"{GCS}/{AR}/.zattrs", timeout=30).text)
    return dt.date.fromisoformat(z["valid_time_stop_era5t"][:10])


def fetch(winters=range(2011, 2027), log=print):
    lat, lon, n = north_index()
    co_stop = co_available()
    log(f"co store holds ERA5/ERA5T to {co_stop}; north points n={n}")
    for W in winters:
        tm, sm = months_for(W)
        for var, ms in (("t2m", tm), ("sf", sm)):
            for (y, m) in ms:
                if dt.date(y, m, 1) > co_stop:
                    continue
                last = co_stop if dt.date(y, m, 28) > co_stop - dt.timedelta(days=1) else None
                if last is not None and (dt.date(y, m, 1) + dt.timedelta(days=40)).replace(day=1) <= co_stop:
                    last = None
                t0 = time.time()
                p = month(var, y, m, last_day=last)
                log(f"{var} {y}-{m:02d} -> {p.name}  total {STATS['bytes'] / 1e6:.1f} MB, {STATS['requests']} req, {time.time() - t0:.0f}s")
    # winter 2026 partial: November 2026 days beyond the co store, from the AR store
    tail0 = co_stop + dt.timedelta(days=1)
    try:
        stop = ar_stop()
    except Exception as e:  # noqa
        stop = None
        log(f"AR store attrs unavailable: {e}")
    if stop and stop >= tail0 and tail0 >= dt.date(2026, 11, 1):
        p = ar_tail(tail0, stop)
        log(f"AR tail {tail0}..{stop} -> {p.name}  total {STATS['bytes'] / 1e6:.1f} MB")
    (OUT / "transfer_log.json").write_text(json.dumps({**STATS, "co_stop": str(co_stop), "ar_stop": str(stop)}))
    http.record("era5_arco",
                dataset="ERA5 hourly reanalysis (2 m temperature analysis; snowfall 1-h accumulations from 06/18 UTC forecasts), ARCO-ERA5 copy",
                url="https://storage.googleapis.com/gcp-public-data-arco-era5/co/ (single-level-reanalysis.zarr-v2 t2m, single-level-forecast.zarr-v2 sf); ar/full_37-1h-0p25deg-chunk-1.zarr-v3 for the ERA5T tail",
                doi="10.24381/cds.adbb2d47 (ERA5 hourly single levels); Hersbach et al. 2020, QJRMS, 10.1002/qj.3803; ARCO-ERA5: Carver & Merose 2023",
                licence="Copernicus Climate Change Service (C3S) licence / CC-BY 4.0 (ERA5); contains modified Copernicus Climate Change Service information. ARCO-ERA5 copy by Google Research, distributed under the same terms.",
                files=[{"name": "data/raw/era5/{t2m,sf}/YYYYMM.npz (daily fields north of 45N, native N320 points)", "sha256": None, "bytes": None}],
                notes=f"Partial HTTP range reads of blosc block 0 (lat>=45N), low mantissa byte dropped (midpoint). T2m daily mean = mean of 00+12 UTC for 1 Nov-15 May, one analysis/day alternating 00/12 UTC for 16 May-15 Sep (winter 2024 Jun-Sep cached earlier at 2/day); snowfall = 24 x one 1-h accumulation per day, valid hour rotating through 24 h (Nov 2024 also at 4/day for a sampling check). Transfer {STATS['bytes'] / 1e6:.0f} MB this run in {STATS['requests']} requests. ERA5T (preliminary) after valid_time_stop. Warm bias over sea ice in cold conditions (Wang et al. 2019).")


if __name__ == "__main__":
    import sys
    ws = range(int(sys.argv[1]), int(sys.argv[2]) + 1) if len(sys.argv) > 2 else range(2011, 2027)
    fetch(ws)
