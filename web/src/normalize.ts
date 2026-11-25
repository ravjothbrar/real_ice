// Accept the pipeline's export (pipeline/export.py) as well as the canonical keys in web/README.md.
// Everything here renames or reshapes; nothing is invented. Missing inputs stay missing.
import type { Manifest, Summary, Card, Source, HindcastMetric } from './types';

type Any = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

// pipeline layer name -> UI layer name
const LAYER_ALIAS: [string, string][] = [
  ['sept_freq', 'sept_presence'],
  ['excluded', 'excl'],
  ['spread', 'h0_spread'],
  ['disagree', 'h0_spread'], // used only when no per-winter spread exists
];
// pipeline card key -> UI card key
const CARD_ALIAS: [string, string][] = [
  ['disagree', 'h0_spread'],
  ['spread', 'h0_spread'],
  ['gap', 'band'],
  ['sept_freq', 'sept_presence'],
  ['excluded', 'excl'],
  ['scale', 'band_area'],
  ['scale', 'energy'],
  ['scale', 'fleet'],
];
const SOURCE_SHORT: Record<string, string> = {
  thickness_cpom: 'CPOM CRYOSAT-2',
  thickness_petty: 'ICESAT-2 + SMOS (PETTY ET AL.)',
  thickness_awi: 'AWI CS2SMOS',
  era5_arco: 'ERA5',
  osisaf: 'OSI SAF',
  piomas: 'PIOMAS',
  gebco: 'GEBCO / IBCAO',
  naturalearth: 'NATURAL EARTH',
  shipping_corridors_hand: 'SHIPPING CORRIDORS (HAND-DRAWN)',
};
const UNITLESS = new Set(['fraction', 'probability', '0/1', 'bits', 'code', 'flag']);

export function normalizeManifest(m: Manifest & Any): Manifest {
  const layers = { ...(m.layers ?? {}) };
  const rename = (list: string[], from: string, to: string) => list.map((n) => (n === from ? to : n));
  let st = [...(m.static_layers ?? [])];
  let wl = [...(m.winter_layers ?? [])];
  for (const [from, to] of LAYER_ALIAS) {
    if (!(from in layers) || to in layers) continue;
    layers[to] = layers[from];
    delete layers[from];
    st = rename(st, from, to);
    wl = rename(wl, from, to);
  }
  for (const [name, L] of Object.entries(layers)) {
    const l = { ...L };
    if (l.unit && UNITLESS.has(l.unit)) l.unit = '';
    if (l.unit === 'K day') l.unit = 'K·day';
    if (!l.unc_layer && `${name}_sd` in layers) l.unc_layer = `${name}_sd`;
    layers[name] = l;
  }
  if (layers['excl'] && !layers['excl'].flags) {
    // bit meanings as documented in pipeline/export.py ("1 settlement, 2 protected, 4 shipping")
    layers['excl'] = { ...layers['excl'], flags: { 1: 'Settlement buffer', 2: 'Protected area', 4: 'Shipping corridor (hand-drawn)' } };
  }
  const g = m.grid ?? {};
  const grid = {
    ...g,
    name: g.name ?? (g.epsg ? `EASE2-N ${(g.res_m ?? g.res ?? 25000) / 1000} km (EPSG:${g.epsg})` : undefined),
    crop: g.crop ?? 360,
  };
  return { ...m, grid, layers, static_layers: st, winter_layers: wl };
}

export function sourcesFrom(m: Manifest, s: Any): Source[] {
  if (m.sources?.length) return m.sources;
  const prov = s.sources;
  if (!prov || typeof prov !== 'object' || Array.isArray(prov)) return Array.isArray(prov) ? prov : [];
  return Object.entries(prov as Any).map(([id, p]) => ({
    id,
    name: p.dataset ?? p.name ?? id,
    short: SOURCE_SHORT[id] ?? id.replace(/_/g, ' ').toUpperCase(),
    authors: p.authors,
    doi: p.doi,
    url: p.url,
    licence: p.licence,
    accessed: p.accessed ?? p.access_date,
  }));
}

