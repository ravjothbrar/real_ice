import type { Atlas } from './data';
import { AtlasMap, reduced, type Marker, type Region } from './map';
import {
  UI_LAYERS, EXCL_LAYER, BAND_CLASSES, classify, thresholds, bandPaint, rampPaint, exclPaint,
  type UILayer, type LegendItem, type PaintGroup, MINT,
} from './layers';
import { esc, fmtInt, fmtNum, fmtEnergy, fmtLat, fmtLon, fillDate, guideHTML, swatchSVG } from './util';
import type { Card } from './types';

export const REGIONS: Region[] = [
  { id: 'pan', label: 'PAN-ARCTIC' },
  { id: 'beaufort', label: 'BEAUFORT', center: [-145, 74.5], span: 9.5 },
  { id: 'transpolar', label: 'TRANSPOLAR', center: [40, 84.5], span: 12 },
  { id: 'caa', label: 'CANADIAN ARCHIPELAGO', center: [-97, 74.5], span: 8.5 },
  { id: 'bk', label: 'BARENTS-KARA', center: [55, 76], span: 10 },
];

// Real positions (WGS84). Settlements are circles; straits (export gates) are diamonds.
export const MARKERS: Marker[] = [
  { id: 'cambridge-bay', name: 'Cambridge Bay', lon: -105.0597, lat: 69.1169, kind: 'hero', note: 'Real Ice field work, winters 2024–2026. Test site about 7 km offshore; exact coordinates not public.' },
  { id: 'nome', name: 'Nome', lon: -165.4064, lat: 64.5011, kind: 'settlement', note: 'Real Ice test, Feb 2023. Qualitative sanity cell only; no public field data.' },
  { id: 'resolute', name: 'Resolute', lon: -94.8297, lat: 74.6973, kind: 'settlement', labelZoom: 2.2 },
  { id: 'utqiagvik', name: 'Utqiaġvik', lon: -156.7887, lat: 71.2906, kind: 'settlement' },
  { id: 'tuktoyaktuk', name: 'Tuktoyaktuk', lon: -133.0342, lat: 69.4454, kind: 'settlement', labelZoom: 1.6 },
  { id: 'qaanaaq', name: 'Qaanaaq', lon: -69.2285, lat: 77.467, kind: 'settlement', labelZoom: 2.2 },
  { id: 'longyearbyen', name: 'Longyearbyen', lon: 15.6267, lat: 78.2232, kind: 'settlement' },
  { id: 'tiksi', name: 'Tiksi', lon: 128.8681, lat: 71.6369, kind: 'settlement' },
  { id: 'pevek', name: 'Pevek', lon: 170.3133, lat: 69.7008, kind: 'settlement', labelZoom: 1.4 },
  { id: 'fram', name: 'Fram Strait', lon: -3, lat: 79, kind: 'site', note: 'Main export gate for Arctic sea ice.' },
  { id: 'bering', name: 'Bering Strait', lon: -168.9, lat: 65.8, kind: 'site', note: 'Pacific gateway.', labelZoom: 2.5 },
  { id: 'nares', name: 'Nares Strait', lon: -70, lat: 80, kind: 'site', note: 'Export gate between Greenland and Ellesmere Island.', minZoom: 2, labelZoom: 2.5 },
];

interface CellRow { name: string; label: string; card: string; alt?: string; digits: number }
const CELL_ROWS: CellRow[] = [
  { name: 'h0', label: 'START THICKNESS', card: 'h0', digits: 2 },
  { name: 'h0_spread', label: 'THICKNESS SPREAD', card: 'h0_spread', digits: 2 },
  { name: 'fdd', label: 'FREEZING DEGREE DAYS', card: 'fdd', digits: 0 },
  { name: 'hs', label: 'SURVIVAL THICKNESS', card: 'hs', digits: 2 },
  { name: 'R', label: 'RETENTION', card: 'R', digits: 2 },
  { name: 'p_without', label: 'P(SURVIVE) WITHOUT', card: 'p_without', alt: 'uplift', digits: 2 },
  { name: 'p_with', label: 'P(SURVIVE) WITH', card: 'p_with', alt: 'uplift', digits: 2 },
  { name: 'uplift', label: 'UPLIFT', card: 'uplift', digits: 2 },
  { name: 'sept_presence', label: 'SEPT PRESENCE 2012–2025', card: 'sept_presence', digits: 2 },
];

const METRIC_CARDS: [string, string][] = [
  ['p_without', 'P(SURVIVE) WITHOUT'], ['p_with', 'P(SURVIVE) WITH'], ['uplift', 'UPLIFT'],
  ['band_area', 'BAND AREA'], ['energy', 'ENERGY'], ['fleet', 'FLEET'],
  ['sensitivity', 'WHAT MOVES THE ANSWER'], ['calibration', 'CALIBRATION'], ['hindcast', 'HINDCAST'],
];

const CLASS_STYLE: { fill: string; pattern?: string; outline?: boolean }[] = [
  { fill: MINT }, { fill: '#1a4555' }, { fill: '#0d1517', pattern: 'dots' }, { fill: '#0a1214', pattern: 'hatch' }, { fill: '#11272c', outline: true },
];
const CLASS_LABEL = ['BAND', 'SURVIVES ANYWAY', 'HOPELESS', 'BLOCKED', 'LOW UPLIFT'];

interface State {
  layer: string;
  winter: number;
  uplift: number;
  excl: boolean;
  selected: number;
  marker: Marker | null;
  region: string;
  mode: 'map' | 'table';
  throughput: number;
  guideFor: string | null;
}

export class Instrument {
  root: HTMLElement;
  map!: AtlasMap;
  st: State;
  cards: Record<string, Card>;
  layers: UILayer[];
  private bandAreas = new Map<string, { total: number; avail: number; counts: number[] }>();
  private q = <T extends Element = HTMLElement>(s: string) => this.root.querySelector(s) as T;

