import { geoStereographic, geoPath, geoGraticule, geoCircle, geoArea, type GeoProjection } from 'd3-geo';
import { select, type Selection } from 'd3-selection';
import { zoom, zoomIdentity, type ZoomBehavior, type ZoomTransform } from 'd3-zoom';
import 'd3-transition';
import type { Atlas } from './data';
import { inverse, cornerXY, lonlatToIJ } from './ease2';
import type { PaintGroup, PatternName } from './layers';

export interface Marker {
  id: string;
  name: string;
  lon: number;
  lat: number;
  kind: 'hero' | 'settlement' | 'site';
  note?: string;
  minZoom?: number;
  labelZoom?: number; // hide the text label below this zoom (declutter)
}

export interface Region { id: string; label: string; center?: [number, number]; span?: number }

const BASE_RADIUS = 31; // degrees from the pole that fit the frame at zoom 1
const CLIP = 50;
const NS = 'http://www.w3.org/2000/svg';

export class AtlasMap {
  readonly el: HTMLElement;
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private svg: Selection<SVGSVGElement, unknown, null, undefined>;
  private gWorld: SVGGElement;
  private gMarkers: SVGGElement;
  private landPath: SVGPathElement;
  private coastPath: SVGPathElement;
  private gratPath: SVGPathElement;
  private rimPath: SVGPathElement;
  private proj: GeoProjection;
  private zoomer: ZoomBehavior<SVGSVGElement, unknown>;
  t: ZoomTransform = zoomIdentity;
  private w = 0;
  private h = 0;
  private dpr = 1;
  private cornerLL: Float32Array; // lon/lat of the (crop+1)^2 corner lattice, NaN where unused
  private cx!: Float32Array;
  private cy!: Float32Array;
  private paths = new Map<string, Path2D>();
  private patterns = new Map<string, CanvasPattern>();
  private groups: PaintGroup[] = [];
  private paintKey = '';
  private selected = -1;
  private raf = 0;
  private markers: Marker[] = [];
  markerLabel: (m: Marker) => string = (m) => m.name.toUpperCase();
  onCell: (k: number, lonlat: [number, number]) => void = () => {};
  onMarker: (m: Marker) => void = () => {};
  onMove: (lonlat: [number, number] | null) => void = () => {};
  onZoom: (k: number) => void = () => {};

