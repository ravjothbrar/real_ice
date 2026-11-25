import type { Atlas } from './data';
import { esc, fmtInt, fmtNum } from './util';
import { UI_LAYERS } from './layers';

const CLI = ['atlas band --winter 2024 --threshold 0.2', 'atlas cell 69.05N -105.10E', 'atlas scale --km2 1000000'];

function cmdBlock(lines: string[], cls = ''): string {
  return `<div class="cmd ${cls}"><pre>${lines.map((l) => `<span class="pr">&gt;</span> ${esc(l)}`).join('\n')}</pre>
    <button type="button" class="copy" data-copy="${esc(lines.join('\n'))}">COPY</button></div>`;
}


export function heroHTML(a: Atlas | null): string {
  return `
  <nav class="topnav" aria-label="Sections">
    <a class="mark" href="#top">SURVIVAL GAP ATLAS</a>
    <div class="navlinks"><a href="#instrument">&gt; instrument</a><a href="#method">&gt; method</a><a href="#evidence">&gt; evidence</a><a href="#limits">&gt; limits</a><a href="#spec">&gt; spec</a></div>
  </nav>
  <section class="hero" id="top">
    <h1 class="statement">Where thickening changes whether the ice survives.</h1>
    <div class="hero-row">
    <p class="hero-sub">Pumping seawater onto winter sea ice makes it thicker. This map shows where that extra ice would decide whether it lasts the summer, and where it wouldn’t. Built on 15 years of satellite data, every weakness shown.</p>
    <div class="hero-actions">
      <a class="pill" href="#instrument">OPEN THE INSTRUMENT ↓</a>
    </div>
    </div>
  </section>`;
}

export function sectionsHTML(a: Atlas | null): string {
  const s = a?.summary;
  const n = s?.ensemble_n;
  const method = [
    ['01', 'Inputs', 'Satellite thickness products, ERA5 freezing degree days and OSI SAF ice drift give every 25 km cell a start thickness, a winter of growth and a chance of staying in the Arctic.'],
    ['02', 'Ensemble', `${n ? `A ${fmtInt(n)}-draw` : 'An'} ensemble asks whether each cell reaches survival thickness by September, with and without flooding, calibrated to the Cambridge Bay field paper.`],
    ['03', 'Band', 'The band is where flooding lifts the survival probability by more than the threshold; every other cell survives anyway, is hopeless, or is blocked by thin ice.'],
  ];
  return `
  <section class="sec" id="method">
    <div class="label">[Method]</div>
    <div class="method-grid">${method.map(([no, t, b]) => `<article class="mcard"><div class="mno">${no} · ${t}</div><p>${esc(b)}</p></article>`).join('')}</div>
  </section>

  <section class="dark-statement" aria-label="Statement">
    <p class="statement statement-dark">A map of uncertainty, not a list of sites.</p>
    <div class="hyphens" aria-hidden="true">------------------------</div>
  </section>

  <section class="sec" id="evidence">
    <div class="label">[Evidence]</div>
    ${evidenceHTML(a)}
  </section>

  <section class="sec" id="limits">
    <div class="label">[Limits]</div>
    <h2 class="h2">What this cannot tell you</h2>
    <div class="accordion">${limitsHTML(a)}</div>
  </section>

  <section class="sec" id="spec">
    <div class="label">[Spec]</div>
    <h2 class="h2">At a glance</h2>
    <div class="spec-grid">
      <table class="spec">${specRows(a).map(([k, v]) => `<tr><th>${esc(k)}</th><td>${v}</td></tr>`).join('')}</table>
      <div class="spec-cli"><p class="cli-note">One backend, three faces: the map, this page and a command line.</p>${cmdBlock(CLI)}</div>
    </div>
  </section>`;
}

