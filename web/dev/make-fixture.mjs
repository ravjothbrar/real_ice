// SYNTHETIC development fixture for the Survival Gap Atlas front end.
// Every value written here is invented and must never be shown as data. It exists only so the
// UI can be developed before `make export` produces web/public/data/. Output: web/dev/fixture-data/
// Usage: node dev/make-fixture.mjs   (then open the dev server with ?fixture=1)
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

const staticLayers = ['sept_presence', 'excl'];
const winterLayers = ['h0', 'h0_spread', 'fdd', 'hs', 'R', 'p_without', 'p_with', 'uplift', 'blocked'];
const layers = {
  h0: { scale: 0.02, offset: 0, unit: 'm', title: 'Start thickness', source: 'FIXTURE (synthetic)', date: 'Nov {W}', unc_layer: 'h0_spread' },
  h0_spread: { scale: 0.01, offset: 0, unit: 'm', title: 'Thickness spread', source: 'FIXTURE (synthetic)', date: 'Nov {W}' },
  fdd: { scale: 25, offset: 0, unit: 'K·day', title: 'Freezing degree days', source: 'FIXTURE (synthetic)', date: 'Nov {W} – May {W1}', unc: 'FIXTURE: no uncertainty' },
  hs: { scale: 0.02, offset: 0, unit: 'm', title: 'Survival thickness', source: 'FIXTURE (synthetic)', date: 'May–Sep {W1}', unc: 'FIXTURE: prior range' },
  R: { scale: 1 / 250, offset: 0, unit: '', title: 'Retention', source: 'FIXTURE (synthetic)', date: '1 Nov {W} – 15 Sep {W1}' },
  p_without: { scale: 1 / 250, offset: 0, unit: '', title: 'P(survive) without', source: 'FIXTURE (synthetic)', date: 'Sep {W1}' },
  p_with: { scale: 1 / 250, offset: 0, unit: '', title: 'P(survive) with', source: 'FIXTURE (synthetic)', date: 'Sep {W1}' },
  uplift: { scale: 1 / 250, offset: 0, unit: '', title: 'Uplift', source: 'FIXTURE (synthetic)', date: 'Sep {W1}' },
  blocked: { scale: 1, offset: 0, unit: '', title: '0.6 m guard', source: 'FIXTURE (synthetic)', date: 'Nov {W}' },
  sept_presence: { scale: 1 / 250, offset: 0, unit: '', title: 'Sept presence 2012–2025', source: 'FIXTURE (synthetic)', date: 'Sep 2012–2025' },
  excl: { scale: 1, offset: 0, unit: '', title: 'Exclusions', source: 'FIXTURE (synthetic)', date: 'static', flags: { 1: 'Settlement buffer', 2: 'Protected area', 4: 'Shipping corridor (hand-drawn)' } },
};
const enc = (name, v) => { if (v == null || !Number.isFinite(v)) return 255; const L = layers[name]; return Math.max(0, Math.min(254, Math.round((v - L.offset) / L.scale))); };

const cellsBuf = new Uint16Array(N * 2);
cells.forEach(([i, j], k) => { cellsBuf[2 * k] = i; cellsBuf[2 * k + 1] = j; });
writeFileSync(join(out, 'cells.bin'), Buffer.from(cellsBuf.buffer));

const st = new Uint8Array(N * staticLayers.length);
cells.forEach(([i, j, lon, lat], k) => {
  const x = (-HALF + RES * (j + 0.5)) / 1e6, y = (HALF - RES * (i + 0.5)) / 1e6;
  st[k] = enc('sept_presence', sig((1.9 - Math.hypot(x + 0.5, y + 0.2)) * 3.2));
  let f = 0;
  for (const [slo, sla] of settlements) { const [sx, sy] = forward(slo, sla); if (Math.hypot(x * 1e6 - sx, y * 1e6 - sy) < 90e3) f |= 1; }
  if (lon > 8 && lon < 30 && lat > 76 && lat < 81) f |= 2;
  if ((lon > 50 && lon < 175 && Math.abs(lat - (76 - 0.02 * (lon - 50))) < 0.6) || (lon > -125 && lon < -80 && Math.abs(lat - 74.3) < 0.45)) f |= 4;
  st[N + k] = f;
});
writeFileSync(join(out, 'static.bin'), st);

