// Post-process `vite build --mode single`: inline JS, CSS and the data files (base64 for .bin)
// into one self-contained dist-single/index.html. Fonts stay on Google Fonts with system fallbacks.
// Data dir: public/data (from `make export`). Override with ATLAS_DATA_DIR for local tests.
import { readFileSync, writeFileSync, readdirSync, rmSync, existsSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const out = join(root, process.env.SINGLE_OUT ?? 'dist-single');
const dataDir = process.env.ATLAS_DATA_DIR ? join(root, process.env.ATLAS_DATA_DIR) : join(root, 'public', 'data');

if (!existsSync(join(dataDir, 'manifest.json'))) {
  console.error(`No data in ${dataDir}. Run make export.`);
  process.exit(1);
}

let html = readFileSync(join(out, 'index.html'), 'utf8');
const safe = (s) => s.replace(/<\/(script)/gi, '<\\/$1').replace(/<!--/g, '<\\!--');

html = html.replace(/<link rel="stylesheet"[^>]*href="\.\/(assets\/[^"]+\.css)"[^>]*>/g, (_, p) => `<style>${readFileSync(join(out, p), 'utf8')}</style>`);
html = html.replace(/<script type="module" crossorigin src="\.\/(assets\/[^"]+\.js)"><\/script>/g, (_, p) => `<script type="module">${safe(readFileSync(join(out, p), 'utf8'))}</script>`);
if (/src="\.\/assets\//.test(html) || /href="\.\/assets\//.test(html)) {
  console.error('inline-single: an asset reference was not inlined');
  process.exit(1);
}

const data = {};
for (const f of readdirSync(dataDir).sort()) {
  const p = join(dataDir, f);
  if (!statSync(p).isFile()) continue;
  if (f.endsWith('.json')) data[f] = JSON.parse(readFileSync(p, 'utf8'));
  else if (f.endsWith('.bin')) data[f] = readFileSync(p).toString('base64');
}
const blob = `<script>window.__ATLAS_DATA__=${safe(JSON.stringify(data))};</script>`;
html = html.replace('</head>', `${blob}\n</head>`);
writeFileSync(join(out, 'index.html'), html);
rmSync(join(out, 'assets'), { recursive: true, force: true });
const mb = Buffer.byteLength(html) / 1e6;
console.log(`dist-single/index.html: ${mb.toFixed(2)} MB (${Object.keys(data).length} data files inlined)`);
if (mb > 10) console.warn('warning: single file is over 10 MB');
