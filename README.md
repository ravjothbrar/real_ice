# Survival Gap Atlas

**Where would winter ice thickening change whether Arctic sea ice survives the summer?**

An open, explainable map. It fuses satellite thickness (CryoSat-2, ICESat-2/SMOS), OSI SAF ice drift and concentration, and ERA5 weather, then runs a 1,000-draw Monte Carlo on every 25 km cell. Each cell lands in a band between "survives anyway" and "hopeless". Every layer carries a four-line card: meaning, why it matters, what it is not proof of, and one real number.

Created by [Ravjoth Brar](https://ravjothbrar.com). It is exploratory, never a deployment recommendation, and it does not claim that thickening works or that it doesn't.

Live: https://ravjothbrar.github.io/real_ice/

## What it found (winter 2024/25; numbers from RESULTS.md)
- **The band is small.** 11,250 km² of cells gain at least 0.2 in survival probability from a flooding gain like Cambridge Bay's. That is 1.1% of Real Ice's 1,000,000 km²/yr plan. Across 2011–2025 the band peaks at 36,250 km² (2018/19).
- **Start thickness and the flooding gain decide it.** In the one-at-a-time sensitivity, +0.2 m of start thickness moves the band from 11,250 to 70,000 km². A gain 1.5 times the prior moves it to 48,750 km².
- **Calibration:** with textbook constants, the growth model gives 25.8 cm flooded-minus-control at Cambridge Bay in 2024/25, against the paper's "up to 32 cm". No value of the scale factor reaches 32 cm.

## Hindcast: does not pass
Pre-registered test (CLAUDE.md §6.3): predict ice presence the next September, 2012–2025, cell by cell.

| | Atlas P(survive without) | Thin ice = at risk | Distance to Sept ice edge |
|---|---|---|---|
| AUC (cell-years) | 0.843 | 0.862 | 0.918 |
| Spearman vs presence frequency | 0.701 | 0.889 | 0.917 |

**The atlas does not beat either naive baseline.** It trails thin ice by 0.019 AUC (95% CI of the difference −0.051 to +0.015) and ice-edge distance by 0.075 (−0.105 to −0.038).

A post-hoc diagnosis was run after the result above and is not a pre-registered claim. The growth-only part of the model scores AUC 0.931, which beats both baselines. Multiplying by drift retention pulls it down, because retention scores whether a cell's ice stays in the Arctic, not whether the cell has ice in September. A climatology of past Septembers scores 0.956, better than every model here.

## What it is not
- Not a siting tool. No ecology, no logistics, no community input. Indigenous use areas and ringed seal habitat are not in open data, and the map says so on screen.
- Not new science. It is an open explainer of public data and published priors, with its weaknesses shown.
- Not observations of thickened ice. The gain prior comes from one 1 km site over one winter, extrapolated by cold.

## Run it
```
make setup      # python deps
make test       # unit, physics, data tests
python -m pipeline.thickness && python -m pipeline.retention && python -m pipeline.climate   # fetch + regrid (cached)
python -m pipeline.growth       # calibration
python -m eval.hindcast 400     # hindcast vs baselines
python -m eval.diagnose         # component diagnosis
python -m pipeline.sensitivity 2024
python -m pipeline.provenance && python -m pipeline.export
cd web && npm ci && npm run dev # http://localhost:5173
npm run build:single            # one self-contained index.html
python cli/atlas.py band --winter 2024 --threshold 0.2
```

## Data (credits and licences in data/PROVENANCE.json)
- **IS2SMGPSIT-V1 daily 25 km ICESat-2 + SMOS/SMAP thickness**: Petty, Cardinale, Tsamados, Gregory, Cabaj. doi:10.5281/zenodo.22147361 (CC-BY-4.0).
- CPOM CryoSat-2 sea-ice thickness, UCL (licence not stated by the provider; check before reuse).
- OSI SAF sea-ice concentration (OSI-450-a/430-a/438) and drift (OSI-455/435/405), EUMETSAT. Copyright EUMETSAT.
- ERA5 via Google ARCO-ERA5 (Copernicus Climate Change Service). PIOMAS v2.1 (UW APL). Natural Earth. GEBCO_2026.
- Field result: Real Ice et al. (2026), *Earth's Future*, doi:10.1029/2025EF007894. Scale numbers: Ocean Visions roadmap.

Records: `ASSUMPTIONS.md` (every constant and choice), `RESULTS.md` (every number and the command behind it), `docs/CONTRACT.md` (data format), `OUTREACH.md` (drafts, unsent).

## Hosting
GitHub Pages via `.github/workflows/pages.yml`. On every push to `main` that touches `web/`, it builds `web/` and deploys `web/dist`. The exported data in `web/public/data/` is committed, so Pages needs no Python.