const winters = [];
const bandArea = {};
for (let w = 2018; w <= 2026; w++) {
  const partial = w === 2026;
  const buf = new Uint8Array(N * winterLayers.length).fill(255);
  const ph = (w - 2018) * 0.9;
  let nb = 0;
  cells.forEach(([i, j], k) => {
    const x = (-HALF + RES * (j + 0.5)) / 1e6, y = (HALF - RES * (i + 0.5)) / 1e6;
    const d = Math.hypot(x + 0.6 + 0.15 * Math.sin(ph), y + 0.3);
    const h0 = Math.max(0.05, 0.25 + 2.3 * Math.exp(-(d * d) / 2.2) + 0.18 * Math.sin(ph + 2 * x) + 0.08 * Math.sin(9 * x) * Math.cos(7 * y));
    const spread = 0.08 + 0.32 * Math.abs(Math.sin(3 * x + ph) * Math.cos(2 * y));
    const fdd = (partial ? 0.25 : 1) * (1500 + 3600 * Math.exp(-(x * x + y * y) / 3.5));
    buf[k] = enc('h0', h0); buf[N + k] = enc('h0_spread', spread); buf[2 * N + k] = enc('fdd', fdd);
    if (partial) return;
    const hs = 1.0 + 1.2 * sig((y - 0.3 * x - 0.2) * 2.2);
    const R = 0.97 - 0.85 * sig((-y - 1.0 + 0.6 * x) * 3.5);
    const hend = Math.sqrt(h0 * h0 + 0.0009 * fdd) * 0.82;
    const blocked = h0 < 0.6 ? 1 : 0;
    const G = blocked ? 0 : 0.5 * fdd / 4000;
    const pwo = sig((hend - hs) / 0.22) * R;
    const pw = sig((hend + G - hs) / 0.22) * R;
    buf[3 * N + k] = enc('hs', hs); buf[4 * N + k] = enc('R', R);
    buf[5 * N + k] = enc('p_without', pwo); buf[6 * N + k] = enc('p_with', pw);
    buf[7 * N + k] = enc('uplift', pw - pwo); buf[8 * N + k] = blocked;
    if (!blocked && pwo < 0.7 && pw > 0.2 && pw - pwo >= 0.2) nb++;
  });
  writeFileSync(join(out, `winter-${w}.bin`), buf);
  winters.push({ w, label: `${w}/${String((w + 1) % 100).padStart(2, '0')}`, partial, ...(partial ? { layers: ['h0', 'h0_spread', 'fdd'], note: 'FIXTURE: partial season' } : {}) });
  bandArea[w] = nb * 625;
}

const sources = [
  { id: 'fx-a', short: 'FIXTURE-A', name: 'Synthetic source A (fixture)' },
  { id: 'fx-b', short: 'FIXTURE-B', name: 'Synthetic source B (fixture)' },
  { id: 'fx-c', short: 'FIXTURE-C', name: 'Synthetic source C (fixture)' },
  { id: 'fx-d', short: 'FIXTURE-D', name: 'Synthetic source D (fixture)' },
  { id: 'fx-e', short: 'FIXTURE-E', name: 'Synthetic source E (fixture)' },
];
writeFileSync(join(out, 'manifest.json'), JSON.stringify({
  fixture: true,
  built: '2026-11-25',
  grid: { name: 'EASE2-N 25 km (EPSG:6931)', res_m: RES, crop: CROP, half_m: HALF, cell_area_km2: 625 },
  n_cells: N, winters, default_winter: 2026, static_layers: staticLayers, winter_layers: winterLayers, layers, sources,
}, null, 1));