function evidenceHTML(a: Atlas | null): string {
  const h = a?.summary.hindcast;
  const card = a?.summary.cards?.['hindcast'];
  if (!h?.metrics?.length || !card) {
    return `<h2 class="h2">Hindcast</h2><p class="body empty">No hindcast yet. Run <code>make hindcast &amp;&amp; make export</code>.</p>`;
  }
  const m0 = h.metrics[0];
  const model = m0.rows.find((r) => r.model) ?? m0.rows[0];
  const base = m0.rows.filter((r) => r !== model);
  const hib = m0.higher_is_better !== false;
  const beats = base.every((b) => (hib ? model.value > b.value : model.value < b.value));
  const verdict = h.beats_both != null
    ? h.beats_both
      ? `Beats both naive baselines on ${h.beats_label ?? m0.label}.`
      : `Does not beat both naive baselines on ${h.beats_label ?? m0.label}. Reported as found.`
    : beats ? `Beats both naive baselines on ${m0.label}.` : `Does not beat ${base.filter((b) => (hib ? model.value <= b.value : model.value >= b.value)).map((b) => b.label).join(' or ')} on ${m0.label}.`;
  const charts = h.metrics
    .map((m) => {
      const max = Math.max(...m.rows.map((r) => Math.abs(r.value)), 1e-9);
      return `<div class="ev-metric"><div class="ev-mlabel">${esc(up(m.label))}</div>${m.rows
        .map((r) => `<div class="ev-row${r.model ? ' model' : ''}"><span>${esc(up(r.label))}</span><i style="width:${(Math.abs(r.value) / max) * 100}%"></i><b>${fmtNum(r.value, 2)}</b></div>`)
        .join('')}</div>`;
    })
    .join('');
  return `
    <h2 class="h2">Hindcast against September ice${h.period ? `, ${esc(h.period)}` : ''}</h2>
    <p class="body">${esc(verdict)} ${h.verdict ? esc(h.verdict) : ''}</p>
    <figure class="ev-frame">
      <div class="ev-head"><span>HINDCAST · ${esc(up(model.label))} VS BASELINES</span><span class="ev-big">${fmtNum(model.value, 2)}</span></div>
      ${charts}
      <figcaption>${esc(card.meaning)} Not proof of: ${esc(card.not_proof.replace(/^FIXTURE\.\s*/, ''))}</figcaption>
    </figure>
    <p class="src">Source: ${esc(h.source ?? 'atlas hindcast')}${h.date ? ` · ${esc(h.date)}` : ''}</p>`;
}

function limitsHTML(a: Atlas | null): string {
  const items: [string, string][] = [
    ['Indigenous use areas and ringed seal habitat are not in open data: community consent required.', 'The atlas cannot see where people hunt, travel or fish, or where seals den. Those places are never ranked as targets here; decisions about them belong to the communities that use them.'],
    ['Start-of-winter thickness is the weakest input.', 'All satellite thickness products are winter-only. October and November thin-ice retrievals are biased, and melt-affected months are excluded.'],
    ['Thickness products disagree.', 'Radar altimetry depends on assumed snow depth and density. The spread across products is shown as its own layer and used as uncertainty.'],
    ['Survival thickness is a prior, not a measurement.', 'Melt rates come from the Beaufort and Transpolar regimes in van Dijke (2022). Whether they generalise to other seas is not verified.'],
    ['Reanalysis runs warm over sea ice.', 'ERA5 has a warm bias over sea ice in cold conditions (Wang et al., 2019), which lowers freezing degree days and modelled growth.'],
    ['Summer drift is modelled.', 'OSI SAF summer drift is gap-filled with a free-drift model, so retention to September carries more uncertainty than winter drift.'],
    ['A 25 km cell is not a 1 km field site.', 'Each cell is 625 km². Real Ice field evidence is one site near Cambridge Bay over one to three winters; extrapolating it is an assumption.'],
    ['Shipping corridors are hand-drawn.', 'Arctic ship-traffic data (ASTD) is not open. Corridors are approximate and labelled as hand-curated.'],
    ['Not a siting tool.', 'Exploratory and independent. It does not recommend a deployment site and does not claim that thickening works, or that it does not.'],
  ];
  const cards = a?.summary.cards ?? {};
  const notProof = UI_LAYERS.filter((L) => cards[L.id]).map((L) => `<li><b>${esc(L.label)}</b> is not proof of: ${esc(cards[L.id].not_proof)}</li>`);
  if (cards['excl']) notProof.push(`<li><b>EXCLUSIONS</b> is not proof of: ${esc(cards['excl'].not_proof)}</li>`);
  for (const l of a?.summary.limits ?? []) items.push([l.title, l.body]);
  const html = items.map(([t, b], i) => acc(t, `<p>${esc(b)}</p>`, i === 0));
  if (notProof.length) html.push(acc('What each layer is not proof of.', `<ul class="np">${notProof.join('')}</ul>`, false));
  return html.join('');
}