  constructor(root: HTMLElement, public atlas: Atlas, land: GeoJSON.GeoJsonObject | null) {
    this.root = root;
    const s = atlas.summary;
    this.cards = s.cards ?? {};
    // A layer ships only if its data exists AND its four-line card exists.
    this.layers = UI_LAYERS.filter((L) => L.needs.every((n) => atlas.hasLayer(n)) && this.cards[L.id]);
    const missing = UI_LAYERS.filter((L) => !this.layers.includes(L)).map((L) => L.id);
    if (missing.length) console.warn('[atlas] layers hidden (missing data or card):', missing.join(', '));
    const ws = atlas.manifest.winters;
    const def = atlas.manifest.default_winter ?? ws[ws.length - 1]?.w;
    const sc = s.scale ?? {};
    this.st = {
      layer: this.layers.find((l) => l.id === 'h0')?.id ?? this.layers[0]?.id ?? '',
      winter: def,
      uplift: s.thresholds?.uplift ?? 0.2,
      excl: true,
      selected: -1,
      marker: null,
      region: 'pan',
      mode: 'map',
      throughput: sc.throughput_default ?? 0.5,
      guideFor: null,
    };
    this.build();
    this.map = new AtlasMap(this.q('.map'), atlas, land);
    this.map.setMarkers(MARKERS);
    this.map.markerLabel = (m) => this.markerLabel(m);
    this.map.onCell = (k) => this.selectCell(k, null);
    this.map.onMarker = (m) => {
      const k = this.map.nearestCell(m.lon, m.lat, 8);
      this.selectCell(k, m);
    };
    this.map.onMove = (ll) => {
      this.q('.readout').textContent = ll ? `${fmtLat(ll[1])} ${fmtLon(ll[0])}` : '';
    };
    this.wire();
  }

  // ---------- layout ----------
  private build() {
    const a = this.atlas;
    const fixture = a.manifest.fixture || a.summary.fixture;
    const nLayers = this.layers.length + (this.hasExcl() ? 1 : 0);
    const nDefined = UI_LAYERS.length + 1;
    this.root.innerHTML = `
    <header class="ih">
      <div class="ih-row">
        <div class="wordmark"><span class="wm">SURVIVAL GAP ATLAS</span><span class="wm-sub">ARCTIC SEA-ICE · EASE2 25 KM · ${fmtInt(a.n)} CELLS</span></div>
        <div class="ih-right">
          ${fixture
            ? '<span class="chip chip-amber" title="Development fixture: every value is invented">SYNTHETIC FIXTURE · NOT DATA</span>'
            : '<span class="chip chip-status"><i class="live"></i>MODEL · EXPLORATORY</span>'}
          <button class="btn btn-guide" type="button">WHAT THESE LAYERS MEAN</button>
        </div>
      </div>
      <div class="ih-row ih-row2">
        <div class="regions" role="group" aria-label="Region">
          ${REGIONS.map((r) => `<button type="button" class="rtab${r.id === 'pan' ? ' on' : ''}" data-region="${r.id}" aria-pressed="${r.id === 'pan'}">${r.label}</button>`).join('')}
        </div>
        <div class="chips">
          <span class="chip">LAYERS <b>${nLayers}/${nDefined}</b></span>
          <span class="chip">WINTER <b class="c-winter"></b></span>
          <span class="chip">DATE <b>${esc(a.manifest.built)}</b></span>
          <span class="chip c-delta" hidden></span>
        </div>
      </div>
    </header>
    <div class="ib">
      <aside class="col col-l" aria-label="Layers and winter">
        <section class="panel p-layers">
          <header class="ph"><h3>LAYERS</h3><span class="pchip">${nLayers} WITH GUIDES</span></header>
          <div class="pb layer-list" role="radiogroup" aria-label="Map layer"></div>
          <div class="pb band-ctl" hidden>
            <label class="slider-row"><span class="lbl">UPLIFT THRESHOLD</span><b class="v-thr"></b>
              <input type="range" class="s-thr" min="0.05" max="0.6" step="0.01" aria-label="Uplift threshold"></label>
            <div class="class-counts"></div>
          </div>
        </section>
        <section class="panel p-winter">
          <header class="ph"><h3>WINTER</h3><span class="pchip">SEP JUDGED W+1</span></header>
          <div class="pb winter-grid"></div>
          <div class="pb winter-spark" hidden></div>
        </section>
        <section class="panel p-sens" hidden>
          <header class="ph"><h3>WHAT MOVES THE ANSWER</h3><button class="pchip qbtn" data-guide="sensitivity" type="button" aria-label="Signal guide: what moves the answer">?</button></header>
          <div class="pb sens"></div>
        </section>
      </aside>
      <div class="mapwrap">
        <div class="map"></div>
        <div class="ctrls" role="toolbar" aria-label="Map controls">
          <button type="button" class="sq z-in" aria-label="Zoom in">+</button>
          <button type="button" class="sq z-out" aria-label="Zoom out">−</button>
          <button type="button" class="sq mode" aria-label="Switch to table view" aria-pressed="false">TBL</button>
        </div>
        <div class="hint">SCROLL TO ZOOM · DRAG TO PAN</div>
        <div class="map-notice" hidden></div>
        <div class="caveat"><b>NOT IN OPEN DATA</b> Indigenous use areas and ringed seal habitat are not in open data: community consent required.</div>
        <div class="readout" aria-hidden="true"></div>
        <div class="legend" aria-label="Legend"></div>
        <div class="table-view" hidden></div>
      </div>
      <aside class="col col-r" aria-label="Scale and cell details">
        <div class="rtabs" role="tablist" aria-label="Side panel">
          <button type="button" role="tab" class="rt on" data-tab="cell" aria-selected="true">SIGNAL GUIDE</button>
          <button type="button" role="tab" class="rt" data-tab="scale" aria-selected="false">SCALE</button>
        </div>
        <section class="panel p-scale tab-off">
          <header class="ph"><h3>SCALE</h3><span class="pchip">VS REAL ICE PLAN</span></header>
          <div class="pb scale"></div>
        </section>
        <section class="panel p-cell" aria-live="polite">
          <div class="cell"></div>
        </section>
      </aside>
    </div>
    <div class="guide-modal" hidden role="dialog" aria-modal="true" aria-label="Signal guide">
      <div class="gm-head">
        <div><h3>SIGNAL GUIDE</h3><p class="gm-sub">Interpretation guides, not conclusions.</p></div>
        <button type="button" class="sq gm-close" aria-label="Close signal guide">×</button>
      </div>
      <div class="gm-grid"></div>
    </div>`;
  }