const card = (m, w, n, e) => ({ meaning: `FIXTURE. ${m}`, why: `FIXTURE. ${w}`, not_proof: `FIXTURE. ${n}`, example: `FIXTURE. ${e}` });
const cards = {
  h0: card('Synthetic start-of-winter thickness.', 'Thicker start ice needs less help.', 'Not a measurement.', 'Cell X: 9.99 m (fake).'),
  h0_spread: card('Synthetic product disagreement.', 'Wide spread = low confidence.', 'Not an error bar from any product.', 'Cell X: 0.99 m (fake).'),
  fdd: card('Synthetic freezing degree days.', 'More cold, more growth.', 'Not ERA5.', 'Cell X: 9999 K·day (fake).'),
  hs: card('Synthetic survival thickness.', 'The bar the ice must clear.', 'Not van Dijke values.', 'Cell X: 9.99 m (fake).'),
  R: card('Synthetic retention.', 'Ice that drifts out is lost.', 'Not OSI SAF drift.', 'Cell X: 0.99 (fake).'),
  band: card('Synthetic band classes.', 'Where flooding would change the outcome.', 'Not a deployment site.', 'Winter X: 99,999 km² (fake).'),
  sept_presence: card('Synthetic September presence.', 'Observed check for the model.', 'Not concentration data.', 'Cell X: 0.99 (fake).'),
  excl: card('Synthetic exclusion buffers.', 'Places thickening must not go.', 'Not the full set of places that matter.', 'Fake buffer 99 km.'),
  p_without: card('Synthetic survival probability without flooding.', 'Baseline.', 'Not a forecast.', '0.99 (fake).'),
  p_with: card('Synthetic survival probability with flooding.', 'Upper case.', 'Not a forecast.', '0.99 (fake).'),
  uplift: card('Synthetic uplift.', 'What the band is built from.', 'Not causal proof.', '0.99 (fake).'),
  band_area: card('Synthetic band area.', 'Compares with the 1M km² plan.', 'Not available area.', '99,999 km² (fake).'),
  energy: card('Band area × 8 MWh/km².', 'Energy scale of the plan.', 'Not a costed design.', '9,999 GWh (fake).'),
  fleet: card('Area ÷ (throughput × days).', 'Fleet scale.', 'Not a fleet design; throughput is assumed.', '999 drones (fake).'),
  sensitivity: card('Synthetic tornado.', 'Shows which input moves the band most.', 'Not a full uncertainty analysis.', '±99,999 km² (fake).'),
  calibration: card('Synthetic calibration.', 'Ties the model to the field paper.', 'Not validation elsewhere.', 'Modelled 12.3 cm (fake).'),
  hindcast: card('Synthetic hindcast.', 'Checks against observed September ice.', 'Not a forecast skill score.', 'ρ 0.50 (fake).'),
};
writeFileSync(join(out, 'summary.json'), JSON.stringify({
  fixture: true,
  built: '2026-11-25',
  ensemble_n: 1000,
  thresholds: { survives: 0.7, hopeless: 0.2, uplift: 0.2, guard_m: 0.6 },
  band_area_km2: bandArea,
  scale: {
    target_km2: 1000000, target_source: 'Real Ice scale model, Ocean Visions roadmap',
    mwh_per_km2: 8, energy_source: 'Ocean Visions roadmap',
    ice_safe_days: 90, ice_safe_note: 'Jan–Mar window',
    arctic_ice_area_km2: 12345678, arctic_ice_area_source: 'FIXTURE (synthetic)',
    throughput_default: 0.5, throughput_min: 0.05, throughput_max: 5,
  },
  calibration: { site: 'Cambridge Bay', winter: 2024, modelled_cm: 12.3, paper_cm: 32, alpha: 9.99, source: 'FIXTURE (synthetic); paper: AGU 10.1029/2025EF007894', date: 'mid-May 2025', note: 'FIXTURE: invented numbers' },
  hindcast: {
    period: '2012–2025', source: 'FIXTURE (synthetic)', date: '2026-11-25',
    metrics: [
      { key: 'spearman', label: 'Spearman ρ vs Sept presence', rows: [{ label: 'Atlas P_without', value: 0.5, model: true }, { label: 'Thin ice = at risk', value: 0.25 }, { label: 'Distance to Sept edge', value: 0.125 }] },
      { key: 'overlap', label: 'Band ∩ marginal cells', rows: [{ label: 'Atlas band', value: 0.4, model: true }, { label: 'Thin ice = at risk', value: 0.2 }, { label: 'Distance to Sept edge', value: 0.1 }] },
    ],
    verdict: 'FIXTURE: synthetic comparison',
  },
  sensitivity: {
    target: 'Band area', unit: 'km²', method: 'one-at-a-time (FIXTURE)', winter: 2024,
    rows: [
      { key: 'hs', label: 'Survival thickness', low: -99000, high: 88000 },
      { key: 'h0', label: 'Start thickness', low: -77000, high: 66000 },
      { key: 'G', label: 'Flooding gain', low: -55000, high: 44000 },
      { key: 'melt_days', label: 'Melt days', low: -33000, high: 22000 },
      { key: 'R', label: 'Retention', low: -11000, high: 9000 },
    ],
  },
  cards,
}, null, 1));
console.log(`fixture: ${N} cells, ${winters.length} winters -> ${out}`);