function acc(title: string, body: string, open: boolean): string {
  return `<details class="acc"${open ? ' open' : ''}><summary><span>${esc(title)}</span><i class="plus" aria-hidden="true"></i></summary><div class="acc-body">${body}</div></details>`;
}

function specRows(a: Atlas | null): [string, string][] {
  if (!a) return [['STATUS', 'No data. Run <code>make export</code>.']];
  const m = a.manifest;
  const s = a.summary;
  const t = s.thresholds;
  const rows: [string, string][] = [];
  if (m.grid.name) rows.push(['GRID', esc(m.grid.name)]);
  rows.push(['CELLS', `${fmtInt(a.n)} ice-capable cells · ${fmtInt(a.cellArea)} km² each`]);
  if (m.winters.length) rows.push(['WINTERS', m.winters.map((w) => esc(w.label) + (w.partial ? ' (partial)' : '')).join(', ')]);
  if (s.ensemble_n) rows.push(['ENSEMBLE', `${fmtInt(s.ensemble_n)} Monte Carlo draws per cell`]);
  if (t) rows.push(['BAND RULES', `survives anyway P<sub>without</sub> ≥ ${t.survives ?? 0.7} · hopeless P<sub>with</sub> ≤ ${t.hopeless ?? 0.2} · band uplift ≥ ${t.uplift ?? 0.2} (slider)${t.guard_m ? ` · no flooding below ${t.guard_m} m` : ''}`]);
  const nl = UI_LAYERS.filter((L) => L.needs.every((n) => a.hasLayer(n)) && s.cards?.[L.id]).length + (a.stat['excl'] && s.cards?.['excl'] ? 1 : 0);
  rows.push(['LAYERS', `${nl}, each with a four-line signal guide`]);
  if (m.sources?.length) rows.push(['SOURCES', `${m.sources.length} open datasets, credited below`]);
  rows.push(['STACK', 'Python pipeline · static site · canvas + d3-geo · no server']);
  rows.push(['BUILT', esc(m.built)]);
  return rows;
}

export function footerHTML(a: Atlas | null): string {
  const src = a?.manifest.sources ?? [];
  return `
  <footer class="foot">
    <p class="attr">Independent project built for Real Ice. Not affiliated.</p>
    <div class="credit-hero">
      <div class="label">[Thickness data]</div>
      <p>Daily 25 km ICESat-2 + SMOS/SMAP Gaussian-process sea-ice thickness, 2018–2025, by <b>Petty, Cardinale, Tsamados, Gregory and Cabaj</b>. Zenodo, doi:<a href="https://doi.org/10.5281/zenodo.22147361">10.5281/zenodo.22147361</a> →</p>
    </div>
    ${src.length ? `<div class="label">[Data credits]</div><ul class="credits">${src
      .map((s) => `<li><b>${esc(s.name)}</b>${s.authors ? `, ${esc(s.authors)}` : ''}${s.citation ? `. ${esc(s.citation)}` : ''}${s.doi ? ` doi:<a href="https://doi.org/${esc(s.doi)}">${esc(s.doi)}</a>` : s.url ? ` <a href="${esc(s.url)}">${esc(s.url.replace(/^https?:\/\//, ''))}</a>` : ''}${s.licence ? ` · ${esc(s.licence)}` : ''}${s.accessed ? ` · accessed ${esc(s.accessed)}` : ''}</li>`)
      .join('')}</ul>` : ''}
    <p class="foot-meta">Field results: Real Ice, AGU <i>Earth’s Future</i> doi:10.1029/2025EF007894 (22 May 2026). Scale numbers: Ocean Visions roadmap. Land: Natural Earth.${a ? ` Built ${esc(a.manifest.built)}.` : ''} Exploratory; not a deployment recommendation.</p>
  </footer>`;
}

export function wireCopy(root: ParentNode) {
  root.querySelectorAll<HTMLButtonElement>('.copy').forEach((b) =>
    b.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(b.dataset.copy ?? '');
        b.textContent = 'COPIED';
      } catch {
        b.textContent = 'SELECT + COPY';
      }
      setTimeout(() => (b.textContent = 'COPY'), 1500);
    }),
  );
}

/** Uppercase Latin letters only, so Greek symbols such as ρ keep their meaning. */
const up = (s: string) => s.replace(/[a-z]/g, (c) => c.toUpperCase());