  constructor(el: HTMLElement, private atlas: Atlas, private land: GeoJSON.GeoJsonObject | null) {
    this.el = el;
    this.canvas = document.createElement('canvas');
    this.canvas.className = 'map-canvas';
    this.canvas.setAttribute('aria-hidden', 'true');
    el.appendChild(this.canvas);
    this.ctx = this.canvas.getContext('2d')!;
    const svgEl = document.createElementNS(NS, 'svg') as SVGSVGElement;
    svgEl.setAttribute('class', 'map-svg');
    svgEl.setAttribute('role', 'img');
    svgEl.setAttribute('aria-label', 'Polar stereographic map of Arctic sea-ice cells. Use the TABLE mode for a keyboard-readable list.');
    el.appendChild(svgEl);
    this.svg = select(svgEl);
    this.gWorld = document.createElementNS(NS, 'g') as SVGGElement;
    this.gMarkers = document.createElementNS(NS, 'g') as SVGGElement;
    const mk = (cls: string) => {
      const p = document.createElementNS(NS, 'path') as SVGPathElement;
      p.setAttribute('class', cls);
      p.setAttribute('vector-effect', 'non-scaling-stroke');
      this.gWorld.appendChild(p);
      return p;
    };
    this.rimPath = mk('rim');
    this.gratPath = mk('graticule');
    this.landPath = mk('land');
    this.coastPath = mk('coast');
    svgEl.appendChild(this.gWorld);
    svgEl.appendChild(this.gMarkers);

    if (land) this.land = fixWinding(land);
    this.proj = geoStereographic().rotate([45, -90]).clipAngle(CLIP).precision(0.2);

    // corner lattice, only for corners used by atlas cells
    const C = atlas.crop + 1;
    this.cornerLL = new Float32Array(C * C * 2).fill(NaN);
    for (let k = 0; k < atlas.n; k++) {
      const i = atlas.ci[k];
      const j = atlas.cj[k];
      for (const [di, dj] of [[0, 0], [0, 1], [1, 0], [1, 1]]) {
        const c = (i + di) * C + (j + dj);
        if (!Number.isNaN(this.cornerLL[2 * c])) continue;
        const [x, y] = cornerXY(i + di, j + dj);
        const [lon, lat] = inverse(x, y);
        this.cornerLL[2 * c] = lon;
        this.cornerLL[2 * c + 1] = lat;
      }
    }

    this.zoomer = zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 28])
      .on('zoom', (ev) => {
        this.t = ev.transform;
        this.gWorld.setAttribute('transform', this.t.toString());
        this.placeMarkers();
        this.schedule();
        this.onZoom(this.t.k);
      });
    this.svg.call(this.zoomer).on('dblclick.zoom', null);
    this.svg.on('click', (ev: MouseEvent) => {
      const tgt = ev.target as Element;
      const mid = tgt.closest('[data-marker]')?.getAttribute('data-marker');
      if (mid) {
        const m = this.markers.find((x) => x.id === mid);
        if (m) this.onMarker(m);
        return;
      }
      const ll = this.pointToLonLat(ev);
      if (!ll) return;
      const k = this.cellAt(ll[0], ll[1]);
      if (k >= 0) this.onCell(k, ll);
    });
    this.svg.on('pointermove', (ev: PointerEvent) => this.onMove(this.pointToLonLat(ev)));
    this.svg.on('pointerleave', () => this.onMove(null));

    new ResizeObserver(() => this.resize()).observe(el);
    this.resize();
  }

  private baseRadius(): number {
    return this.w < 560 ? 25 : BASE_RADIUS;
  }

  private pointToLonLat(ev: MouseEvent): [number, number] | null {
    const r = this.el.getBoundingClientRect();
    const [px, py] = this.t.invert([ev.clientX - r.left, ev.clientY - r.top]);
    const ll = this.proj.invert?.([px, py]);
    if (!ll || !Number.isFinite(ll[1])) return null;
    return ll as [number, number];
  }

  cellAt(lon: number, lat: number): number {
    const [fi, fj] = lonlatToIJ(lon, lat);
    const i = Math.floor(fi);
    const j = Math.floor(fj);
    const c = this.atlas.crop;
    if (i < 0 || j < 0 || i >= c || j >= c) return -1;
    return this.atlas.index[i * c + j];
  }

  /** Nearest atlas cell within `rad` cells of a point (for coastal markers). */
  nearestCell(lon: number, lat: number, rad = 6): number {
    const [fi, fj] = lonlatToIJ(lon, lat);
    let best = -1;
    let bd = Infinity;
    const c = this.atlas.crop;
    for (let i = Math.floor(fi) - rad; i <= Math.floor(fi) + rad; i++)
      for (let j = Math.floor(fj) - rad; j <= Math.floor(fj) + rad; j++) {
        if (i < 0 || j < 0 || i >= c || j >= c) continue;
        const k = this.atlas.index[i * c + j];
        if (k < 0) continue;
        const d = (i + 0.5 - fi) ** 2 + (j + 0.5 - fj) ** 2;
        if (d < bd) { bd = d; best = k; }
      }
    return best;
  }

  cellCenterLonLat(k: number): [number, number] {
    const [x, y] = cornerXY(this.atlas.ci[k] + 0.5, this.atlas.cj[k] + 0.5);
    return inverse(x, y);
  }

  private resize() {
    const r = this.el.getBoundingClientRect();
    const w = Math.max(1, Math.round(r.width));
    const h = Math.max(1, Math.round(r.height));
    if (w === this.w && h === this.h) return;
    this.w = w;
    this.h = h;
    this.dpr = Math.min(2, window.devicePixelRatio || 1);
    this.canvas.width = w * this.dpr;
    this.canvas.height = h * this.dpr;
    this.canvas.style.width = `${w}px`;
    this.canvas.style.height = `${h}px`;
    this.svg.attr('width', w).attr('height', h).attr('viewBox', `0 0 ${w} ${h}`);
    const m = Math.min(w, h) < 500 ? 8 : 20;
    this.proj.fitExtent([[m, m], [w - m, h - m]], geoCircle().center([0, 90]).radius(this.baseRadius())());
    this.zoomer.extent([[0, 0], [w, h]]).translateExtent([[-w * 0.5, -h * 0.5], [w * 1.5, h * 1.5]]);
    const path = geoPath(this.proj);
    this.rimPath.setAttribute('d', path({ type: 'Sphere' }) ?? '');
    this.gratPath.setAttribute('d', path(geoGraticule().step([30, 10]).extentMinor([[-180, 40], [180, 89.9]])()) ?? '');
    if (this.land) {
      const d = path(this.land as GeoJSON.Feature) ?? '';
      this.landPath.setAttribute('d', d);
      this.coastPath.setAttribute('d', d);
    }
    // project corner lattice
    const L = this.cornerLL.length / 2;
    this.cx = new Float32Array(L);
    this.cy = new Float32Array(L);
    for (let c = 0; c < L; c++) {
      const lon = this.cornerLL[2 * c];
      if (Number.isNaN(lon)) continue;
      const p = this.proj([lon, this.cornerLL[2 * c + 1]])!;
      this.cx[c] = p[0];
      this.cy[c] = p[1];
    }
    this.paths.clear();
    this.placeMarkers();
    this.draw();
  }

  private cellPath(cells: Int32Array): Path2D {
    const p = new Path2D();
    const C = this.atlas.crop + 1;
    const { ci, cj } = this.atlas;
    const cx = this.cx;
    const cy = this.cy;
    for (let n = 0; n < cells.length; n++) {
      const k = cells[n];
      const a = ci[k] * C + cj[k];
      const b = a + 1;
      const c = a + C + 1;
      const d = a + C;
      p.moveTo(cx[a], cy[a]);
      p.lineTo(cx[b], cy[b]);
      p.lineTo(cx[c], cy[c]);
      p.lineTo(cx[d], cy[d]);
      p.closePath();
    }
    return p;
  }

  private pattern(name: PatternName): CanvasPattern {
    const key = `${name}@${this.dpr}`;
    let pat = this.patterns.get(key);
    if (pat) return pat;
    const s = Math.round((name === 'dither' ? 4 : name === 'dots' ? 5 : 6) * this.dpr);
    const c = document.createElement('canvas');
    c.width = c.height = s;
    const g = c.getContext('2d')!;
    const d = this.dpr;
    if (name === 'dots') {
      g.fillStyle = 'rgba(127,154,150,0.55)';
      g.fillRect(Math.round(s / 2 - d / 2), Math.round(s / 2 - d / 2), Math.max(1, Math.round(d)), Math.max(1, Math.round(d)));
    } else if (name === 'dither') {
      g.fillStyle = 'rgba(3,6,10,0.78)';
      g.fillRect(0, 0, s / 2, s / 2);
      g.fillRect(s / 2, s / 2, s / 2, s / 2);
    } else {
      g.strokeStyle = name === 'amber' ? 'rgba(242,184,75,0.9)' : 'rgba(127,154,150,0.45)';
      g.lineWidth = name === 'amber' ? 1.1 * d : 1 * d;
      g.beginPath();
      if (name === 'amber') {
        g.moveTo(0, 0); g.lineTo(s, s);
        g.moveTo(-s, 0); g.lineTo(s, 2 * s);
        g.moveTo(0, -s); g.lineTo(2 * s, s);
      } else {
        g.moveTo(0, s); g.lineTo(s, 0);
        g.moveTo(-s, s); g.lineTo(s, -s);
        g.moveTo(0, 2 * s); g.lineTo(2 * s, 0);
      }
      g.stroke();
    }
    pat = this.ctx.createPattern(c, 'repeat')!;
    this.patterns.set(key, pat);
    return pat;
  }

  setPaint(key: string, groups: PaintGroup[]) {
    if (key !== this.paintKey) {
      for (const k of [...this.paths.keys()]) if (!k.startsWith('excl')) this.paths.delete(k);
    }
    this.paintKey = key;
    this.groups = groups;
    this.schedule();
  }

  select(k: number) {
    this.selected = k;
    this.schedule();
  }

  private schedule() {
    if (this.raf) return;
    this.raf = requestAnimationFrame(() => {
      this.raf = 0;
      this.draw();
    });
  }

  draw() {
    const ctx = this.ctx;
    const { k, x, y } = this.t;
    const d = this.dpr;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.setTransform(d * k, 0, 0, d * k, d * x, d * y);
    ctx.lineJoin = 'miter';
    const inv = new DOMMatrix([1 / (d * k), 0, 0, 1 / (d * k), 0, 0]);
    for (const g of this.groups) {
      if (!g.cells.length) continue;
      const pk = `${g.key === 'excl' ? 'excl' : this.paintKey}:${g.key}`;
      let p = this.paths.get(pk);
      if (!p) {
        p = this.cellPath(g.cells);
        this.paths.set(pk, p);
      }
      if (g.fill) {
        ctx.fillStyle = g.fill;
        ctx.strokeStyle = g.fill;
        ctx.lineWidth = 0.6 / k;
        if (g.glow) {
          ctx.shadowColor = 'rgba(100,240,200,0.55)';
          ctx.shadowBlur = 7 * d;
        }
        ctx.fill(p);
        ctx.shadowBlur = 0;
        ctx.shadowColor = 'transparent';
        ctx.stroke(p);
      }
      if (g.pattern) {
        const pat = this.pattern(g.pattern);
        pat.setTransform(inv);
        ctx.fillStyle = pat;
        ctx.fill(p);
      }
    }
    if (this.selected >= 0) {
      const p = this.cellPath(Int32Array.of(this.selected));
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.5 / k;
      ctx.stroke(p);
      ctx.strokeStyle = 'rgba(255,255,255,0.35)';
      ctx.lineWidth = 6 / k;
      ctx.stroke(p);
    }
  }

  setMarkers(ms: Marker[]) {
    this.markers = ms;
    this.gMarkers.textContent = '';
    for (const m of ms) {
      const g = document.createElementNS(NS, 'g');
      g.setAttribute('class', `marker marker-${m.kind}`);
      g.setAttribute('data-marker', m.id);
      g.setAttribute('tabindex', '0');
      g.setAttribute('role', 'button');
      g.setAttribute('aria-label', `${m.name}${m.note ? `. ${m.note}` : ''}`);
      g.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this.onMarker(m); }
      });
      const hit = document.createElementNS(NS, 'circle');
      hit.setAttribute('r', '14');
      hit.setAttribute('class', 'hit');
      g.appendChild(hit);
      if (m.kind === 'site') {
        const p = document.createElementNS(NS, 'path');
        p.setAttribute('d', 'M0,-5L5,0L0,5L-5,0Z');
        g.appendChild(p);
      } else {
        if (m.kind === 'hero') {
          const ring = document.createElementNS(NS, 'circle');
          ring.setAttribute('r', '9');
          ring.setAttribute('class', 'ring');
          g.appendChild(ring);
        }
        const c = document.createElementNS(NS, 'circle');
        c.setAttribute('r', m.kind === 'hero' ? '4.5' : '3');
        g.appendChild(c);
      }
      const t = document.createElementNS(NS, 'text');
      t.setAttribute('x', m.kind === 'hero' ? '14' : '8');
      t.setAttribute('y', '3.5');
      g.appendChild(t);
      this.gMarkers.appendChild(g);
    }
    this.refreshMarkerLabels();
    this.placeMarkers();
  }

  refreshMarkerLabels() {
    this.gMarkers.querySelectorAll<SVGGElement>('g.marker').forEach((g) => {
      const m = this.markers.find((x) => x.id === g.getAttribute('data-marker'));
      if (m) g.querySelector('text')!.textContent = this.markerLabel(m);
    });
  }

  private placeMarkers() {
    if (!this.w) return;
    this.gMarkers.querySelectorAll<SVGGElement>('g.marker').forEach((g) => {
      const m = this.markers.find((x) => x.id === g.getAttribute('data-marker'));
      if (!m) return;
      const p = this.proj([m.lon, m.lat]);
      if (!p) return;
      const [x, y] = this.t.apply(p as [number, number]);
      g.setAttribute('transform', `translate(${x.toFixed(1)},${y.toFixed(1)})`);
      const vis = !m.minZoom || this.t.k >= m.minZoom;
      g.style.display = vis && x > -40 && y > -40 && x < this.w + 40 && y < this.h + 40 ? '' : 'none';
      const tx = g.querySelector('text');
      if (tx) tx.style.display = !m.labelZoom || this.t.k >= m.labelZoom ? '' : 'none';
    });
  }

  zoomBy(f: number) {
    this.svg.transition().duration(reduced() ? 0 : 250).call(this.zoomer.scaleBy, f);
  }

  goTo(r: Region) {
    let t = zoomIdentity;
    if (r.center && r.span) {
      const p = this.proj(r.center)!;
      const k = this.baseRadius() / r.span;
      t = zoomIdentity.translate(this.w / 2, this.h / 2).scale(k).translate(-p[0], -p[1]);
    }
    this.svg.transition().duration(reduced() ? 0 : 600).call(this.zoomer.transform, t);
  }

  focusCell(k: number, minZoom = 4) {
    const ll = this.cellCenterLonLat(k);
    const p = this.proj(ll)!;
    const z = Math.max(this.t.k, minZoom);
    const t = zoomIdentity.translate(this.w / 2, this.h / 2).scale(z).translate(-p[0], -p[1]);
    this.svg.transition().duration(reduced() ? 0 : 500).call(this.zoomer.transform, t);
  }
}

