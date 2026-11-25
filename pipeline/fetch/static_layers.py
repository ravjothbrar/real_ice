"""Static layers on the 25 km EASE2-N grid -> data/interim/static.nc, and web/public/data/land.json.

land            Natural Earth 50 m land (public domain), cell = 1 if > 50 % of its area is land
                (rasterised at 5 km = 25 sub-cells per cell).
depth           GEBCO_2026 15" grid via the GEBCO subsetting app (download.gebco.net). Only a small
                Cambridge Bay box was fetched (the full 45-90N subset is ~1.9 GB, over the 1 GB rule);
                depth = mean ocean depth of GEBCO points in the cell, NaN elsewhere. See ASSUMPTIONS.md.
excl_settlement Natural Earth 10 m populated places with latitude > 55N, 50 km buffer.
excl_protected  all zeros: no open, licence-clean pan-Arctic marine protected-area layer was
                reachable (Natural Earth has none; WDPA is not on the allowed hosts / has non-open terms).
excl_shipping   hand-curated approximate polylines (Northwest Passage southern route, Northern Sea Route),
                50 km buffer; vertices in data/hand_curated/shipping_corridors.geojson. NOT ASTD.
region          integer atlas regions from simple lon/lat boxes (REGIONS below).
"""
import io, json, struct, zipfile, time, pathlib
import numpy as np
import shapely
from shapely.geometry import Polygon, MultiPolygon, LineString, mapping, shape
import xarray as xr
from scipy.spatial import cKDTree
from pipeline import http, grid

ROOT = http.RAW.parents[1]
INTERIM = ROOT / "data" / "interim"
HAND = ROOT / "data" / "hand_curated"
WEB = ROOT / "web" / "public" / "data"
NE = "https://naciscdn.org/naturalearth"
NE_LICENCE = "Public domain (Natural Earth terms of use: 'All versions of Natural Earth raster + vector map data found on this website are in the public domain')."
SETTLE_KM = 50.0
SHIP_KM = 50.0
CB_BOX = dict(left=-106.5, right=-103.5, top=69.6, bottom=68.6)


# ---------------------------------------------------------------- minimal shapefile reader
def _read_shp(zf, stem):
    shp = zf.read(stem + ".shp")
    out, pos = [], 100
    while pos < len(shp):
        _, clen = struct.unpack(">ii", shp[pos:pos + 8]); pos += 8
        rec = shp[pos:pos + 2 * clen]; pos += 2 * clen
        st = struct.unpack("<i", rec[:4])[0]
        if st == 0:
            out.append(None)
        elif st == 1:
            out.append(struct.unpack("<dd", rec[4:20]))
        elif st == 5:
            nparts, npts = struct.unpack("<ii", rec[36:44])
            parts = list(struct.unpack(f"<{nparts}i", rec[44:44 + 4 * nparts])) + [npts]
            pts = np.frombuffer(rec[44 + 4 * nparts:44 + 4 * nparts + 16 * npts], "<f8").reshape(-1, 2)
            out.append([pts[parts[k]:parts[k + 1]] for k in range(nparts)])
        else:
            raise ValueError(f"shape type {st}")
    return out


def _read_dbf(zf, stem):
    b = zf.read(stem + ".dbf")
    n, hlen, rlen = struct.unpack("<IHH", b[4:12])
    fields, p = [], 32
    while b[p] != 0x0D:
        name = b[p:p + 11].split(b"\0")[0].decode(); ftype = chr(b[p + 11]); flen = b[p + 16]
        fields.append((name, ftype, flen)); p += 32
    rows = []
    for r in range(n):
        o = hlen + r * rlen + 1; row = {}
        for name, ftype, flen in fields:
            v = b[o:o + flen].decode("utf-8", "replace").strip(); o += flen
            if ftype in "NF":
                try: v = float(v)
                except ValueError: v = None
            row[name] = v
        rows.append(row)
    return rows


def _rings_to_polys(rings):
    """Shapefile rings (outer clockwise, holes counter-clockwise) -> shapely polygons."""
    polys = []
    for r in rings:
        ring = shapely.LinearRing(r)
        if not ring.is_ccw:            # clockwise = outer
            polys.append([r, []])
        elif polys:
            polys[-1][1].append(r)
    return [Polygon(o, h) for o, h in polys]


