import type { Card } from './types';

export const esc = (s: unknown): string =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!);

export const fmtInt = (v: number): string => Math.round(v).toLocaleString('en-GB');

export function fmtNum(v: number, digits = 2): string {
  return v.toLocaleString('en-GB', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function fmtEnergy(mwh: number): string {
  if (mwh >= 1e6) return `${fmtNum(mwh / 1e6, mwh >= 1e7 ? 1 : 2)} TWh`;
  if (mwh >= 1e3) return `${fmtNum(mwh / 1e3, 1)} GWh`;
  return `${fmtInt(mwh)} MWh`;
}

export function fmtLat(lat: number): string {
  return `${Math.abs(lat).toFixed(2)}°${lat >= 0 ? 'N' : 'S'}`;
}
export function fmtLon(lon: number): string {
  return `${Math.abs(lon).toFixed(2)}°${lon >= 0 ? 'E' : 'W'}`;
}

export function fillDate(s: string | undefined, w: number): string {
  if (!s) return '';
  return s.replace(/\{W1\}/g, String(w + 1)).replace(/\{W\}/g, String(w));
}

export function guideHTML(card: Card, cls = ''): string {
  return `<dl class="guide ${cls}">
    <div><dt>MEANING</dt><dd>${esc(card.meaning)}</dd></div>
    <div><dt>WHY IT MATTERS</dt><dd>${esc(card.why)}</dd></div>
    <div><dt>NOT PROOF OF</dt><dd>${esc(card.not_proof)}</dd></div>
    <div><dt>EXAMPLE</dt><dd>${esc(card.example)}</dd></div>
  </dl>`;
}

export function h<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, html?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
}

export function swatchSVG(o: { fill?: string; pattern?: string; outline?: boolean }, size = 10): string {
  const s = size;
  let body = `<rect width="${s}" height="${s}" fill="${o.fill ?? 'none'}"${o.outline ? ' stroke="#44585a" stroke-width="1"' : ''}/>`;
  if (o.pattern === 'hatch') body += `<path d="M0,${s}L${s},0M-2,2L2,-2M${s - 2},${s + 2}L${s + 2},${s - 2}" stroke="#7f9a96" stroke-width="1"/>`;
  if (o.pattern === 'amber') body += `<path d="M0,0L${s},${s}M-2,${s - 2}L2,${s + 2}M${s - 2},-2L${s + 2},2" stroke="#f2b84b" stroke-width="1.2"/>`;
  if (o.pattern === 'dots') body += `<circle cx="${s / 4}" cy="${s / 4}" r="0.9" fill="#a0b3b0"/><circle cx="${(3 * s) / 4}" cy="${(3 * s) / 4}" r="0.9" fill="#a0b3b0"/>`;
  if (o.pattern === 'dither') body += `<rect width="${s / 2}" height="${s / 2}" fill="#03060a" opacity=".8"/><rect x="${s / 2}" y="${s / 2}" width="${s / 2}" height="${s / 2}" fill="#03060a" opacity=".8"/>`;
  return `<svg class="sw" width="${s}" height="${s}" viewBox="0 0 ${s} ${s}" aria-hidden="true">${body}</svg>`;
}
