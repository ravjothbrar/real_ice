import type { Atlas } from './data';

export type PatternName = 'dots' | 'hatch' | 'amber' | 'dither';

export interface PaintGroup {
  key: string;
  cells: Int32Array;
  fill?: string;
  pattern?: PatternName;
  glow?: boolean;
}

export interface LegendItem {
  label: string;
  fill?: string;
  pattern?: PatternName;
  outline?: boolean;
}

export interface UILayer {
  id: string;
  label: string;
  chip: string; // panel state chip: OBS / MODEL / PRIOR / REANALYSIS
  needs: string[]; // data layers required
  field?: string; // continuous layers
  bins?: number[]; // bin edges for stepped ramps (n edges -> n-1 classes + overflow)
  fmt?: (v: number) => string;
  isStatic?: boolean;
}

export const RAMP = ['#0d2329', '#103642', '#155066', '#1d7090', '#2e98bf', '#4cc9f0', '#a8e9fb'];
export const MINT = '#64f0c8';
export const CYAN = '#4cc9f0';
export const AMBER = '#f2b84b';

const f2 = (v: number) => v.toFixed(2);
const f1 = (v: number) => v.toFixed(1);
const pct = (v: number) => `${Math.round(v * 100)}%`;
const int = (v: number) => Math.round(v).toLocaleString('en-GB');

export const UI_LAYERS: UILayer[] = [
  { id: 'h0', label: 'START THICKNESS', chip: 'OBS', needs: ['h0'], field: 'h0', bins: [0, 0.5, 1, 1.5, 2, 2.5, 3], fmt: f1 },
  { id: 'h0_spread', label: 'THICKNESS SPREAD', chip: 'OBS', needs: ['h0_spread'], field: 'h0_spread', bins: [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.75], fmt: f2 },
  { id: 'fdd', label: 'FREEZING DEGREE DAYS', chip: 'REANALYSIS', needs: ['fdd'], field: 'fdd', bins: [0, 1000, 2000, 3000, 4000, 5000, 6000], fmt: int },
  { id: 'hs', label: 'SURVIVAL THICKNESS', chip: 'PRIOR', needs: ['hs'], field: 'hs', bins: [0, 0.8, 1.2, 1.6, 2.0, 2.4, 2.8], fmt: f1 },
  { id: 'R', label: 'RETENTION', chip: 'MODEL', needs: ['R'], field: 'R', bins: [0, 0.2, 0.4, 0.6, 0.8, 0.95, 1.01], fmt: pct },
  { id: 'band', label: 'SURVIVAL GAP', chip: 'MODEL', needs: ['p_without', 'p_with'] },
  { id: 'sept_presence', label: 'SEPT PRESENCE 2012–2025', chip: 'OBS', needs: ['sept_presence'], field: 'sept_presence', bins: [0, 0.2, 0.4, 0.6, 0.8, 0.95, 1.01], fmt: pct, isStatic: true },
];
export const EXCL_LAYER = { id: 'excl', label: 'EXCLUSIONS', chip: 'STATIC' };

export interface Thresholds { survives: number; hopeless: number; uplift: number }

export function thresholds(atlas: Atlas, uplift: number): Thresholds {
  const t = atlas.summary.thresholds ?? {};
  return { survives: t.survives ?? 0.7, hopeless: t.hopeless ?? 0.2, uplift };
}

export const BAND_CLASSES = ['BAND', 'SURVIVES', 'HOPELESS', 'BLOCKED', 'LOW UPLIFT'] as const;
export type BandClass = 0 | 1 | 2 | 3 | 4 | -1;

/** Classify every cell for a winter. -1 = no data. Order: blocked, survives, hopeless, band, low uplift. */
export function classify(atlas: Atlas, w: number, t: Thresholds): Int8Array {
  const n = atlas.n;
  const out = new Int8Array(n).fill(-1);
  const pwo = atlas.raw('p_without', w);
  const pw = atlas.raw('p_with', w);
  if (!pwo || !pw) return out;
  const up = atlas.raw('uplift', w);
  const bl = atlas.raw('blocked', w);
  const m = atlas.manifest.layers;
  const d = (name: string, b: number) => b * m[name].scale + m[name].offset;
  for (let k = 0; k < n; k++) {
    if (pwo[k] === 255 || pw[k] === 255) continue;
    const a = d('p_without', pwo[k]);
    const b = d('p_with', pw[k]);
    const u = up && up[k] !== 255 ? d('uplift', up[k]) : b - a;
    if (bl && bl[k] !== 255 && bl[k] > 0) out[k] = 3;
    else if (a >= t.survives) out[k] = 1;
    else if (b <= t.hopeless) out[k] = 2;
    else if (u >= t.uplift - 1e-9) out[k] = 0;
    else out[k] = 4;
  }
  return out;
}