def ne_land():
    p = http.get(f"{NE}/50m/physical/ne_50m_land.zip", "naturalearth/ne_50m_land.zip")
    zf = zipfile.ZipFile(p)
    polys = []
    for rings in _read_shp(zf, "ne_50m_land"):
        polys += _rings_to_polys(rings)
    return [shapely.make_valid(g) for g in polys], p


def ne_places():
    p = http.get(f"{NE}/10m/cultural/ne_10m_populated_places.zip", "naturalearth/ne_10m_populated_places.zip")
    zf = zipfile.ZipFile(p)
    pts = _read_shp(zf, "ne_10m_populated_places"); rows = _read_dbf(zf, "ne_10m_populated_places")
    return [(r.get("NAME"), xy[0], xy[1]) for xy, r in zip(pts, rows) if xy and xy[1] > 55.0], p


# ---------------------------------------------------------------- projection helpers
def _project(geom):
    return shapely.transform(geom, lambda c: np.c_[grid._to_xy.transform(c[:, 0], c[:, 1])])


def land_mask(polys, sub=5):
    from rasterio import features
    from rasterio.transform import from_origin
    north = []
    for g in polys:
        g = shapely.clip_by_rect(g, -180, 20, 180, 90)
        if not g.is_empty:
            north.append(_project(shapely.segmentize(g, 0.25)))
    n = grid.CROP * sub
    tr = from_origin(-grid.HALF, grid.HALF, grid.RES / sub, grid.RES / sub)
    fine = features.rasterize(((g, 1) for g in north), out_shape=(n, n), transform=tr, fill=0, dtype="uint8")
    frac = fine.reshape(grid.CROP, sub, grid.CROP, sub).mean(axis=(1, 3))
    return (frac > 0.5).astype(np.uint8), frac.astype(np.float32)


def _cells():
    return np.c_[grid.XX.ravel(), grid.YY.ravel()]


def settlement_mask(places):
    xy = np.c_[grid._to_xy.transform([p[1] for p in places], [p[2] for p in places])]
    d, _ = cKDTree(xy).query(_cells())
    return (d <= SETTLE_KM * 1000).reshape(grid.CROP, grid.CROP).astype(np.uint8)


# ---------------------------------------------------------------- hand-curated shipping corridors
# Approximate centrelines drawn from general knowledge of the routes (lon, lat); NOT ASTD, NOT a chart.
NWP_SOUTH = [(-168.8, 65.8), (-166.5, 68.9), (-161.0, 70.9), (-156.5, 71.6), (-150.0, 71.0), (-141.0, 70.3),
             (-133.0, 70.5), (-127.0, 71.0), (-123.5, 70.6), (-118.0, 69.5), (-114.5, 69.0), (-111.0, 68.4),
             (-107.5, 68.7), (-105.1, 69.05), (-101.5, 68.6), (-98.5, 68.6), (-96.5, 69.3), (-96.5, 71.5),
             (-96.0, 73.0), (-95.5, 74.0), (-91.0, 74.2), (-85.0, 74.2), (-80.0, 74.2), (-75.0, 74.0),
             (-68.0, 72.0), (-60.0, 67.0), (-58.0, 62.0)]
NSR = [(33.0, 69.5), (40.0, 70.5), (50.0, 70.8), (58.0, 70.4), (62.0, 71.5), (68.0, 73.0), (75.0, 73.8),
       (80.5, 73.7), (90.0, 75.5), (98.0, 77.0), (104.0, 77.8), (112.0, 77.0), (120.0, 76.0), (130.0, 74.5),
       (138.0, 73.8), (141.5, 73.2), (150.0, 72.0), (157.0, 71.0), (164.0, 70.2), (170.3, 69.9),
       (176.0, 68.0), (180.0, 66.8), (-171.0, 66.0), (-169.0, 65.6)]


