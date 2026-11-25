# Survival Gap Atlas — build brief for Real Ice

Read this whole file before doing anything. It is the single source of truth: what to build, why, with what data, how to calculate, how it should look, how to test it, and how to send it. Work phase by phase. Commit after each phase.

Owner: Ravjoth Brar (ravjothbrar.com), UK school student. Goal: a build good enough that Real Ice's two co-CEOs want him for a summer placement.

---

## 0. How to work (rules for Claude Code)

1. Do the phases in order (section 10). Each has an exit test. Do not start the next phase until the exit test passes.
2. Never invent data. If a dataset cannot be fetched, stop, say so in `ASSUMPTIONS.md`, and use a small hand-curated seed set labelled as such. An honest empty state beats a fake number.
3. Every number shown anywhere in the UI carries a source and a date. Keep `data/PROVENANCE.json` (dataset, URL, DOI, licence, access date, checksum).
4. Ask before downloading anything over 1 GB. Prefer subsets and coarse grids. Cache everything under `data/raw/` and never re-download.
5. Credentials (Copernicus CDS key, NASA Earthdata login, ESA EO sign-in) come from environment variables or `.env` (git-ignored). Never print or commit them. If one is missing, tell Ravjoth exactly which account to create.
6. Be a polite guest on public servers: identify yourself in the User-Agent, rate-limit, single-thread, honour terms and robots.txt.
7. Keep a running `ASSUMPTIONS.md` (every guess, constant, threshold, with where it came from) and `RESULTS.md` (every eval number with the command that produced it).
8. Write the evaluation set (section 8) BEFORE tuning any parameter. Never let a model generate ground truth for a test of that same model.
9. Order work so an early stop still leaves something demonstrable: data and core calculation first, UI second, polish last.
10. Use the TaskCreate/task list for each phase. Last step of every phase: run the tests and look at the output.

---

## 1. The project in one paragraph

An interactive, explainable map of the Arctic that answers one question: **where would winter ice thickening change whether sea ice survives the summer?** It fuses several open satellite and reanalysis datasets, runs an ensemble calculation per grid cell, and shows the result as a band (not a heatmap) between "survives anyway" and "hopeless". It also converts Real Ice's own scale numbers (1 million km² a year) into energy and fleet requirements, and it shows the weakness of every layer next to it. It is an independent, open project, not research and not a deployment recommendation.

Working title: **Survival Gap Atlas**. Line under the map everywhere: *Independent project built for Real Ice. Not affiliated.*

Why this one: it is the same shape as Ravjoth's earlier builds that worked (Baltic Seabed Watch: public feeds fused, every signal shown with its weakness, a simulated coverage layer; GammaSignal: a data layer plus a fun interface). It also fills a gap Real Ice and its partners state but have not published a tool for.

---

## 2. The company: Real Ice (facts only, with sources)

- UK-based sea-ice thickening company. Pumps seawater onto winter sea ice so it freezes and thickens. Staff: 9 (UArctic member profile). Co-CEOs: Andrea Ceccolini and Cían Sherwin (Cambridge Centre for Climate Repair page). Cían Sherwin's LinkedIn says he led Real Ice from a wholly volunteer effort for 5 years.
- Homepage mission: develop a high-autonomy, modular system of underwater drones to thicken Arctic sea ice at scale using zero-carbon energy. Drones are planned, not shipped. https://www.realice.eco/
- Field work: Nome, Alaska (Feb 2023); Cambridge Bay, Nunavut (Jan 2024, 2025, 2026). Inuit community guides site choice, safety and governance. Funded by ARIA via the Cambridge-led "Re-thickening Arctic Sea Ice" (RASi) project.
- 2024/25 paper (AGU, DOI 10.1029/2025EF007894, published 22 May 2026): 1 x 1 km site, 3 control areas, 8 test areas, 0.25 km² flooded in total. Flooded areas up to 32 cm thicker than control by mid-May; snow 1-13 cm thinner; areas flooded twice thickened more; flooded ice brighter and melted more slowly; a drained melt pond brightened within a week. Mongabay (July 2026) reports a 50 cm difference at the end of May 2026. A 30 cm gain is roughly the thinning seen at Cambridge Bay over 50 years.
- Scale model (Ocean Visions roadmap page): thicken 1,000,000 km² per year, about 70 cm added, about 700 km³ of extra ice, about 8 MWh per km², about $43bn over 10 years (about $6bn a year at full scale), and about 5% of Arctic sea-ice area per year to begin repair. Sites are chosen as "areas most at risk of summer melt, or that could be restored to full-year coverage based on historical patterns and start-of-winter thickness". Drones powered by hydrogen fuel cells. CBC: drones would find drilling sites away from settlements, shipping routes and fragile wildlife areas.
- Stated gap: the RASi poster says thickening the whole Arctic is impractical, so satellite analysis will be used to find areas of maximum benefit. No datasets, sensors or maps are named. This atlas operationalises that sentence.
- Field-operations facts (ARIA community-engagement PDF, winter 2025/26): site about 7 km from Cambridge Bay in water over 20 m deep; thickening January to end March; ponds at about -30 C freeze in under 24 h, deeper ones about 48 h; thin early ice (about 40 cm) bent under pumped water; decisions on start date, pumping schedule and drainage are made manually from conditions.
- Contact: no public email. Contact form at https://www.realice.eco/contact and LinkedIn company page realice-eco. Do not guess email addresses.
- Controversy to respect: critics call polar geoengineering environmentally dangerous (Frontiers in Science, 2025); removing snow may affect ring seals; one researcher says thickened ice may last only 1-2 years before drifting away. The tool must show uncertainty, not advocate.