export function exclMask(atlas: Atlas): Uint8Array | null {
  return atlas.stat['excl'] ?? null;
}

function collect(n: number, test: (k: number) => boolean): Int32Array {
  let c = 0;
  for (let k = 0; k < n; k++) if (test(k)) c++;
  const out = new Int32Array(c);
  c = 0;
  for (let k = 0; k < n; k++) if (test(k)) out[c++] = k;
  return out;
}

export function bandPaint(cls: Int8Array): { groups: PaintGroup[]; legend: LegendItem[] } {
  const n = cls.length;
  const groups: PaintGroup[] = [
    { key: 'low', cells: collect(n, (k) => cls[k] === 4), fill: '#11272c' },
    { key: 'surv', cells: collect(n, (k) => cls[k] === 1), fill: 'rgba(76,201,240,0.30)' },
    { key: 'hope', cells: collect(n, (k) => cls[k] === 2), fill: '#0d1517', pattern: 'dots' },
    { key: 'block', cells: collect(n, (k) => cls[k] === 3), fill: '#0a1214', pattern: 'hatch' },
    { key: 'band', cells: collect(n, (k) => cls[k] === 0), fill: MINT, glow: true },
  ];
  const legend: LegendItem[] = [
    { label: 'BAND', fill: MINT },
    { label: 'SURVIVES ANYWAY', fill: 'rgba(76,201,240,0.45)' },
    { label: 'HOPELESS', fill: '#0d1517', pattern: 'dots' },
    { label: 'BLOCKED <0.6 M', fill: '#0a1214', pattern: 'hatch' },
    { label: 'LOW UPLIFT', fill: '#11272c', outline: true },
  ];
  return { groups, legend };
}

export function rampPaint(atlas: Atlas, L: UILayer, w: number): { groups: PaintGroup[]; legend: LegendItem[] } {
  const a = atlas.raw(L.field!, w)!;
  const bins = L.bins!;
  const meta = atlas.manifest.layers[L.field!];
  const nb = bins.length - 1;
  const cls = new Int8Array(atlas.n).fill(-1);
  for (let k = 0; k < atlas.n; k++) {
    if (a[k] === 255) continue;
    const v = a[k] * meta.scale + meta.offset;
    let b = 0;
    while (b < nb - 1 && v >= bins[b + 1]) b++;
    cls[k] = b;
  }
  const groups: PaintGroup[] = [];
  const legend: LegendItem[] = [];
  const unit = meta.unit ? ` ${meta.unit.toUpperCase()}` : '';
  for (let b = 0; b < nb; b++) {
    groups.push({ key: `r${b}`, cells: collect(atlas.n, (k) => cls[k] === b), fill: RAMP[b] });
    const lo = L.fmt!(bins[b]);
    const label = b === nb - 1 ? `≥${lo}` : `${lo}–${L.fmt!(bins[b + 1])}`;
    legend.push({ label: b === 0 ? `${label}${unit}` : label, fill: RAMP[b] });
  }
  // Uncertain start thickness is dithered (opacity/dither encodes confidence, never blur).
  if (L.id === 'h0') {
    const sp = atlas.raw('h0_spread', w);
    if (sp) {
      const sm = atlas.manifest.layers['h0_spread'];
      groups.push({ key: 'dither', cells: collect(atlas.n, (k) => sp[k] !== 255 && a[k] !== 255 && sp[k] * sm.scale + sm.offset >= 0.3), pattern: 'dither' });
      legend.push({ label: 'DITHER = SPREAD ≥0.3 M', fill: '#155066', pattern: 'dither' });
    }
  }
  return { groups, legend };
}

export function exclPaint(atlas: Atlas): PaintGroup | null {
  const e = exclMask(atlas);
  if (!e) return null;
  return { key: 'excl', cells: collect(atlas.n, (k) => e[k] !== 255 && e[k] > 0), pattern: 'amber' };
}