def shipping():
    HAND.mkdir(parents=True, exist_ok=True)
    feats = [{"type": "Feature", "properties": {"name": n, "note": "hand-curated, approximate, not ASTD", "buffer_km": SHIP_KM},
              "geometry": {"type": "LineString", "coordinates": [list(c) for c in pts]}}
             for n, pts in (("Northwest Passage (southern route via Cambridge Bay, Queen Maud Gulf, Lancaster Sound)", NWP_SOUTH),
                            ("Northern Sea Route (along the Russian coast)", NSR))]
    gj = {"type": "FeatureCollection", "name": "shipping_corridors",
          "note": "hand-curated, approximate, not ASTD. Centrelines drawn from general route descriptions; Survival Gap Atlas, 2026-11-25.",
          "features": feats}
    (HAND / "shipping_corridors.geojson").write_text(json.dumps(gj, indent=1))
    pts = shapely.points(_cells())
    d = np.full(len(pts), np.inf)
    for pl in (NWP_SOUTH, NSR):
        # densify in lon/lat (handle the antimeridian by unwrapping), then project
        lon = np.unwrap(np.radians([p[0] for p in pl])); lon = np.degrees(lon)
        line = shapely.segmentize(LineString(np.c_[lon, [p[1] for p in pl]]), 0.2)
        c = np.asarray(line.coords)
        xy = np.c_[grid._to_xy.transform(((c[:, 0] + 180) % 360) - 180, c[:, 1])]
        d = np.minimum(d, shapely.distance(pts, LineString(xy)))
    return (d <= SHIP_KM * 1000).reshape(grid.CROP, grid.CROP).astype(np.uint8)


# ---------------------------------------------------------------- regions
REGION_NAMES = {0: "other", 1: "Beaufort (incl. Chukchi)", 2: "Transpolar (central Arctic/Eurasian Basin + Laptev/E Siberian)",
                3: "Canadian Archipelago", 4: "Barents-Kara", 5: "Greenland/Fram", 6: "Baffin/Hudson/Labrador", 7: "Bering/Okhotsk"}
# Applied in this order; a cell keeps the first region whose box contains it. lon in [-180, 180).
REGIONS = [
    (3, "lon -125..-80, lat 66.5..82 ; plus Nares Strait lon -80..-60, lat 78..82"),
    (6, "lon -100..-45, lat 45..78 (Hudson Bay, Foxe Basin south, Hudson Strait, Baffin Bay, Davis Strait, Labrador Sea)"),
    (7, "lon >= 135E or <= -157, lat 40..66.5 (Bering Sea, Sea of Okhotsk, Tatar Strait)"),
    (2, "lat >= 82 (all lon) ; plus lon 100..180, lat 68..82 (Laptev, East Siberian)"),
    (1, "lon -180..-125, lat 66.5..82 (Chukchi, Beaufort, southern Canada Basin)"),
    (4, "lon 15..100, lat 68..82 ; plus White Sea lon 32..45, lat 63..68"),
    (5, "lon -45..15, lat 60..82 (Greenland, Iceland and Norwegian seas, Fram Strait)"),
]


def regions(lon, lat):
    lon = ((lon + 180) % 360) - 180
    tests = {
        3: ((lon >= -125) & (lon < -80) & (lat >= 66.5) & (lat < 82)) | ((lon >= -80) & (lon < -60) & (lat >= 78) & (lat < 82)),
        6: (lon >= -100) & (lon < -45) & (lat >= 45) & (lat < 78),
        7: ((lon >= 135) | (lon <= -157)) & (lat >= 40) & (lat < 66.5),
        2: (lat >= 82) | ((lon >= 100) & (lat >= 68) & (lat < 82)),
        1: (lon < -125) & (lat >= 66.5) & (lat < 82),
        4: ((lon >= 15) & (lon < 100) & (lat >= 68) & (lat < 82)) | ((lon >= 32) & (lon < 45) & (lat >= 63) & (lat < 68)),
        5: (lon >= -45) & (lon < 15) & (lat >= 60) & (lat < 82),
    }
    out = np.zeros(lon.shape, np.int8)
    for code, _ in REGIONS:
        out[(out == 0) & tests[code]] = code
    return out


# ---------------------------------------------------------------- GEBCO subset (Cambridge Bay box only)
GEBCO_API = "https://download.gebco.net/api/queue"