export function normalizeSummary(s: Any, m: Manifest): Summary {
  const out: Any = { ...s };
  // thresholds
  const t = s.thresholds ?? {};
  out.thresholds = {
    survives: t.survives ?? t.survives_p_without,
    hopeless: t.hopeless ?? t.hopeless_p_with,
    uplift: t.uplift,
    guard_m: t.guard_m,
    blocked_frac: t.blocked_frac,
  };
  // scale
  const sc = s.scale ?? {};
  out.scale = {
    ...sc,
    target_source: sc.target_source ?? sc.source,
    energy_source: sc.energy_source ?? sc.source,
    ice_safe_days: sc.ice_safe_days ?? sc.window_days,
    throughput_default: sc.throughput_default ?? sc.throughput_default_km2_per_drone_day,
    share_of_ice_area: sc.share_of_ice_area ?? 0.05,
  };
  // calibration
  const c = s.calibration;
  if (c && c.modelled_cm == null && (c.calibrated || c.uncalibrated)) {
    out.calibration = {
      site: typeof c.site === 'string' ? c.site.split(',')[0] : 'Cambridge Bay',
      winter_label: typeof c.winter === 'string' ? c.winter : undefined,
      winter: typeof c.winter === 'number' ? c.winter : undefined,
      modelled_cm: c.calibrated?.diff_m != null ? c.calibrated.diff_m * 100 : undefined,
      uncalibrated_cm: c.uncalibrated?.diff_m != null ? c.uncalibrated.diff_m * 100 : undefined,
      paper_cm: c.paper_diff_m != null ? c.paper_diff_m * 100 : 32,
      alpha: c.alpha,
      source: c.paper,
      note: typeof c.site === 'string' && c.site.includes('(') ? c.site.slice(c.site.indexOf('(') + 1, c.site.lastIndexOf(')')) : undefined,
    };
    if (out.calibration.modelled_cm == null) delete out.calibration;
  }
  // hindcast
  const h = s.hindcast;
  if (h && !h.metrics) {
    const metrics: HindcastMetric[] = [];
    const three = (o: Any | undefined, label: string, key: string, model = 'model', thin = 'baseline_thin_ice', edge = 'baseline_edge_distance', modelLabel = 'Atlas P(survive without)') => {
      if (!o || o[model] == null || !Number.isFinite(o[model])) return;
      const rows = [{ label: modelLabel, value: o[model], model: true }];
      if (Number.isFinite(o[thin])) rows.push({ label: 'Thin ice = at risk', value: o[thin], model: false });
      if (Number.isFinite(o[edge])) rows.push({ label: 'Distance to September ice edge', value: o[edge], model: false });
      metrics.push({ key, label, rows });
    };
    three(h.auc_cell_year, 'AUC: ice present next September (cell-years)', 'auc');
    three(h.spearman_vs_presence, 'Spearman ρ vs September presence frequency', 'spearman');
    three(h.band_overlap_with_marginal, 'Share of band cells that flip between Septembers', 'overlap', 'model_band', 'baseline_thin_ice_same_k', 'baseline_edge_distance_same_k', 'Atlas band');
    const ws: number[] = Array.isArray(h.winters) ? h.winters : [];
    out.hindcast = {
      period: ws.length ? `Septembers ${Math.min(...ws) + 1}–${Math.max(...ws) + 1}` : undefined,
      source: ['OSI SAF September sea-ice concentration', h.command ? `\`${h.command}\`` : ''].filter(Boolean).join(' · '),
      date: h.built,
      metrics,
      beats_both: h.beats_both,
      beats_label: 'AUC and Spearman ρ',
    };
    if (!metrics.length) delete out.hindcast;
  }
  // sensitivity
  const se = s.sensitivity;
  if (se && !se.rows && Array.isArray(se.factors)) {
    const base = se.base_band_km2;
    out.sensitivity = {
      target: 'Band area',
      unit: 'km²',
      method: se.method,
      winter: se.winter,
      base,
      rows: se.factors.map((f: Any) => ({
        key: f.factor,
        label: f.label,
        low: base != null && f.band_km2_low != null ? f.band_km2_low - base : undefined,
        high: base != null && f.band_km2_high != null ? f.band_km2_high - base : undefined,
        value: f.swing_km2,
      })),
    };
  }
  // cards: not_proof_of -> not_proof, and key aliases
  const cards: Record<string, Card> = {};
  for (const [k, v] of Object.entries((s.cards ?? {}) as Any)) {
    if (!v) continue;
    const card = { meaning: v.meaning, why: v.why ?? v.why_it_matters, not_proof: v.not_proof ?? v.not_proof_of, example: v.example };
    if (card.meaning && card.why && card.not_proof && card.example) cards[k] = card;
  }
  for (const [from, to] of CARD_ALIAS) if (cards[from] && !cards[to]) cards[to] = cards[from];
  out.cards = cards;
  void m;
  return out as Summary;
}
