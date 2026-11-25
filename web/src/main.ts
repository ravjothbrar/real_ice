import './style.css';
import { loadAtlas, getJSON, type Atlas } from './data';
import { Instrument } from './instrument';
import { heroHTML, sectionsHTML, footerHTML, wireCopy } from './page';
import { reduced } from './map';
import { esc } from './util';
import { sourcesFrom } from './normalize';
import type { Manifest } from './types';

const t0 = performance.now();
const app = document.getElementById('app')!;
app.innerHTML = `
  <div class="page-top"></div>
  <section class="inst-wrap" aria-label="Instrument">
    <div class="inst" id="instrument"></div>
    <p class="attr-line">Independent project built for Real Ice. Not affiliated.</p>
  </section>
  <div class="page-rest"></div>`;
const instEl = document.getElementById('instrument')!;

// ---- boot sequence (1 s, skippable, honours prefers-reduced-motion) ----
const boot = document.createElement('div');
boot.className = 'boot';
boot.setAttribute('role', 'status');
boot.innerHTML = '<pre class="boot-log"></pre><button type="button" class="boot-skip">SKIP ›</button>';
instEl.appendChild(boot);
const log = boot.querySelector('.boot-log')!;
const lines: string[] = [];
const push = (s: string) => { lines.push(s); log.textContent = lines.join('\n'); };
let skipped = reduced();
const skip = () => { skipped = true; boot.remove(); };
boot.querySelector('.boot-skip')!.addEventListener('click', skip);
window.addEventListener('keydown', (e) => { if (e.key === 'Escape' && boot.isConnected) skip(); }, { once: true });
const wait = (ms: number) => new Promise((r) => setTimeout(r, skipped ? 0 : ms));

async function bootSeq() {
  if (skipped) { boot.remove(); return; }
  push('INITIALIZING ATLAS ENGINE');
  const manifest = await getJSON<Manifest>('manifest.json').catch(() => null);
  const rawSummary = manifest?.sources?.length ? {} : await getJSON<Record<string, unknown>>('summary.json').catch(() => ({}));
  await wait(120);
  const src = manifest ? sourcesFrom(manifest, rawSummary) : [];
  if (src.length) {
    push(`CONNECTING ${src.length} SOURCES`);
    for (let i = 0; i < src.length; i++) {
      await wait(Math.max(30, 440 / src.length));
      push(`${i === src.length - 1 ? '└─' : '├─'} ${(src[i].short ?? src[i].name).toUpperCase()}`);
    }
  }
  await wait(160);
}

async function main() {
  const bootDone = bootSeq();
  const res = await loadAtlas().catch((e) => { console.error(e); return null; });
  const atlas: Atlas | null = res?.atlas ?? null;
  document.querySelector('.page-top')!.innerHTML = heroHTML(atlas);
  document.querySelector('.page-rest')!.innerHTML = sectionsHTML(atlas) + footerHTML(atlas);
  wireCopy(document);
  if (!atlas) {
    await bootDone;
    instEl.insertAdjacentHTML('afterbegin', `<div class="inst-empty"><span class="wm">SURVIVAL GAP ATLAS</span><p>No data. Run <b>make export</b> to write web/public/data/.</p></div>`);
    boot.remove();
    return;
  }
  if (atlas.manifest.fixture) document.title = 'Survival Gap Atlas (synthetic fixture)';
  const holder = document.createElement('div');
  holder.className = 'inst-inner';
  instEl.prepend(holder);
  const inst = new Instrument(holder, atlas, res!.land);
  await inst.start();
  await new Promise((r) => requestAnimationFrame(() => r(null)));
  // time to data loaded + first map render (the boot overlay runs in parallel and is not counted)
  const ms = Math.round(performance.now() - t0);
  const w = window as unknown as { __atlasRender: number; __atlasReady: number; __inst: Instrument };
  w.__atlasRender = ms;
  w.__inst = inst;
  console.info(`[atlas] data load + first render ${ms} ms`);
  await bootDone;
  if (boot.isConnected) {
    push(`READY · ${atlas.n.toLocaleString('en-GB')} CELLS · ${atlas.manifest.winters.length} WINTERS`);
    await wait(160);
    boot.remove();
  }
  w.__atlasReady = Math.round(performance.now() - t0);
}

main().catch((e) => {
  console.error(e);
  instEl.innerHTML = `<div class="inst-empty"><p>${esc(String(e))}</p></div>`;
});