def gebco_box(box=CB_BOX, name="gebco_2026_cambridge_bay.zip"):
    dest = http.RAW / "gebco" / name
    if dest.exists():
        return dest
    s = http.session()
    body = {"id": "0", "email": None, "submission_date": time.strftime("%Y-%m-%dT%H:%M:%S"), "processing_status": "new",
            "items": [{"id": 0, "grid_id": 1, "data_source_ids": [1], "formats": [1], **box}]}   # GEBCO_2026 global, NetCDF
    bid = s.post(GEBCO_API, json=body, timeout=60).json()["basketId"]
    for _ in range(60):
        st = s.get(f"{GEBCO_API}/status/{bid}", timeout=60).json().get("status")
        if st == "finished":
            break
        time.sleep(10)
    return http.get(f"{GEBCO_API}/download/{bid}", f"gebco/{name}", s=s)


def gebco_depth(zpath):
    zf = zipfile.ZipFile(zpath)
    nc = [n for n in zf.namelist() if n.endswith(".nc")][0]
    tmp = http.RAW / "gebco" / pathlib.Path(nc).name
    if not tmp.exists():
        tmp.write_bytes(zf.read(nc))
    ds = xr.open_dataset(tmp)
    el = ds["elevation"].values.astype(float)
    LO, LA = np.meshgrid(ds["lon"].values, ds["lat"].values)
    ocean = el < 0
    depth = grid.regrid_points(LO[ocean], LA[ocean], -el[ocean])
    cnt_ocean = grid.regrid_points(LO, LA, ocean.astype(float))
    # keep only cells fully inside the box and at least half ocean
    i, j = grid.lonlat_to_ij(LO, LA)
    inside = np.zeros((grid.CROP, grid.CROP), bool)
    ii = np.rint(i).astype(int); jj = np.rint(j).astype(int)
    cnt = np.bincount(ii.ravel() * grid.CROP + jj.ravel(), minlength=grid.CROP ** 2).reshape(grid.CROP, grid.CROP)
    full = cnt >= 0.8 * np.median(cnt[cnt > 0])
    depth[~full | ~(cnt_ocean >= 0.5)] = np.nan
    return depth.astype(np.float32), ds, el, LO, LA


def site_depth(el, LO, LA, lon, lat, r_km=2.0):
    x0, y0 = grid._to_xy.transform(lon, lat)
    x, y = grid._to_xy.transform(LO, LA)
    m = np.hypot(x - x0, y - y0) <= r_km * 1000
    return float(-np.median(el[m])), float(-np.max(el[m])), float(-np.min(el[m]))


# ---------------------------------------------------------------- web land.json
def land_json(polys, tol=0.05, lat_min=45.0):
    WEB.mkdir(parents=True, exist_ok=True)
    geoms = []
    for g in polys:
        c = shapely.clip_by_rect(g, -180, lat_min, 180, 90)
        if c.is_empty:
            continue
        c = shapely.set_precision(c.simplify(tol, preserve_topology=True), 0.001)
        if not c.is_empty and c.area > 0:
            geoms.append(c)
    feats = [{"type": "Feature", "properties": {}, "geometry": mapping(g)} for g in geoms]
    gj = {"type": "FeatureCollection",
          "properties": {"source": "Natural Earth 50m land (public domain), clipped north of 45N, simplified 0.05 deg",
                         "url": f"{NE}/50m/physical/ne_50m_land.zip"},
          "features": feats}
    p = WEB / "land.json"
    p.write_text(json.dumps(gj, separators=(",", ":")))
    return p


