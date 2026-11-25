// SYNTHETIC development fixture for the Survival Gap Atlas front end.
// Every value written here is invented and must never be shown as data. It exists only so the
// UI can be developed before `make export` produces web/public/data/. Output: web/dev/fixture-data/
// Usage: node dev/make-fixture.mjs   (then open the dev server with ?fixture=1)
// It mimics the key names and shapes written by pipeline/export.py, so the fixture exercises the same
// normalisation path (src/normalize.ts) as the real export.
import { mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { feature } from 'topojson-client';

const here = dirname(fileURLToPath(import.meta.url));
const out = join(here, 'fixture-data');
mkdirSync(out, { recursive: true });

// ---- EASE2-N (same maths as src/ease2.ts) ----
const A = 6378137.0, E2 = 0.0066943799901413165, E = Math.sqrt(E2), D2R = Math.PI / 180;
const q = (phi) => { const s = Math.sin(phi); return (1 - E2) * (s / (1 - E2 * s * s) - (1 / (2 * E)) * Math.log((1 - E * s) / (1 + E * s))); };
const QP = q(Math.PI / 2);
const RES = 25000, CROP = 360, HALF = CROP * RES / 2;
function forward(lon, lat) { const rho = A * Math.sqrt(Math.max(0, QP - q(lat * D2R))); const l = lon * D2R; return [rho * Math.sin(l), -rho * Math.cos(l)]; }
function inverse(x, y) {
  const rho = Math.hypot(x, y); const lon = Math.atan2(x, -y) / D2R; if (rho < 1e-6) return [0, 90];
  const qq = QP - (rho / A) ** 2; let phi = Math.asin(qq / 2);
  for (let k = 0; k < 8; k++) { const s = Math.sin(phi), c = Math.cos(phi), one = 1 - E2 * s * s; phi += (one * one / (2 * c)) * (qq / (1 - E2) - s / one + (1 / (2 * E)) * Math.log((1 - E * s) / (1 + E * s))); }
  return [lon, phi / D2R];
}

// ---- land (Natural Earth 50 m via world-atlas, real geometry; fine for a basemap) ----
const topo = JSON.parse(readFileSync(join(here, '..', 'node_modules', 'world-atlas', 'land-50m.json'), 'utf8'));
const land = feature(topo, topo.objects.land);
const polys = (land.type === 'FeatureCollection' ? land.features : [land]).flatMap((f) =>
  f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates);
const north = polys.filter((p) => p[0].some(([, la]) => la >= 45));
const r3 = (v) => Math.round(v * 1000) / 1000;
writeFileSync(join(out, 'land.json'), JSON.stringify({ type: 'Feature', properties: { note: 'Natural Earth 50m land (world-atlas 2.0.2), north of 45N' }, geometry: { type: 'MultiPolygon', coordinates: north.map((p) => p.map((r) => r.map(([lo, la]) => [r3(lo), r3(la)]))) } }));

// rasterise land onto the grid (even-odd scanline at cell centres)
const landMask = new Uint8Array(CROP * CROP);
for (const poly of north) {
  const rings = poly.map((r) => r.map(([lo, la]) => { const [x, y] = forward(lo, Math.max(la, -60)); return [(x + HALF) / RES - 0.5, (HALF - y) / RES - 0.5]; }));
  let imin = Infinity, imax = -Infinity;
  for (const r of rings) for (const [, i] of r) { imin = Math.min(imin, i); imax = Math.max(imax, i); }
  for (let i = Math.max(0, Math.ceil(imin)); i <= Math.min(CROP - 1, Math.floor(imax)); i++) {
    const xs = [];
    for (const r of rings) for (let k = 0; k < r.length - 1; k++) {
      const [j1, i1] = r[k], [j2, i2] = r[k + 1];
      if ((i1 <= i && i2 > i) || (i2 <= i && i1 > i)) xs.push(j1 + ((i - i1) / (i2 - i1)) * (j2 - j1));
    }
    xs.sort((a, b) => a - b);
    for (let k = 0; k + 1 < xs.length; k += 2) for (let j = Math.max(0, Math.ceil(xs[k])); j <= Math.min(CROP - 1, Math.floor(xs[k + 1])); j++) landMask[i * CROP + j] = 1;
  }
}

// ---- synthetic ice-capable cells ----
const cells = [];
for (let i = 0; i < CROP; i++) for (let j = 0; j < CROP; j++) {
  if (landMask[i * CROP + j]) continue;
  const [lon, lat] = inverse(-HALF + RES * (j + 0.5), HALF - RES * (i + 0.5));
  if (lat > 66 + 10 * Math.cos((lon - 10) * D2R)) cells.push([i, j, lon, lat]);
}
const N = cells.length;
const sig = (z) => 1 / (1 + Math.exp(-z));
const settlements = [[-105.06, 69.12], [-165.41, 64.5], [-94.83, 74.7], [-156.79, 71.29], [15.63, 78.22], [128.87, 71.64]];

// Layer names and shapes follow pipeline/export.py.
const STATIC = {
  sept_freq: [1 / 254, 0, 'fraction', 'FIXTURE September ice presence 2012-2025'],
  fdd: [25, 0, 'K day', 'FIXTURE freezing degree days'],
  hs: [0.015, 0, 'm', 'FIXTURE survival thickness'],
  R: [1 / 254, 0, 'fraction', 'FIXTURE retention to 15 September'],
  R_sd: [1 / 254, 0, 'fraction', 'FIXTURE retention year-to-year spread'],
  disagree: [0.01, 0, 'm', 'FIXTURE thickness product disagreement'],
  excluded: [1, 0, 'bits', 'FIXTURE exclusions: 1 settlement, 2 protected, 4 shipping'],
};
const WINTER = {
  h0: [0.025, 0, 'm', 'FIXTURE start-of-winter thickness'],
  h0_sd: [0.01, 0, 'm', 'FIXTURE start thickness uncertainty'],
  spread: [0.01, 0, 'm', 'FIXTURE between-product spread'],
  p_without: [1 / 254, 0, 'probability', 'FIXTURE P(survive) without'],
  p_with: [1 / 254, 0, 'probability', 'FIXTURE P(survive) with'],
  uplift: [1 / 254, 0, 'probability', 'FIXTURE uplift'],
  blocked: [1 / 254, 0, 'fraction', 'FIXTURE share of draws below the 0.6 m guard'],
};
const ALL = { ...STATIC, ...WINTER };
const enc = (name, v) => { if (v == null || !Number.isFinite(v)) return 255; const [sc, of] = ALL[name]; return Math.max(0, Math.min(254, Math.round((v - of) / sc))); };
const sNames = Object.keys(STATIC), wNames = Object.keys(WINTER);

const cellsBuf = new Uint16Array(N * 2);
cells.forEach(([i, j], k) => { cellsBuf[2 * k] = i; cellsBuf[2 * k + 1] = j; });
writeFileSync(join(out, 'cells.bin'), Buffer.from(cellsBuf.buffer));

const XY = cells.map(([i, j]) => [(-HALF + RES * (j + 0.5)) / 1e6, (HALF - RES * (i + 0.5)) / 1e6]);
const st = new Uint8Array(N * sNames.length).fill(255);
const put = (buf, names, name, k, v) => { buf[names.indexOf(name) * N + k] = enc(name, v); };
const statics = cells.map(([, , lon, lat], k) => {
  const [x, y] = XY[k];
  const fdd = 1500 + 3600 * Math.exp(-(x * x + y * y) / 3.5);
  const hs = 1.0 + 1.2 * sig((y - 0.3 * x - 0.2) * 2.2);
  const R = 0.97 - 0.85 * sig((-y - 1.0 + 0.6 * x) * 3.5);
  put(st, sNames, 'sept_freq', k, sig((1.9 - Math.hypot(x + 0.5, y + 0.2)) * 3.2));
  put(st, sNames, 'fdd', k, fdd); put(st, sNames, 'hs', k, hs); put(st, sNames, 'R', k, R);
  put(st, sNames, 'R_sd', k, 0.05 + 0.1 * Math.abs(Math.sin(4 * x)));
  put(st, sNames, 'disagree', k, 0.1 + 0.25 * Math.abs(Math.sin(3 * x) * Math.cos(2 * y)));
  let f = 0;
  for (const [slo, sla] of settlements) { const [sx, sy] = forward(slo, sla); if (Math.hypot(x * 1e6 - sx, y * 1e6 - sy) < 90e3) f |= 1; }
  if (lon > 8 && lon < 30 && lat > 76 && lat < 81) f |= 2;
  if ((lon > 50 && lon < 175 && Math.abs(lat - (76 - 0.02 * (lon - 50))) < 0.6) || (lon > -125 && lon < -80 && Math.abs(lat - 74.3) < 0.45)) f |= 4;
  st[sNames.indexOf('excluded') * N + k] = f;
  return { fdd, hs, R, f };
});
writeFileSync(join(out, 'static.bin'), st);

const winters = [];
for (let w = 2018; w <= 2026; w++) {
  const partial = w === 2026;
  const buf = new Uint8Array(N * wNames.length).fill(255);
  const ph = (w - 2018) * 0.9;
  let nb = 0, nbx = 0;
  cells.forEach((_, k) => {
    const [x, y] = XY[k];
    const { fdd, hs, R, f } = statics[k];
    const d = Math.hypot(x + 0.6 + 0.15 * Math.sin(ph), y + 0.3);
    const h0 = Math.max(0.05, 0.25 + 2.3 * Math.exp(-(d * d) / 2.2) + 0.18 * Math.sin(ph + 2 * x) + 0.08 * Math.sin(9 * x) * Math.cos(7 * y));
    put(buf, wNames, 'h0', k, h0);
    put(buf, wNames, 'h0_sd', k, 0.05 + 0.15 * Math.abs(Math.sin(5 * y + ph)));
    put(buf, wNames, 'spread', k, 0.08 + 0.32 * Math.abs(Math.sin(3 * x + ph) * Math.cos(2 * y)));
    if (partial) return;
    const hend = Math.sqrt(h0 * h0 + 0.0009 * fdd) * 0.82;
    const blocked = sig((0.6 - h0) * 12);
    const G = 0.5 * fdd / 4000 * (1 - blocked);
    const pwo = sig((hend - hs) / 0.22) * R;
    const pw = sig((hend + G - hs) / 0.22) * R;
    put(buf, wNames, 'p_without', k, pwo); put(buf, wNames, 'p_with', k, pw);
    put(buf, wNames, 'uplift', k, pw - pwo); put(buf, wNames, 'blocked', k, blocked);
    if (pwo < 0.7 && !(blocked >= 0.5) && pw - pwo >= 0.2) { nb++; if (f) nbx++; }
  });
  writeFileSync(join(out, `winter-${w}.bin`), buf);
  winters.push({ w, label: `${w}/${String((w + 1) % 100).padStart(2, '0')}`, partial, ice_km2: 7654321, band_km2: nb * 625, band_excl_km2: nbx * 625 });
}

const layers = Object.fromEntries(Object.entries(ALL).map(([k, [scale, offset, unit, title]]) => [k, { scale, offset, unit, title }]));
writeFileSync(join(out, 'manifest.json'), JSON.stringify({
  fixture: true,
  built: '2026-11-25',
  grid: { epsg: 6931, res: RES, crop: CROP, half: HALF, cell_area_km2: 625 },
  n_cells: N, winters, static_layers: sNames, winter_layers: wNames, layers,
}, null, 1));

const card = (m, w, n, e) => ({ meaning: `FIXTURE. ${m}`, why: `FIXTURE. ${w}`, not_proof_of: `FIXTURE. ${n}`, example: `FIXTURE. ${e}` });
const cards = {
  h0: card('Synthetic start-of-winter thickness.', 'Thicker start ice needs less help.', 'Not a measurement.', 'Cell X: 9.99 m (fake).'),
  disagree: card('Synthetic product disagreement.', 'Wide spread = low confidence.', 'Not an error bar from any product.', 'Median 0.99 m (fake).'),
  fdd: card('Synthetic freezing degree days.', 'More cold, more growth.', 'Not ERA5.', 'Cell X: 9999 K day (fake).'),
  hs: card('Synthetic survival thickness.', 'The bar the ice must clear.', 'Not van Dijke values.', 'Cell X: 9.99 m (fake).'),
  R: card('Synthetic retention.', 'Ice that drifts out is lost.', 'Not OSI SAF drift.', 'Cell X: 0.99 (fake).'),
  gap: card('Synthetic band classes.', 'Where flooding would change the outcome.', 'Not a deployment site.', 'Winter X: 99,999 km2 (fake).'),
  sept_freq: card('Synthetic September presence.', 'Observed check for the model.', 'Not concentration data.', 'Cell X: 0.99 (fake).'),
  excluded: card('Synthetic exclusion buffers.', 'Places thickening must not go.', 'Not the full set of places that matter.', 'Fake buffer 99 km.'),
  uplift: card('Synthetic uplift, P(with) minus P(without).', 'What the band is built from.', 'Not causal proof.', '0.99 (fake).'),
  scale: card('Band area against a synthetic plan.', 'Scale of the plan.', 'Feasibility; throughput is assumed.', '9.99 TWh (fake).'),
  sensitivity: card('Synthetic tornado.', 'Shows which input moves the band most.', 'Not a full uncertainty analysis.', '±99,999 km2 (fake).'),
  calibration: card('Synthetic calibration.', 'Ties the model to the field paper.', 'Not validation elsewhere.', 'Uncalibrated 12 cm (fake).'),
  hindcast: card('Synthetic hindcast.', 'Checks against observed September ice.', 'Not a forecast skill score.', 'AUC 0.500 (fake).'),
};
const fakeProv = (n) => ({ dataset: `Synthetic dataset ${n} (fixture)`, url: 'https://example.invalid/fixture', licence: 'none (synthetic)' });
writeFileSync(join(out, 'summary.json'), JSON.stringify({
  fixture: true,
  built: '2026-11-25',
  thresholds: { survives_p_without: 0.7, hopeless_p_with: 0.2, uplift: 0.2, blocked_frac: 0.5, guard_m: 0.6 },
  scale: { target_km2: 1000000, mwh_per_km2: 8, window_days: 90, share_of_ice_area: 0.05, source: 'FIXTURE (synthetic source line)', throughput_default_km2_per_drone_day: 0.1, throughput_note: 'ASSUMPTION' },
  calibration: { site: 'Cambridge Bay, approx. (FIXTURE)', winter: '2024/25', uncalibrated: { diff_m: 0.123 }, calibrated: { diff_m: 0.32 }, alpha: 9.99, paper_diff_m: 0.32, paper: 'FIXTURE (synthetic); paper doi:10.1029/2025EF007894' },
  hindcast: {
    built: '2026-11-25', command: 'FIXTURE', winters: [2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024],
    auc_cell_year: { model: 0.5, baseline_thin_ice: 0.25, baseline_edge_distance: 0.125 },
    spearman_vs_presence: { model: 0.4, baseline_thin_ice: 0.2, baseline_edge_distance: 0.1 },
    band_overlap_with_marginal: { model_band: 0.3, baseline_thin_ice_same_k: 0.15, baseline_edge_distance_same_k: 0.075, base_rate: 0.11 },
    beats_both: true,
  },
  sensitivity: {
    winter: 2024, n_draws: 300, base_band_km2: 999000, method: 'one-at-a-time (FIXTURE)',
    factors: [
      { factor: 'hs_scale', label: 'Survival thickness (FIXTURE)', band_km2_low: 1099000, band_km2_high: 899000, swing_km2: 200000 },
      { factor: 'gain_scale', label: 'Flooding gain G (FIXTURE)', band_km2_low: 849000, band_km2_high: 1049000, swing_km2: 200000 },
      { factor: 'fdd_scale', label: 'Freezing degree days (FIXTURE)', band_km2_low: 929000, band_km2_high: 1029000, swing_km2: 100000 },
      { factor: 'snow_scale', label: 'Snow insulation (FIXTURE)', band_km2_low: 1019000, band_km2_high: 979000, swing_km2: 40000 },
      { factor: 'guard', label: 'Thin-ice guard (FIXTURE)', band_km2_low: 1009000, band_km2_high: 989000, swing_km2: 20000 },
    ],
  },
  sources: { fixture_a: fakeProv('A'), fixture_b: fakeProv('B'), fixture_c: fakeProv('C'), fixture_d: fakeProv('D'), fixture_e: fakeProv('E') },
  cards,
}, null, 1));
console.log(`fixture: ${N} cells, ${winters.length} winters -> ${out}`);