  private hasExcl() {
    return !!this.atlas.stat['excl'] && !!this.cards['excl'];
  }

  private wire() {
    const r = this.root;
    r.querySelectorAll<HTMLButtonElement>('.rtab').forEach((b) =>
      b.addEventListener('click', () => {
        this.st.region = b.dataset.region!;
        r.querySelectorAll('.rtab').forEach((x) => { x.classList.toggle('on', x === b); x.setAttribute('aria-pressed', String(x === b)); });
        this.map.goTo(REGIONS.find((x) => x.id === b.dataset.region)!);
        if (this.st.mode === 'table') this.renderTable();
      }),
    );
    this.q('.z-in').addEventListener('click', () => this.map.zoomBy(1.6));
    this.q('.z-out').addEventListener('click', () => this.map.zoomBy(1 / 1.6));
    this.q('.mode').addEventListener('click', () => this.setMode(this.st.mode === 'map' ? 'table' : 'map'));
    this.q('.btn-guide').addEventListener('click', () => this.openGuide());
    r.querySelectorAll<HTMLButtonElement>('.rt').forEach((b) => b.addEventListener('click', () => this.setTab(b.dataset.tab as 'cell' | 'scale')));
    this.q('.gm-close').addEventListener('click', () => this.closeGuide());
    this.root.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !this.q('.guide-modal').hidden) this.closeGuide();
    });
    const s = this.q<HTMLInputElement>('.s-thr');
    s.value = String(this.st.uplift);
    s.addEventListener('input', () => {
      this.st.uplift = +s.value;
      this.render();
    });
    this.root.addEventListener('click', (e) => {
      const g = (e.target as Element).closest<HTMLElement>('[data-guide]');
      if (g && !g.closest('.guide-modal')) {
        e.preventDefault();
        this.openGuide(g.dataset.guide!);
      }
    });
    this.buildLayerList();
    this.buildWinters();
    this.buildSensitivity();
  }

  private buildLayerList() {
    const list = this.q('.layer-list');
    const rows = this.layers
      .map((L) => `<button type="button" role="radio" class="lrow" data-layer="${L.id}"><i class="dot"></i><span>${L.label}</span><em>${L.chip}</em></button>`)
      .join('');
    const ex = this.hasExcl()
      ? `<button type="button" role="checkbox" class="lrow lrow-excl" data-excl="1"><i class="box">${swatchSVG({ fill: '#03060a', pattern: 'amber' }, 10)}</i><span>${EXCL_LAYER.label}</span><em>OVERLAY</em></button>`
      : '';
    list.innerHTML = rows + ex;
    list.querySelectorAll<HTMLButtonElement>('[data-layer]').forEach((b) => b.addEventListener('click', () => this.setLayer(b.dataset.layer!)));
    list.querySelector<HTMLButtonElement>('[data-excl]')?.addEventListener('click', () => {
      this.st.excl = !this.st.excl;
      this.render();
    });
  }

  private buildWinters() {
    const g = this.q('.winter-grid');
    g.innerHTML = this.atlas.manifest.winters
      .map((w) => `<button type="button" class="wbtn${w.partial ? ' partial' : ''}" data-w="${w.w}" aria-pressed="false">${esc(w.label)}${w.partial ? '<small>CURRENT SEASON, PARTIAL DATA</small>' : ''}</button>`)
      .join('');
    g.querySelectorAll<HTMLButtonElement>('.wbtn').forEach((b) => b.addEventListener('click', () => this.setWinter(+b.dataset.w!)));
  }

  private buildSensitivity() {
    const s = this.atlas.summary.sensitivity;
    if (!s?.rows?.length || !this.cards['sensitivity']) return;
    this.q('.p-sens').hidden = false;
    const rows = [...s.rows].sort((a, b) => mag(b) - mag(a));
    const max = Math.max(...rows.map(mag), 1e-9);
    const unit = s.unit ?? '';
    const sgn = (v: number) => `${v < 0 ? '−' : '+'}${Math.abs(v) >= 100 ? fmtInt(Math.abs(v)) : fmtNum(Math.abs(v), 2)}`;
    const meta = [(s.target ?? 'Band area').toUpperCase(), s.winter ? `WINTER ${s.winter}/${String((s.winter + 1) % 100).padStart(2, '0')}` : '', s.method ? s.method.toUpperCase() : '']
      .filter(Boolean).map(esc).join(' · ');
    this.q('.sens').innerHTML =
      `<div class="sens-meta">${meta}${s.base != null ? `<br>BASE ${fmtInt(s.base)} ${esc(unit.toUpperCase())}` : ''}</div>` +
      rows
        .map((r, i) => {
          if (r.low != null && r.high != null) {
            const lo = Math.min(r.low, r.high, 0);
            const hi = Math.max(r.low, r.high, 0);
            const left = 50 + (lo / max) * 50;
            const w = ((hi - lo) / max) * 50;
            return `<div class="sbar"><span class="sl"><b>${i + 1}</b>${esc(r.label.toUpperCase())}</span>
              <span class="track tornado"><i class="rng" style="left:${left}%;width:${Math.max(w, 0.5)}%"></i><i class="axis"></i></span>
              <span class="sv">LOW ${sgn(r.low)} · HIGH ${sgn(r.high)}${unit ? ` ${esc(unit)}` : ''}</span></div>`;
          }
          const v = r.value ?? 0;
          return `<div class="sbar"><span class="sl"><b>${i + 1}</b>${esc(r.label.toUpperCase())}</span>
            <span class="track"><i class="rng" style="width:${(Math.abs(v) / max) * 100}%;left:0"></i></span>
            <span class="sv">${Math.abs(v) >= 100 ? fmtInt(v) : fmtNum(v, 2)}${unit ? ` ${esc(unit)}` : ''}</span></div>`;
        })
        .join('');
    function mag(r: { value?: number; low?: number; high?: number }) {
      return r.low != null && r.high != null ? Math.max(Math.abs(r.low), Math.abs(r.high)) : Math.abs(r.value ?? 0);
    }
  }

  // ---------- state changes ----------
  async start() {
    await this.atlas.loadWinter(this.st.winter);
    await this.render();
    // preload remaining winters for the band comparison strip
    Promise.all(this.atlas.manifest.winters.map((w) => this.atlas.loadWinter(w.w).catch(() => null))).then(() => {
      this.renderSpark();
      this.renderChips();
    });
  }

  setLayer(id: string) {
    this.st.layer = id;
    this.render();
  }

  async setWinter(w: number) {
    this.st.winter = w;
    await this.atlas.loadWinter(w).catch(() => null);
    this.render();
  }

  private setMode(m: 'map' | 'table') {
    this.st.mode = m;
    const b = this.q<HTMLButtonElement>('.mode');
    b.textContent = m === 'map' ? 'TBL' : 'MAP';
    b.setAttribute('aria-pressed', String(m === 'table'));
    b.setAttribute('aria-label', m === 'map' ? 'Switch to table view' : 'Switch to map view');
    this.q('.table-view').hidden = m === 'map';
    if (m === 'table') this.renderTable();
  }

  private winterHas(L: UILayer, w: number): boolean {
    return L.needs.every((n) => !!this.atlas.raw(n, w));
  }

  private cls(w: number): Int8Array {
    return classify(this.atlas, w, thresholds(this.atlas, this.st.uplift));
  }

  bandArea(w: number): { total: number; avail: number; counts: number[] } | null {
    if (!this.atlas.raw('p_without', w) || !this.atlas.raw('p_with', w)) return null;
    const key = `${w}:${this.st.uplift}`;
    const hit = this.bandAreas.get(key);
    if (hit) return hit;
    const c = this.cls(w);
    const ex = this.atlas.stat['excl'];
    const counts = [0, 0, 0, 0, 0];
    let avail = 0;
    for (let k = 0; k < c.length; k++) {
      if (c[k] < 0) continue;
      counts[c[k]]++;
      if (c[k] === 0 && !(ex && ex[k] !== 255 && ex[k] > 0)) avail++;
    }
    const res = { total: counts[0] * this.atlas.cellArea, avail: avail * this.atlas.cellArea, counts };
    this.bandAreas.set(key, res);
    return res;
  }

  async render() {
    const st = this.st;
    const L = this.layers.find((l) => l.id === st.layer);
    const notice = this.q('.map-notice');
    notice.hidden = true;
    let groups: PaintGroup[] = [];
    let legend: LegendItem[] = [];
    if (!L) {
      notice.hidden = false;
      notice.textContent = 'No layers with data and a signal guide. Run make export.';
    } else {
      if (!this.winterHas(L, st.winter) && !L.isStatic) {
        // fall back to the latest winter that carries this layer
        const ws = [...this.atlas.manifest.winters].reverse();
        let found: number | null = null;
        for (const w of ws) {
          await this.atlas.loadWinter(w.w).catch(() => null);
          if (this.winterHas(L, w.w)) { found = w.w; break; }
        }
        if (found != null) {
          const from = this.atlas.manifest.winters.find((x) => x.w === st.winter)?.label;
          st.winter = found;
          notice.hidden = false;
          notice.textContent = `${L.label} is not computed for ${from}. Showing ${this.atlas.manifest.winters.find((x) => x.w === found)?.label}.`;
          clearTimeout((this as any)._nt);
          (this as any)._nt = setTimeout(() => (notice.hidden = true), 4000);
        }
      }
      if (this.winterHas(L, st.winter) || L.isStatic) {
        const p = L.id === 'band' ? bandPaint(this.cls(st.winter)) : rampPaint(this.atlas, L, st.winter);
        groups = p.groups;
        legend = p.legend;
      } else {
        notice.hidden = false;
        notice.textContent = `No ${L.label} data for this winter. Run make export.`;
      }
    }
    const ex = st.excl && this.hasExcl() ? exclPaint(this.atlas) : null;
    if (ex) {
      groups = [...groups, ex];
      legend = [...legend, { label: 'EXCLUDED', fill: '#03060a', pattern: 'amber' }];
    }
    this.map.setPaint(`${st.layer}:${st.winter}:${st.layer === 'band' ? st.uplift : ''}`, groups);
    this.renderLegend(legend);
    this.renderLayerPanel();
    this.renderWinterPanel();
    this.renderChips();
    this.renderScale();
    this.renderCell();
    this.map.refreshMarkerLabels();
    if (st.mode === 'table') this.renderTable();
  }

  private renderLegend(items: LegendItem[]) {
    this.q('.legend').innerHTML = items.map((i) => `<span class="li">${swatchSVG(i, 10)}${esc(i.label)}</span>`).join('');
  }

  private renderLayerPanel() {
    const st = this.st;
    this.root.querySelectorAll<HTMLButtonElement>('.lrow[data-layer]').forEach((b) => {
      const on = b.dataset.layer === st.layer;
      b.classList.toggle('on', on);
      b.setAttribute('aria-checked', String(on));
      const L = this.layers.find((l) => l.id === b.dataset.layer)!;
      const has = L.isStatic || this.atlas.manifest.winters.some((w) => this.atlas.winters.get(w.w) && this.winterHas(L, w.w));
      b.classList.toggle('dim', !has && this.atlas.winters.size === this.atlas.manifest.winters.length);
    });
    const ex = this.root.querySelector<HTMLButtonElement>('.lrow[data-excl]');
    if (ex) {
      ex.classList.toggle('on', st.excl);
      ex.setAttribute('aria-checked', String(st.excl));
    }
    const bc = this.q('.band-ctl');
    bc.hidden = st.layer !== 'band';
    if (st.layer === 'band') {
      this.q('.v-thr').textContent = fmtNum(st.uplift, 2);
      const t = thresholds(this.atlas, st.uplift);
      const ba = this.bandArea(st.winter);
      const ca = this.atlas.cellArea;
      const defs = [
        `U ≥ ${fmtNum(t.uplift, 2)}`, `P WITHOUT ≥ ${fmtNum(t.survives, 1)}`, `P WITH ≤ ${fmtNum(t.hopeless, 1)}`,
        `START < ${fmtNum(this.atlas.summary.thresholds?.guard_m ?? 0.6, 1)} M`, `U < ${fmtNum(t.uplift, 2)}`,
      ];
      this.q('.class-counts').innerHTML = ba
        ? BAND_CLASSES.map((_, c) => `<div class="cc"><span>${swatchSVG(CLASS_STYLE[c], 10)}${CLASS_LABEL[c]}<small>${defs[c]}</small></span><b>${fmtInt(ba.counts[c] * ca)}<small> KM²</small></b></div>`).join('')
        : '';
    }
  }

  private renderWinterPanel() {
    this.root.querySelectorAll<HTMLButtonElement>('.wbtn').forEach((b) => {
      const on = +b.dataset.w! === this.st.winter;
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', String(on));
    });
    this.renderSpark();
  }

  private renderSpark() {
    const el = this.q('.winter-spark');
    const ws = this.atlas.manifest.winters.filter((w) => this.atlas.winters.has(w.w));
    const vals = ws.map((w) => ({ w, a: this.bandArea(w.w) })).filter((x) => x.a);
    if (vals.length < 2 || !this.layers.some((l) => l.id === 'band')) { el.hidden = true; return; }
    el.hidden = false;
    const max = Math.max(...vals.map((v) => v.a!.total), 1);
    el.innerHTML = `<div class="spark-title">BAND AREA BY WINTER · U ≥ ${fmtNum(this.st.uplift, 2)}</div><div class="spark">${vals
      .map((v) => `<button type="button" class="sp${v.w.w === this.st.winter ? ' on' : ''}" data-w="${v.w.w}" title="${esc(v.w.label)}: ${fmtInt(v.a!.total)} km²" aria-label="Winter ${esc(v.w.label)}, band ${fmtInt(v.a!.total)} square kilometres"><i style="height:${Math.max(2, (v.a!.total / max) * 100)}%"></i><span>${String(v.w.w).slice(2)}</span></button>`)
      .join('')}</div>`;
    el.querySelectorAll<HTMLButtonElement>('.sp').forEach((b) => b.addEventListener('click', () => this.setWinter(+b.dataset.w!)));
  }

  private renderChips() {
    const w = this.atlas.manifest.winters.find((x) => x.w === this.st.winter);
    this.q('.c-winter').textContent = w ? `${w.label}${w.partial ? ' PARTIAL' : ''}` : '';
    const d = this.q('.c-delta');
    const ws = this.atlas.manifest.winters;
    const i = ws.findIndex((x) => x.w === this.st.winter);
    const cur = this.bandArea(this.st.winter);
    const prev = i > 0 && this.atlas.winters.has(ws[i - 1].w) ? this.bandArea(ws[i - 1].w) : null;
    if (cur && prev) {
      const dv = cur.total - prev.total;
      d.hidden = false;
      d.innerHTML = `DELTA <b>${dv > 0 ? '▲ +' : dv < 0 ? '▼ −' : '◆ '}${fmtInt(Math.abs(dv))} KM²</b> <span class="dim">VS ${esc(ws[i - 1].label)}</span>`;
    } else d.hidden = true;
  }

  private renderScale() {
    const el = this.q('.scale');
    const sc = this.atlas.summary.scale ?? {};
    const ba = this.bandArea(this.st.winter);
    const w = this.atlas.manifest.winters.find((x) => x.w === this.st.winter);
    if (!ba || !this.cards['band_area']) {
      el.innerHTML = `<p class="empty">No band for ${esc(w?.label ?? 'this winter')}${w?.partial ? ' (partial season)' : ''}. Pick a complete winter${this.cards['band_area'] ? '' : ', or run make export'}.</p>`;
      return;
    }
    const target = sc.target_km2 ?? 1_000_000;
    const share = sc.share_of_ice_area ?? 0.05;
    const iceArea = sc.arctic_ice_area_km2 ?? w?.ice_km2 ?? null;
    const iceLabel = sc.arctic_ice_area_km2 ? `${fmtInt(sc.arctic_ice_area_km2)} KM²${sc.arctic_ice_area_source ? ` · ${esc(sc.arctic_ice_area_source)}` : ''}` : `${fmtInt(iceArea ?? 0)} KM² MODELLED ICE AREA, ${esc(w?.label ?? '')}`;
    const five = iceArea ? iceArea * share : null;
    const mwh = sc.mwh_per_km2 ?? 8;
    const days = sc.ice_safe_days ?? 90;
    const area = ba.avail;
    const max = Math.max(area, target, five ?? 0, ba.total) * 1.08;
    const pos = (v: number) => `${(v / max) * 100}%`;
    const tmin = sc.throughput_min ?? 0.05;
    const tmax = sc.throughput_max ?? 5;
    const tp = this.st.throughput;
    const sl = (Math.log(tp) - Math.log(tmin)) / (Math.log(tmax) - Math.log(tmin));
    const fleet = (a: number) => Math.ceil(a / (tp * days));
    const g = (key: string) => (this.cards[key] ? `<button type="button" class="qbtn" data-guide="${key}" aria-label="Signal guide">?</button>` : '');
    el.innerHTML = `
      <div class="big"><span class="lbl">BAND AREA, OUTSIDE EXCLUSIONS ${g('band_area')}</span><b class="mint">${fmtInt(area)}<small> KM²</small></b>
        <span class="meta">${esc(w?.label ?? '')} · U ≥ ${fmtNum(this.st.uplift, 2)} · ${fmtInt(ba.total)} KM² INCL. BUFFERS · ${fmtInt(this.atlas.cellArea)} KM² CELLS</span></div>
      <div class="scalebar" role="img" aria-label="Band area ${fmtInt(area)} square kilometres against Real Ice target ${fmtInt(target)}">
        <i class="bar" style="width:${pos(area)}"></i>
        <i class="tick t-target" style="left:${pos(target)}"><span>${shortKm(target)}</span></i>
        ${five ? `<i class="tick t-five" style="left:${pos(five)}"><span>${Math.round(share * 100)}%</span></i>` : ''}
      </div>
      <div class="scale-legend"><span>${swatchSVG({ fill: MINT }, 8)}BAND</span><span><i class="tk"></i>${shortKm(target)} = REAL ICE ${fmtInt(target)} KM²/YR${sc.target_source ? ` · ${esc(sc.target_source)}` : ''}</span>${five ? `<span><i class="tk tk2"></i>${Math.round(share * 100)}% = ${Math.round(share * 100)}% OF ${iceLabel}</span>` : ''}</div>
      ${this.cards['energy'] ? `<div class="row"><span class="lbl">ENERGY @ ${fmtNum(mwh, 0)} MWH/KM² ${g('energy')}<small>${esc(sc.energy_source ?? 'Ocean Visions roadmap')}</small></span><b>${fmtEnergy(area * mwh)}</b></div>
      <div class="row"><span class="lbl">ENERGY FOR TARGET<small>${fmtInt(target)} KM² × ${fmtNum(mwh, 0)} MWH</small></span><b>${fmtEnergy(target * mwh)}</b></div>` : ''}
      ${this.cards['fleet'] ? `<div class="assume">
        <label class="slider-row"><span class="lbl">THROUGHPUT <em class="tag">ASSUMPTION</em></span><b>${fmtNum(tp, tp < 1 ? 2 : 1)}<small> KM²/DRONE/DAY</small></b>
          <input type="range" class="s-tp" min="0" max="1" step="0.001" value="${sl}" aria-label="Drone throughput assumption, square kilometres per drone per day"></label>
        <p class="note">Drone throughput is not public. ${days} ice-safe days (${esc(sc.ice_safe_note ?? 'Jan–Mar')}).</p>
        <div class="row"><span class="lbl">FLEET FOR BAND <em class="tag">ASSUMPTION</em> ${g('fleet')}</span><b>${fmtInt(fleet(area))}<small> DRONES</small></b></div>
        <div class="row"><span class="lbl">FLEET FOR TARGET <em class="tag">ASSUMPTION</em></span><b>${fmtInt(fleet(target))}<small> DRONES</small></b></div>
      </div>` : ''}`;
    const s = el.querySelector<HTMLInputElement>('.s-tp');
    s?.addEventListener('input', () => {
      const v = Math.exp(Math.log(tmin) + +s.value * (Math.log(tmax) - Math.log(tmin)));
      this.st.throughput = v < 1 ? Math.round(v * 100) / 100 : Math.round(v * 10) / 10;
      const focus = document.activeElement === s;
      this.renderScale();
      if (focus) el.querySelector<HTMLInputElement>('.s-tp')?.focus();
    });
  }

  private markerLabel(m: Marker): string {
    const name = m.name.toUpperCase();
    if (m.kind === 'site') return name;
    const k = this.map.nearestCell(m.lon, m.lat, 3);
    if (k < 0) return name;
    const L = this.layers.find((l) => l.id === this.st.layer);
    if (!L) return name;
    if (L.id === 'band') {
      const c = this.cls(this.st.winter)[k];
      return c >= 0 ? `${name} · ${CLASS_LABEL[c]}` : name;
    }
    const v = this.atlas.value(L.field!, this.st.winter, k);
    if (v == null) return name;
    const u = this.atlas.manifest.layers[L.field!].unit;
    return `${name} · ${L.fmt!(v)}${u && u !== '' ? ` ${u.toUpperCase()}` : ''}`;
  }

  setTab(t: 'cell' | 'scale') {
    this.root.querySelectorAll<HTMLButtonElement>('.rt').forEach((b) => {
      const on = b.dataset.tab === t;
      b.classList.toggle('on', on);
      b.setAttribute('aria-selected', String(on));
    });
    this.q('.p-scale').classList.toggle('tab-off', t !== 'scale');
    this.q('.p-cell').classList.toggle('tab-off', t !== 'cell');
  }

  // ---------- cell card ----------
  selectCell(k: number, marker: Marker | null) {
    this.st.selected = k;
    this.q('.rt[data-tab="cell"]').textContent = k >= 0 ? 'CELL' : 'SIGNAL GUIDE';
    this.setTab('cell');
    this.st.marker = marker;
    this.map.select(k);
    this.renderCell();
    if (window.matchMedia('(max-width: 899px)').matches) this.q('.p-cell').scrollIntoView({ block: 'nearest', behavior: reduced() ? 'auto' : 'smooth' });
  }

  private renderCell() {
    const el = this.q('.cell');
    const st = this.st;
    const L = this.layers.find((l) => l.id === st.layer);
    const card = L ? this.cards[L.id] : null;
    if (st.selected < 0) {
      el.innerHTML = `<header class="ph"><h3>${esc(L?.label ?? 'SIGNAL GUIDE')}</h3><span class="pchip">${esc(L?.chip ?? '')}</span></header>
        <div class="pb"><p class="sub">Interpretation guides, not conclusions.</p>${card ? guideHTML(card) : ''}
        <p class="tip">Click any cell or marker for its values, sources and dates.</p></div>`;
      if (st.marker) this.st.marker = null;
      return;
    }
    const a = this.atlas;
    const k = st.selected;
    const w = st.winter;
    const wl = a.manifest.winters.find((x) => x.w === w);
    const [lon, lat] = this.map.cellCenterLonLat(k);
    const c = a.raw('p_without', w) ? this.cls(w)[k] : -1;
    const cardOf = (r: CellRow) => this.cards[r.card] ?? (r.alt ? this.cards[r.alt] : undefined);
    const rows = CELL_ROWS.filter((r) => a.hasLayer(r.name) && cardOf(r))
      .map((r) => {
        const v = a.value(r.name, w, k);
        if (v == null) return '';
        const m = a.manifest.layers[r.name];
        const unc = m.unc_layer ? a.value(m.unc_layer, w, k) : null;
        const isStatic = a.manifest.static_layers.includes(r.name);
        const date = fillDate(m.date, w) || (isStatic ? 'all winters' : `winter ${wl?.label ?? ''}`);
        const meta = [
          m.title,
          unc != null ? `± ${fmtNum(unc, r.digits)} ${m.unit} (${a.manifest.layers[m.unc_layer!]?.title.toLowerCase() ?? 'uncertainty'})` : m.unc ?? '',
          m.source ?? '',
          date,
        ].filter(Boolean).map(esc).join(' · ');
        const open = (L?.field === r.name) || (L?.id === 'band' && r.name === 'uplift');
        return `<details class="crow"${open ? ' open' : ''}><summary><span class="lbl">${r.label}</span><b>${fmtNum(v, r.digits)}${m.unit ? `<small> ${esc(m.unit.toUpperCase())}</small>` : ''}</b></summary>
          <div class="cmeta">${meta}</div>${guideHTML(cardOf(r)!, 'compact')}</details>`;
      })
      .join('');
    // exclusions
    let exRow = '';
    const ex = a.stat['excl'];
    if (ex && this.cards['excl'] && ex[k] !== 255) {
      const flags = a.manifest.layers['excl']?.flags ?? {};
      const names = Object.entries(flags).filter(([b]) => ex[k] & +b).map(([, n]) => n);
      const m = a.manifest.layers['excl'];
      exRow = `<details class="crow"><summary><span class="lbl">EXCLUSIONS</span><b class="${ex[k] ? 'amber' : ''}">${ex[k] ? esc(names.join(', ').toUpperCase() || 'EXCLUDED') : 'NONE'}</b></summary>
        <div class="cmeta">${[m?.source, fillDate(m?.date, w)].filter(Boolean).map(esc).join(' · ')}</div>${guideHTML(this.cards['excl'], 'compact')}</details>`;
    }
    // band layer guide
    const bandRow = c >= 0 && this.cards['band']
      ? `<details class="crow"${L?.id === 'band' ? ' open' : ''}><summary><span class="lbl">SURVIVAL GAP CLASS</span><b class="${c === 0 ? 'mint' : ''}">${CLASS_LABEL[c]}</b></summary><div class="cmeta">U ≥ ${fmtNum(st.uplift, 2)} threshold · ${esc(wl?.label ?? '')}</div>${guideHTML(this.cards['band'], 'compact')}</details>`
      : '';
    const mk = st.marker;
    const cal = a.summary.calibration;
    const calMax = cal ? Math.max(cal.modelled_cm, cal.paper_cm, cal.uncalibrated_cm ?? 0, 1e-9) : 1;
    const bar = (lbl: string, v: number, cls: string) => `<div><span>${lbl}</span><i style="width:${Math.max(0, (v / calMax) * 100)}%" class="${cls}"></i><b>${v >= 0 ? '+' : '−'}${fmtNum(Math.abs(v), 1)} CM</b></div>`;
    const calBars = cal
      ? (cal.uncalibrated_cm != null ? bar('UNCALIB.', cal.uncalibrated_cm, 'u') : '') + bar(cal.uncalibrated_cm != null ? 'CALIBRATED' : 'MODELLED', cal.modelled_cm, 'm') + bar('PAPER', cal.paper_cm, 'p')
      : '';
    const calWinter = cal?.winter_label ?? (cal?.winter ? `${cal.winter}/${String((cal.winter + 1) % 100).padStart(2, '0')}` : '');
    const calBlock = mk?.id === 'cambridge-bay' && cal && this.cards['calibration']
      ? `<div class="cal">
          <div class="cal-h"><span class="lbl">CALIBRATION · ${esc((cal.site ?? 'Cambridge Bay').toUpperCase())} ${esc(calWinter)}</span>${'<button type="button" class="qbtn" data-guide="calibration" aria-label="Signal guide: calibration">?</button>'}</div>
          <div class="cal-bars">${calBars}</div>
          <div class="cmeta">Flooded minus control, mid-May. ${cal.modelled_range_cm ? `Model range ${fmtNum(cal.modelled_range_cm[0], 0)}–${fmtNum(cal.modelled_range_cm[1], 0)} cm. ` : ''}Gap ${cal.modelled_cm - cal.paper_cm >= 0 ? '+' : '−'}${fmtNum(Math.abs(cal.modelled_cm - cal.paper_cm), 1)} cm.${cal.alpha != null ? ` α = ${fmtNum(cal.alpha, 2)}.` : ''} ${esc(cal.source ?? '')}${cal.date ? ` · ${esc(cal.date)}` : ''}${cal.note ? ` · ${esc(cal.note)}` : ''}</div>
        </div>`
      : '';
    el.innerHTML = `<header class="ph"><h3>${mk ? esc(mk.name.toUpperCase()) : 'CELL'}</h3>
        <span class="pchip">${fmtLat(lat)} ${fmtLon(lon)}</span>
        <button type="button" class="sq sq-s c-close" aria-label="Close cell card">×</button></header>
      <div class="pb">
        ${mk?.note ? `<p class="mnote">${esc(mk.note)}</p>` : ''}
        <div class="cell-sub">CELL ${a.ci[k]},${a.cj[k]} · 25 × 25 KM · ${esc(wl?.label ?? '')}${wl?.partial ? ' · PARTIAL' : ''}</div>
        ${calBlock}${bandRow}${rows}${exRow}
        ${!rows && !bandRow ? `<p class="empty">No values for this cell in ${esc(wl?.label ?? 'this winter')}.</p>` : ''}
      </div>`;
    el.querySelector('.c-close')?.addEventListener('click', () => this.selectCell(-1, null));
  }

  // ---------- table fallback ----------
  private renderTable() {
    const el = this.q('.table-view');
    const a = this.atlas;
    const w = this.st.winter;
    const hasBand = !!a.raw('p_without', w);
    const cls = hasBand ? this.cls(w) : null;
    const want = (el.querySelector<HTMLSelectElement>('.t-filter')?.value ?? (hasBand ? '0' : 'all'));
    const keys = ['h0', 'hs', 'R', 'p_without', 'p_with', 'uplift'].filter((n) => a.raw(n, w));
    const idx: number[] = [];
    for (let k = 0; k < a.n; k++) {
      if (want !== 'all' && cls && cls[k] !== +want) continue;
      idx.push(k);
    }
    const sortKey = keys.includes('uplift') ? 'uplift' : keys[0];
    if (sortKey) idx.sort((x, y) => (a.value(sortKey, w, y) ?? -1) - (a.value(sortKey, w, x) ?? -1));
    const LIMIT = 250;
    const shown = idx.slice(0, LIMIT);
    const wl = a.manifest.winters.find((x) => x.w === w)?.label ?? '';
    el.innerHTML = `<div class="tv-head"><span class="lbl">CELLS · ${esc(wl)} · ${fmtInt(idx.length)} ROWS${idx.length > LIMIT ? ` · FIRST ${LIMIT} BY ${sortKey?.toUpperCase()}` : ''}</span>
      <label class="lbl">CLASS <select class="t-filter">${hasBand ? CLASS_LABEL.map((l, i) => `<option value="${i}"${want === String(i) ? ' selected' : ''}>${l}</option>`).join('') : ''}<option value="all"${want === 'all' ? ' selected' : ''}>ALL CELLS</option></select></label></div>
      <div class="tv-scroll"><table><thead><tr><th>LAT</th><th>LON</th>${cls ? '<th>CLASS</th>' : ''}${keys.map((n) => `<th>${esc(n.toUpperCase())}</th>`).join('')}</tr></thead><tbody>
      ${shown.map((k) => {
        const [lon, lat] = this.map.cellCenterLonLat(k);
        return `<tr tabindex="0" data-k="${k}"><td>${fmtLat(lat)}</td><td>${fmtLon(lon)}</td>${cls ? `<td>${cls[k] >= 0 ? CLASS_LABEL[cls[k]] : ''}</td>` : ''}${keys.map((n) => { const v = a.value(n, w, k); return `<td>${v == null ? '' : fmtNum(v, 2)}</td>`; }).join('')}</tr>`;
      }).join('')}
      </tbody></table></div>`;
    el.querySelector('.t-filter')?.addEventListener('change', () => this.renderTable());
    el.querySelectorAll<HTMLTableRowElement>('tr[data-k]').forEach((tr) => {
      const go = () => this.selectCell(+tr.dataset.k!, null);
      tr.addEventListener('click', go);
      tr.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
    });
  }

  // ---------- signal guide modal ----------
  openGuide(focus?: string) {
    const m = this.q('.guide-modal');
    const items: [string, string][] = [
      ...this.layers.map((L) => [L.id, L.label] as [string, string]),
      ...(this.hasExcl() ? [['excl', 'EXCLUSIONS'] as [string, string]] : []),
      ...METRIC_CARDS.filter(([k]) => this.cards[k]),
    ];
    this.q('.gm-grid').innerHTML = items
      .map(([k, label]) => `<article class="gcard${k === focus ? ' focus' : ''}" id="g-${k}"><h4>${esc(label)}<span>${this.layers.some((l) => l.id === k) || k === 'excl' ? 'LAYER' : 'METRIC'}</span></h4>${guideHTML(this.cards[k])}</article>`)
      .join('');
    m.hidden = false;
    this.q<HTMLButtonElement>('.gm-close').focus();
    if (focus) this.q(`#g-${focus}`)?.scrollIntoView({ block: 'center' });
  }

  closeGuide() {
    this.q('.guide-modal').hidden = true;
    this.q<HTMLButtonElement>('.btn-guide').focus();
  }
}

function shortKm(v: number): string {
  return v >= 1e6 ? `${fmtNum(v / 1e6, v % 1e6 ? 1 : 0)}M` : `${fmtNum(v / 1e3, 0)}K`;
}