def build():
    INTERIM.mkdir(parents=True, exist_ok=True)
    polys, land_zip = ne_land()
    land, frac = land_mask(polys)
    places, pp_zip = ne_places()
    settle = settlement_mask(places)
    ship = shipping()
    reg = regions(grid.LON, grid.LAT)
    reg[land == 1] = 0
    try:
        gz = gebco_box()
        depth, gds, el, LO, LA = gebco_depth(gz)
        cb = site_depth(el, LO, LA, -105.10, 69.05)
        gebco_note = f"GEBCO_2026 15-arcsec subset {CB_BOX}; depth at approx. site 69.05N 105.10W within 2 km: median {cb[0]:.0f} m (range {cb[1]:.0f}..{cb[2]:.0f} m)"
    except Exception as e:   # noqa
        gz, depth, cb = None, np.full((grid.CROP, grid.CROP), np.nan, np.float32), None
        gebco_note = f"GEBCO not reachable: {e}"
    depth[land == 1] = np.nan
    coords = {"lat": (("y", "x"), grid.LAT.astype(np.float32)), "lon": (("y", "x"), grid.LON.astype(np.float32))}
    ds = xr.Dataset({
        "land": (("y", "x"), land, {"long_name": "land (Natural Earth 50m, >50% of cell)", "source": "Natural Earth 50m land, public domain"}),
        "land_frac": (("y", "x"), frac, {"long_name": "land area fraction (5 km sub-cells)"}),
        "depth": (("y", "x"), depth, {"units": "m", "positive": "down", "long_name": "mean ocean depth of GEBCO_2026 15\" points in cell",
                                       "coverage": f"Cambridge Bay box only {CB_BOX}; NaN elsewhere (full 45-90N subset ~1.9 GB, not fetched)", "note": gebco_note}),
        "excl_settlement": (("y", "x"), settle, {"buffer_km": SETTLE_KM, "source": "Natural Earth 10m populated places, latitude > 55N", "n_places": len(places)}),
        "excl_protected": (("y", "x"), np.zeros((grid.CROP, grid.CROP), np.uint8), {"status": "not available",
                            "note": "No open, licence-clean pan-Arctic marine protected-area layer reachable; all zeros. Not 'no protected areas'."}),
        "excl_shipping": (("y", "x"), ship, {"buffer_km": SHIP_KM, "source": "data/hand_curated/shipping_corridors.geojson",
                          "note": "hand-curated, approximate, not ASTD"}),
        "region": (("y", "x"), reg, {"codes": json.dumps(REGION_NAMES), "definition": json.dumps({c: d for c, d in REGIONS}),
                   "note": "simple lon/lat boxes applied in order 3,6,7,2,1,4,5; land cells = 0"}),
    }, coords=coords, attrs={"grid": "EASE2-N 25 km 360x360 (pipeline/grid.py)", "built": time.strftime("%Y-%m-%d")})
    enc = {v: {"zlib": True, "complevel": 4} for v in ds.data_vars}
    ds.to_netcdf(INTERIM / "static.nc", encoding=enc)
    lj = land_json(polys)
    f = lambda p: {"name": str(p.relative_to(ROOT)), "sha256": http.sha256(p), "bytes": p.stat().st_size}
    http.record("naturalearth", dataset="Natural Earth 50m land; Natural Earth 10m populated places (v5.x)",
                url=f"{NE}/50m/physical/ne_50m_land.zip ; {NE}/10m/cultural/ne_10m_populated_places.zip",
                doi=None, licence=NE_LICENCE, files=[f(land_zip), f(pp_zip)],
                notes=f"land: >50% of 25 km cell; settlements: {len(places)} places north of 55N, {SETTLE_KM:.0f} km buffer; web land.json clipped >=45N, simplify 0.05 deg ({lj.stat().st_size/1e3:.0f} KB)")
    if gz is not None:
        http.record("gebco", dataset="GEBCO_2026 Grid (15 arc-second), subset via GEBCO subsetting app",
                    url="https://download.gebco.net/ (api/queue, grid gebco_2026_global, NetCDF)",
                    doi="10.5285/4f68d5c7-45eb-f999-e063-7086abc036fa (GEBCO Compilation Group (2026) GEBCO 2026 Grid)",
                    licence="Public domain (file metadata: 'The GEBCO Grid is placed in the public domain and may be used free of charge'); conditions of use at gebco.net ask for acknowledgement and state it is not for navigation.",
                    files=[f(gz)], notes=gebco_note)
    http.record("shipping_corridors_hand", dataset="Hand-curated approximate shipping corridors (NWP southern route, NSR)",
                url="data/hand_curated/shipping_corridors.geojson", doi=None, licence="Own work (project), CC0",
                files=[f(HAND / "shipping_corridors.geojson")], notes="hand-curated, approximate, not ASTD; 50 km buffer")
    print("land cells", int(land.sum()), "settlement cells", int(settle.sum()), "shipping cells", int(ship.sum()),
          "region counts", np.bincount(reg.ravel()), "land.json KB", lj.stat().st_size // 1000, gebco_note)
    return ds


if __name__ == "__main__":
    build()
