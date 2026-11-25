import type { Manifest, Summary } from './types';
import { normalizeManifest, normalizeSummary, sourcesFrom } from './normalize';

// Where data comes from:
//  - single-file build: window.__ATLAS_DATA__ (inlined by scripts/inline-single.mjs)
//  - dev with ?fixture=1: /dev/fixture-data/ (SYNTHETIC; never part of a production build)
//  - otherwise: data/ (web/public/data, written by `make export`)
function baseUrl(): string {
  if (import.meta.env.DEV && new URLSearchParams(location.search).has('fixture')) return 'dev/fixture-data/';
  return 'data/';
}
const BASE = baseUrl();

function b64ToBytes(s: string): Uint8Array {
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export class MissingData extends Error {}

export async function getJSON<T>(name: string): Promise<T> {
  const inl = window.__ATLAS_DATA__;
  if (inl) {
    if (!(name in inl)) throw new MissingData(name);
    return inl[name] as T;
  }
  const r = await fetch(BASE + name);
  if (!r.ok) throw new MissingData(name);
  const ct = r.headers.get('content-type') || '';
  if (ct.includes('text/html')) throw new MissingData(name); // dev-server SPA fallback
  return (await r.json()) as T;
}

export async function getBin(name: string): Promise<Uint8Array> {
  const inl = window.__ATLAS_DATA__;
  if (inl) {
    if (!(name in inl)) throw new MissingData(name);
    return b64ToBytes(inl[name] as string);
  }
  const r = await fetch(BASE + name);
  if (!r.ok) throw new MissingData(name);
  const ct = r.headers.get('content-type') || '';
  if (ct.includes('text/html')) throw new MissingData(name);
  return new Uint8Array(await r.arrayBuffer());
}

export class Atlas {
  n: number;
  ci: Uint16Array;
  cj: Uint16Array;
  index: Int32Array; // i * crop + j -> cell index, -1 when not an atlas cell
  crop: number;
  cellArea: number;
  stat: Record<string, Uint8Array> = {};
  winters = new Map<number, Record<string, Uint8Array>>();
  private pending = new Map<number, Promise<Record<string, Uint8Array>>>();

  constructor(public manifest: Manifest, public summary: Summary, cells: Uint8Array, stat: Uint8Array | null) {
    const n = manifest.n_cells;
    this.n = n;
    this.crop = manifest.grid.crop ?? 360;
    this.cellArea = manifest.grid.cell_area_km2 ?? 625;
    const dv = new DataView(cells.buffer, cells.byteOffset, cells.byteLength);
    this.ci = new Uint16Array(n);
    this.cj = new Uint16Array(n);
    this.index = new Int32Array(this.crop * this.crop).fill(-1);
    for (let k = 0; k < n; k++) {
      const i = dv.getUint16(4 * k, true);
      const j = dv.getUint16(4 * k + 2, true);
      this.ci[k] = i;
      this.cj[k] = j;
      this.index[i * this.crop + j] = k;
    }
    if (stat) manifest.static_layers.forEach((name, li) => (this.stat[name] = stat.subarray(li * n, (li + 1) * n)));
  }

  hasLayer(name: string): boolean {
    return name in this.manifest.layers;
  }

  async loadWinter(w: number): Promise<Record<string, Uint8Array>> {
    const have = this.winters.get(w);
    if (have) return have;
    let p = this.pending.get(w);
    if (!p) {
      p = getBin(`winter-${w}.bin`).then((buf) => {
        const n = this.n;
        const rec: Record<string, Uint8Array> = {};
        const meta = this.manifest.winters.find((x) => x.w === w);
        this.manifest.winter_layers.forEach((name, li) => {
          const a = buf.subarray(li * n, (li + 1) * n);
          if (meta?.layers && !meta.layers.includes(name)) return;
          if (a.length < n) return;
          let any = false;
          for (let k = 0; k < n; k++) if (a[k] !== 255) { any = true; break; }
          if (any) rec[name] = a;
        });
        this.winters.set(w, rec);
        return rec;
      });
      this.pending.set(w, p);
    }
    return p;
  }

  /** Raw byte array for a layer in a winter (static layers ignore w). */
  raw(name: string, w: number): Uint8Array | undefined {
    return this.stat[name] ?? this.winters.get(w)?.[name];
  }

  decode(name: string, b: number): number {
    const m = this.manifest.layers[name];
    return b * m.scale + m.offset;
  }

  value(name: string, w: number, k: number): number | null {
    const a = this.raw(name, w);
    if (!a || a[k] === 255) return null;
    return this.decode(name, a[k]);
  }
}

export async function loadAtlas(): Promise<{ atlas: Atlas; land: GeoJSON.GeoJsonObject | null }> {
  const manifest = normalizeManifest(await getJSON<Manifest>('manifest.json'));
  const [rawSummary, cells, stat, land] = await Promise.all([
    getJSON<Record<string, unknown>>('summary.json').catch(() => ({})),
    getBin('cells.bin'),
    manifest.static_layers?.length ? getBin('static.bin').catch(() => null) : Promise.resolve(null),
    getJSON<GeoJSON.GeoJsonObject>('land.json').catch(() => null),
  ]);
  manifest.sources = sourcesFrom(manifest, rawSummary);
  const summary: Summary = normalizeSummary(rawSummary, manifest);
  return { atlas: new Atlas(manifest, summary, cells, stat), land };
}