Risk to state honestly: Michel Tsamados (UCL) is an author on the RASi poster and co-author of a daily ICESat-2/SMOS thickness dataset, so the project partners have strong in-house satellite capability and may have an internal siting analysis. No public tool was found, but that is not proof. Position this as an open explainer with its limits shown, never as new science.

---

## 3. Design brief (embed this; it is the design skill)

One page, two surfaces. The **instrument** is a dark, dense, intelligence-terminal map with panels (after crucix.live). The **page** around it is stark, light and typographic (after omnigraph.dev, factory.com and a Times New Roman text-deck style). They never blend: the instrument is a window cut into the white page.

Tokens were read from screenshots, not source CSS. Treat hex values as close matches and adjust by eye. Take a screenshot at 1440 and 390 px wide at the end of the UI phase and compare against crucix.live and omnigraph.dev.

### Rule of two surfaces
- Instrument (dark): map, layer panels, status bar, signal guide. Data only. No editorial headlines inside it.
- Page (light): statements, method, limits, spec table, CLI snippet. Words only. No live map on white without the dark frame.
- One accent per surface. Instrument: mint. Page: none (black pills).
- Hard cut between surfaces: 96-160 px white margin, no gradients, no fades.
- Charcoal #262626 is for text-only statement sections on the page. Deep navy #03060A is for data only.

### Instrument tokens
- Background #03060A to #050C10. Panel fill rgba(5,12,16,0.85). Panel border 1px solid rgba(100,240,200,0.14). Radius 2-4 px. No shadows, no blur.
- Accents: mint #64F0C8 (active tab, key values, live dots), cyan #4CC9F0 (context), amber #F2B84B (exclusions/cautions), red #E5484D (real alerts only).
- Text: primary #D7E3E0, secondary #7F9A96, disabled #44585A.
- Type: JetBrains Mono (fallback ui-monospace, SF Mono, Menlo). Labels uppercase 10-11 px, letter-spacing 0.14em. Numbers 14-28 px, tabular-nums. Panel titles Space Grotesk or Inter 13 px.
- Header: wordmark in tracked mono; status chip right (e.g. HIGH ALERT outlined red); region tabs as a button grid, active tab filled mint with dark text; row of small chips: LAYERS 9/11, SWEEP, DATE, DELTA; a WHAT THESE LAYERS MEAN button.
- Panels: title left, state chip right (LIVE, WINTER ONLY, MODEL). Rows are label left, value right, one hairline between rows.
- Boot sequence: one 1 s mono sequence (INITIALIZING ATLAS ENGINE, CONNECTING 9 SOURCES, then a tree line of source names such as CRYOSAT, SMOS, ICESAT-2, OSI SAF, ERA5). Skippable. Honour prefers-reduced-motion.