export function reduced(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/** d3-geo wants clockwise exterior rings (spherical polygons); RFC 7946 GeoJSON is counter-clockwise.
 *  Reverse any polygon whose area exceeds a hemisphere, so either convention renders as land. */
function fixWinding(g: GeoJSON.GeoJsonObject): GeoJSON.GeoJsonObject {
  const fixPoly = (rings: GeoJSON.Position[][]): GeoJSON.Position[][] => {
    const poly: GeoJSON.Polygon = { type: 'Polygon', coordinates: rings };
    return geoArea(poly) > 2 * Math.PI ? rings.map((r) => [...r].reverse()) : rings;
  };
  const fixGeom = (geom: GeoJSON.Geometry | null): GeoJSON.Geometry | null => {
    if (!geom) return geom;
    if (geom.type === 'Polygon') return { ...geom, coordinates: fixPoly(geom.coordinates) };
    if (geom.type === 'MultiPolygon') return { ...geom, coordinates: geom.coordinates.map(fixPoly) };
    if (geom.type === 'GeometryCollection') return { ...geom, geometries: geom.geometries.map((x) => fixGeom(x)!) };
    return geom;
  };
  const o = g as GeoJSON.FeatureCollection | GeoJSON.Feature | GeoJSON.Geometry;
  if (o.type === 'FeatureCollection') return { ...o, features: o.features.map((f) => ({ ...f, geometry: fixGeom(f.geometry)! })) } as GeoJSON.FeatureCollection;
  if (o.type === 'Feature') return { ...o, geometry: fixGeom(o.geometry)! } as GeoJSON.Feature;
  return fixGeom(o as GeoJSON.Geometry)!;
}