### Map rules
- Polar stereographic centred on the pole (EPSG:3413-style, central meridian -45). Never a world rectangle.
- Land very dark teal-grey (about #0D1A1F), 0.5 px lighter coastline, faint graticule. No satellite imagery.
- Layers glow, not fill. Mint = the band where thickening matters. Cyan = context. Amber hatch = excluded cells. Opacity encodes confidence, never blur; uncertain cells are dithered or hatched.
- Markers: small circles for settlements, diamonds for fixed sites, one white dot for the hero site (Cambridge Bay). 10 px mono label with the value.
- Controls top-left: + / - / mode toggle in 1 px outlined squares. Hint top-right: SCROLL TO ZOOM - DRAG TO PAN. Legend row along the bottom with dot + uppercase label.
- Click any cell to open a side card: value, source, date, uncertainty, and the four-line guide for the layer.
- Region tabs: PAN-ARCTIC, BEAUFORT, TRANSPOLAR, CANADIAN ARCHIPELAGO, BARENTS-KARA.

### Signal guide (the weakness card), mandatory for every layer and metric
Exactly four lines, in this order: **Meaning / Why it matters / Not proof of / Example** (one real number). Subtitle: *Interpretation guides, not conclusions.* No layer ships without its card.

### Page tokens
- Background #FAFAFA (alternate #FFFFFF). Text #111111, secondary #6B6B6B, hairline #E4E4E4, card #EBEBEB. No gradients, no drop shadows, no icons except one mark. Card radius 12-14 px.
- Statements: Times New Roman, italic, weight 400, 56-96 px desktop (40-56 mobile). Max 12 words. One idea per section. Typographic quotes and apostrophes.
- Optional divider under a statement: a line of 24 hyphens, used once or twice per page.
- Section labels: bracketed mono, grey, 12 px: [Method] [Evidence] [Limits] [Spec].
- Body: Inter (fallback system-ui) 17-19 px, line-height 1.55, max 62ch, #222. Non-statement headings: Inter or a tight grotesk, uppercase allowed.
- Buttons: black pill #111 with white mono uppercase 12 px; secondary 1 px outline. Links end in an arrow.
- Code/CLI: #EFEFEF block, mono, leading `>`, Copy button. Spec table: label left in grey mono, value right, hairlines. Limits as an accordion with a + toggle.
- Optional single dark statement section: #262626 background, #F2F2F2 text. At most one per page.

### Page order
1. Hero: italic serif statement, one mono subtitle line, one black pill, one `>` command.
2. The instrument, full width, dark frame, attribution line beneath.
3. [Method]: three blocks max, one sentence each.
4. [Evidence]: the one chart or number that proves it, with source and date.
5. [Limits]: accordion mirroring the signal guide.
6. [Spec] table and CLI snippet.
7. Footer: attribution, data credits, date built.

### Copy
Terse, declarative, fragments allowed, no hype. Every number has source and date. Plain line: *Independent project built for Real Ice. Not affiliated.* Empty states say what to run. No emoji.

### Responsive and accessibility
Under 900 px the map comes first, panels stack, region tabs scroll horizontally. Touch targets 44 px. Instrument labels at least 10 px, page text at least 16 px. Touch pan/zoom; a keyboard-reachable table fallback of the same cells. Contrast 4.5:1; never rely on colour alone (pair with hatch or shape). Page stays light, instrument stays dark.

### Do not
Gradients, glassmorphism, shadows, a second accent on a surface, mint on the white page, Times New Roman inside the instrument, monospace paragraphs on the page, rounded pill panels inside the instrument, more than one dark statement section.

---

## 4. Data inputs (verified to exist; check access when you fetch)

| # | Layer | Dataset | Notes |
|---|---|---|---|
| 1 | Thickness A | AWI CryoSat-2/Sentinel-3/SMOS (CS3SMOS) weekly L4, winter only | Anonymous FTP via AWI, also ESA SMOS dissemination (EO sign-in). The 2026/27 Arctic season began with a field for 15-22 Oct 2026, so the atlas can show this winter. https://spaces.awi.de/display/CS2SMOS |
| 2 | Thickness B | ICESat-2 + SMOS/SMAP Gaussian-process fusion, daily 25 km, 2018-2025 (Petty, Cardinale, Tsamados, Gregory, Cabaj) | Zenodo DOI 10.5281/zenodo.22147361 (ESSD preprint essd-2026-700). Credit the authors prominently. |
| 3 | Thickness C | DTU monthly 5 km multi-altimeter (ERS-2, Envisat, CryoSat-2), 1995 to April 2025 | Zenodo record 13699698, 1.7 GB zip. Ask before downloading. |
| 4 | Thickness D | CPOM / EOCIS CryoSat-2 monthly 5 km, winter (Oct-Apr) | URL pattern `https://www.cpom.ucl.ac.uk/eocis/seaice/data/EOCIS-SEAICE-L3C-SITHICK-CS2-5KM-YYYYMM-fv1.0.nc` |
| 5 | Ice motion | OSI SAF sea-ice drift CDR, daily 75 km EASE2, 1991-2020 (DOI 10.15770/EUM_SAF_OSI_0012; also on CDS as satellite-sea-ice-drift) | Winter RMSE about 2.1 km vs buoys; summer drift is gap-filled with a free-drift model so retention carries more uncertainty. NRT product OSI-405 for current winter. |
| 6 | Ice age | NSIDC EASE-Grid Sea Ice Age v4 (NSIDC-0611), weekly, to end 2024 | Earthdata login. Quicklook product NSIDC-0749 for recent weeks. |
| 7 | Sea-ice concentration | OSI SAF / NSIDC CDR concentration | Needed for the September-presence eval and for retention endpoints. Choose one, record which. |
| 8 | Weather forcing | ERA5 2 m temperature (CDS) and CARRA2 (2.5 km, CDS) | Compute freezing degree days. Known issue: ERA5 has a warm bias over sea ice in cold conditions (Wang et al., 2019); record this in the limits card. |
| 9 | Model cross-check | PIOMAS daily thickness, snow depth, ice growth rate (psc.apl.uw.edu) | Model, not observation; use for sanity checks and growth-rate comparison. |
| 10 | Bathymetry | IBCAO v5.1 (GEBCO), 100/200/400 m GeoTIFF | The 100 m grid is 12.6 GB. Use the 400 m grid (about 1 GB) or a subset. Used for the >20 m water criterion at Cambridge Bay-like sites. |
| 11 | Exclusions | Settlements (Natural Earth populated places), protected areas (WDPA/Protected Planet or Natural Earth), shipping corridors | Arctic Ship Traffic Data (ASTD) is application/fee based, not open. Use hand-drawn corridors (Northwest Passage, Northern Sea Route) clearly labelled as hand-curated and approximate. |

Known data limits (put these in the Limits section and the layer cards):
- All satellite thickness products are winter-only; October-November thin-ice retrievals and melt-affected months are biased. "Start-of-winter thickness" is therefore the weakest input.
- Radar altimetry thickness depends on assumed snow depth and density. Products disagree; use the spread as uncertainty.
- 25 km cells vs a 1 km field site: scale mismatch.
- Real Ice field evidence is one site, one to three winters.
- Indigenous use areas and wildlife (ringed seal) habitat are not in the open data. The atlas must say so on screen.

---

## 5. The calculation

Grid: 25 km EASE2 north grid (about 22,000 ice-capable cells). All steps vectorised with xarray/numpy. Everything is an ensemble; never a single number.

Notation per cell c and winter y: h0 start-of-winter thickness, G flooding gain, hs survival thickness, R retention probability.

1. **Start thickness ensemble h0(c,y).** Regrid products A-D to the 25 km grid. Members = each product, plus noise drawn from its stated uncertainty. Spread across products is reported as the cell's thickness uncertainty. Use the first reliable weeks of the winter season; record which dates.
2. **Thermodynamic growth.** Freezing degree days FDD = integral of (T_freeze - T_air) dt from ERA5/CARRA2, with T_freeze about -1.8 C. Baseline Stefan growth: h_f^2 = h_0^2 + (2 k_i / (rho_i L_f)) * FDD, with textbook constants (k_i about 2 W/m/K, rho_i about 917 kg/m3, L_f about 3.34e5 J/kg; verify and log in ASSUMPTIONS.md). Snow insulation is handled with a single reduction factor per cell using ERA5 snowfall or PIOMAS snow depth. Introduce one calibration scale alpha so modelled growth for the Cambridge Bay control vs flooded areas matches the 2024/25 paper.
3. **Flooding gain G.** Flooding removes snow insulation and adds snow-ice. Prior: G distribution centred on the paper's up-to-32 cm, with an upper scenario of 70 cm (Real Ice scale model), lower bound 0. Scale G for each cell by (FDD_cell / FDD_CambridgeBay_2024/25) to extrapolate. Hard guard: do not apply thickening where h0 < 0.6 m (van Dijke 2022). Optionally a second flooding event (paper: twice flooded thickened more) as a scenario toggle.
4. **Survival thickness hs(c).** Thickness needed to survive the melt season: hs = melt_rate * melt_days. Prior from van Dijke (2022): decay about 2.1-2.7 cm/day (Beaufort) and 0.8-1.4 cm/day (Transpolar Drift) over 91 melt days, giving about 2.18 m and 1 m (Ocean Visions quotes ranges 1.91-2.46 m and 0.73-1.27 m). Interpolate between the two regimes using local ice age and drift character; make melt-season length a per-cell input (derive from ERA5 days above 0 C). Show this as the weakest assumption.
5. **Retention R(c,y) by Lagrangian tracking.** Seed particles in each cell at start of winter. Advect them with OSI SAF drift day by day to 15 September. R = fraction ending in cells with ice concentration at or above 15%. This replaces regional constants such as "5 years in the Beaufort Sea, 1-2 years in the Transpolar Drift". Run over many past years to get a distribution of R, not one value.
6. **Survival probabilities.** With a Monte Carlo of N=1,000 draws over h0, hs, G, melt days:
   - P_without = P( (h0 + natural growth) >= hs ) * R
   - P_with = P( (h0 + natural growth + G) >= hs ) * R, with G = 0 where the 0.6 m guard blocks it
   - **Uplift U = P_with - P_without.** This is what the map shows.
7. **Band classification (what the map colours).**
   - SURVIVES ANYWAY: P_without high.
   - BAND: U above a threshold (default 0.2, user slider).
   - HOPELESS: P_with low.
   - BLOCKED: failed the 0.6 m guard.
   - EXCLUDED: inside an exclusion buffer (settlement, protected area, shipping corridor), shown as amber hatch on top of the above.
8. **Real Ice scale check.** Sum area of BAND cells in km². Compare with their 1,000,000 km² per year target and 5% of ice area. Report: area available, energy at 8 MWh per km², and fleet size for a user-set drone throughput over the January-March ice-safe window. Drone throughput is NOT public; make it an explicit slider labelled ASSUMPTION. Never show a fleet number without its assumption label.
9. **Sensitivity.** Run a global sensitivity analysis (SALib Sobol or a simple one-at-a-time tornado) on the BAND area. Show a ranked bar panel: WHAT MOVES THE ANSWER. Expect survival thickness, start thickness and gain to dominate; report whatever the data says.
10. **Winter selector.** Let the user pick a winter (2018-2025 where thickness data exists) and compare the band year to year. Mark 2026/27 as "current season, partial data".

Outputs: compressed per-year grids (`web/public/data/atlas-YYYY.bin` or JSON, target under 10 MB total), a `summary.json` of headline numbers, and `PROVENANCE.json`.

---

## 6. Evaluation (write first, tune later)

Never tune before these exist. Record everything in `RESULTS.md`.

1. **Hand-labelled set (`eval/labels.csv`, 25 rows).** Ravjoth labels, from published literature only, 25 places/regions as ONE of: likely-survives-anyway, marginal, likely-melts-out, export zone. Examples to start from: central Arctic multiyear ice remnant north of Greenland/Canadian Archipelago; Fram Strait export region; Beaufort Gyre interior; Laptev and East Siberian shelf seas; Hudson Bay/Baffin seasonal ice; Cambridge Bay area. Keep sources in a column. A model must not generate these labels.
2. **Calibration check.** Reproduce the Cambridge Bay 2024/25 result: flooded minus control thickness near 32 cm by mid-May within the stated range; control-area growth in line with PIOMAS and the site's historical thickness record at the 25 km scale. Report the gap honestly even if large.
3. **Observed-variability hindcast.** For each cell, compute how often ice is present in the following September over 2012-2025 (from sea-ice concentration). The model's BAND should overlap cells whose September presence flips between years (say 20-80% frequency). Report Spearman correlation of modelled P_without against observed September presence, and the overlap fraction of BAND cells with the marginal-frequency cells. Compare against two naive baselines: (a) "thin ice = at risk" using start thickness only, (b) distance from the September ice edge.
4. **Physics unit tests.** Growth is monotonic in FDD; flooding never applied below 0.6 m; uplift is zero where P_without is already about 1; band area shrinks when survival thickness rises; retention is between 0 and 1.
5. **Data-disagreement report.** For each thickness pair, a map and a number for where products disagree most. Show this in the UI as a layer.

Pass bar: the pipeline must beat both naive baselines on test 3, or the README says plainly that it does not and by how much.

---

## 7. Stack and repo layout

- Pipeline: Python 3.11+. xarray, netCDF4, numpy, scipy, pyproj, rasterio, SALib, requests, tqdm, pytest. A single `make` entry point per phase.
- Front end: static site, no server. Vite + TypeScript (or plain ES modules). d3-geo for projection; render the cell grid on canvas (ImageData with a colormap); SVG overlay for markers/labels. No heavy map framework needed. Fonts via system fallbacks; optional self-hosted JetBrains Mono and Inter.
- Deploy: static bundle. Also produce a single self-contained `index.html` (inline data) so it can be published as an artifact or opened locally.

```
.
├─ CLAUDE.md                # this file
├─ ASSUMPTIONS.md  RESULTS.md  README.md
├─ data/
│  ├─ raw/                  # cached downloads (git-ignored)
│  ├─ interim/              # regridded 25 km grids
│  └─ PROVENANCE.json
├─ pipeline/
│  ├─ fetch/                # one module per dataset, rate-limited, cached
│  ├─ grid.py               # EASE2 25 km grid, masks
│  ├─ thickness.py          # ensemble h0
│  ├─ growth.py             # FDD + Stefan + calibration
│  ├─ retention.py          # Lagrangian advection
│  ├─ survival.py           # Monte Carlo, uplift, bands
│  ├─ scale.py              # area, energy, fleet
│  ├─ sensitivity.py
│  └─ export.py             # to web/public/data
├─ eval/
│  ├─ labels.csv
│  ├─ hindcast.py
│  └─ tests/
├─ web/                     # instrument + page
│  ├─ src/  public/data/
└─ cli/                     # `atlas` command (optional face of the same backend)
```

Optional CLI (one backend, three faces: map, page, CLI): `atlas cell 72.5N -105E`, `atlas band --winter 2024 --threshold 0.2`, `atlas scale --km2 1000000`. Keep it thin.

---

## 8. Ethics and data rules (hard stops)

- Public data only; nothing behind a login except the free data accounts named above, used as the providers intend.
- Do not scrape realice.eco or partner sites beyond the pages already cited. No headless-browser evasion, rotating agents or proxies.
- Credit every dataset and author on screen and in PROVENANCE.json. Highlight the Petty et al. dataset authors.
- Label the project exploratory. It never recommends a deployment site. Indigenous-use areas and wildlife habitat are shown as "not in open data: community consent required", never ranked as targets.
- Do not claim the thickening works, or that it does not. Show uncertainty and limits.
- Do not fabricate anything: no placeholder stats left in the shipped UI (the Baltic page shipped with empty "—" tiles; do not repeat that). If a tile has no data, remove the tile.
- If you find a security flaw in any site, report it privately; never in the demo.

---

## 9. What the user must see (demo script, 25 seconds)

1. Boot line, instrument appears, polar map of this winter's thickness (1.5 s).
2. Toggle SURVIVAL GAP: cells collapse into three tones and the mint band lights up (4 s).
3. Switch winter 2019 to 2024: the band moves (4 s).
4. Click Cambridge Bay: side card shows calibration vs the paper (4 s).
5. Open SCALE: Real Ice's 1M km² line against the band area, energy and fleet with the assumption label (5 s).
6. Open WHAT MOVES THE ANSWER and the Limits card (4 s). End on the attribution line.

Record at 1440 px, no voiceover needed, captions in mono.

---

## 10. Phases and exit tests

Create tasks for each. Commit at the end of every phase.

- **P0 Setup.** Repo, env, Makefile, `.gitignore` (raw data, .env), README stub, ASSUMPTIONS/RESULTS stubs. Exit: `make test` runs and passes an empty suite.
- **P1 Evaluation first.** `eval/labels.csv` (25 rows with sources, ask Ravjoth to confirm labels), test skeletons, hindcast script design. Exit: tests exist and fail meaningfully.
- **P2 Fetch and grid.** Fetch modules for datasets 1-8 and 10 (ask before >1 GB). EASE2 25 km grid and masks. `PROVENANCE.json` populated. Exit: each dataset has a cached subset and a plotted sanity map saved to `eval/figs/`.
- **P3 Thickness ensemble.** Regrid products A-D, build ensemble and disagreement layer. Exit: disagreement map generated; numbers logged in RESULTS.md.
- **P4 Growth and calibration.** FDD, Stefan growth, alpha calibration against Cambridge Bay. Exit: calibration test reports modelled vs paper (32 cm); gap logged.
- **P5 Retention.** Lagrangian tracking with OSI SAF drift. Exit: retention map; Fram Strait export region shows low R; unit tests pass.
- **P6 Survival, uplift, bands, scale, sensitivity.** Exit: hindcast beats both baselines, or RESULTS.md says it does not. Band area and 1M km² comparison computed.
- **P7 Export.** Compressed grids and `summary.json` under the size target. Exit: web loads data in under 2 s on a laptop.
- **P8 Instrument UI.** Dark map, panels, signal guide cards, winter selector, scale panel, sensitivity panel, boot sequence. Exit: screenshots at 1440 and 390 px; every layer has its four-line card; no empty tiles.
- **P9 Page.** Editorial wrapper (hero, instrument, Method, Evidence, Limits, Spec, footer). Exit: squint test passes (eye goes to the map, then the statement); one accent per surface; attribution line present.
- **P10 Demo and outreach pack.** 25 s screen recording, short README, the message drafts below with real numbers filled in. Exit: Ravjoth reviews everything before anything is sent.

If time runs out: stop after P6 + a plain export. That is still a result worth sending.

---

## 11. Outreach (do not send anything; draft only)

Rules (from the build-for-company playbook): private first, always. Two co-CEOs, so ONE message to both, never two parallel pitches. No ask in the first message. Link and video at the top. Five lines or fewer. Then wait a week. One follow-up with new information, ending with a soft close. Then go public 10-14 days after the first message with Ravjoth's own build and Real Ice credited, native video, no tag after an unanswered message.

Channels: the Real Ice contact form (https://www.realice.eco/contact) and LinkedIn messages to Andrea Ceccolini and Cían Sherwin, same text. No guessed emails. Optional second route: replying to a Real Ice LinkedIn update with a link.

Draft 1 (fill the brackets from RESULTS.md only; remove any line with no number):

> Andrea, Cían, sending this to you both.
>
> Your scale plan is 1M km² a year, with drones choosing the sites. I built an open map of where thickening changes whether ice survives: [link] (25 s video).
>
> Calibrated to your Cambridge Bay paper. Beats a thin-ice baseline by [X] on a 2012-2025 hindcast. Every layer shows its weakness.
>
> Ravjoth, ravjothbrar.com

Draft 2 (follow-up after a week, new information only): one new finding from building, for example what moved the band most in the sensitivity panel, or the winter where the band shrank. End: "That's me done pinging you." No ask.

Draft 3 (public post, 10-14 days out): "I built an open map of where Arctic ice thickening could matter. What I learned: [one finding]. Data from [credits]. Credit to Real Ice for the public work it builds on." Native video, no tagging.

Expectation to hold: most unsolicited builds get no reply and that is not a verdict. The returns are the capability, the portfolio piece, and the fact that the same artifact can be re-aimed at other groups working on Arctic or climate-repair problems. Ravjoth may add one line about being available for the summer; the playbook advises against, so decide deliberately.

---

## 12. Things I could not verify (resolve or flag during the build)

- Exact coordinates of the Cambridge Bay test site (not public). Use the hamlet plus about 7 km as an approximation and say so; do not guess further.
- Whether Real Ice or RASi already have an internal siting analysis.
- Nome 2023 field data availability (none found). Do not use Nome as a calibration point unless public data appears; use it only as a qualitative sanity cell.
- Whether the van Dijke survival-thickness thresholds generalise beyond the Beaufort/Transpolar regimes they were built for.
- ASTD shipping access; the shipping layer is hand-curated and approximate.
- Whether the 2025/26 season results are published beyond news reports; do not quote numbers from the 2026 season other than as "reported by Mongabay, July 2026".
- Exact licence terms for each dataset: read and log them in PROVENANCE.json before publishing.

---

## 13. Final checklist before Ravjoth sends anything

- [ ] README states what it is, what it is not, and the pass/fail of the hindcast.
- [ ] Every layer has its four-line card; every number has source and date.
- [ ] Attribution line and dataset credits visible; "Independent project built for Real Ice. Not affiliated."
- [ ] No placeholder or invented data anywhere.
- [ ] Indigenous-use and wildlife caveat visible on the map.
- [ ] Screenshots at 1440 and 390 px; demo video recorded.
- [ ] Message drafts have real numbers from RESULTS.md only.
- [ ] Ravjoth has read and approved every outgoing message.
