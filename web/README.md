# Survival Gap Atlas: web front end

Vite + TypeScript static site. There's no framework: d3-geo/d3-zoom for the map, canvas for the cells and SVG for land and markers. One page has two surfaces: a light editorial page and a dark instrument.

## Run

```
cd web
npm ci                      # exact versions from package-lock.json
npm run dev                 # http://localhost:5173/        reads data/ (= public/data from `make export`)
npm run fixture             # writes the SYNTHETIC fixture to dev/fixture-data/
                            # http://localhost:5173/?fixture=1  (dev server only)
npm run build               # dist/ with public/data copied in (GitHub Pages deploys this)
npm run build:single        # dist-single/index.html: JS, CSS and data inlined (.bin as base64)
NODE_PATH=$(npm root -g) node dev/screenshots.cjs [url] [suffix]   # screenshots + perf -> screenshots/
```

- **GitHub Pages** (`https://ravjothbrar.github.io/real_ice/`): `vite.config.ts` uses `base: './'`. Every fetch is relative (`data/manifest.json`), and no asset path starts with `/`. `.github/workflows/pages.yml` runs `npm ci && npm run build` in `web/` and deploys `web/dist`. Commit `package-lock.json` and `public/data/`.
- The fixture is **synthetic**: every value is invented. It is served only by the dev server (`import.meta.env.DEV`), and nothing under `dev/` reaches `dist/` or `dist-single/`.
- Empty states: with no data the instrument says "No data. Run make export." `build:single` exits with the same message.

## Data interface (`public/data/`, see docs/CONTRACT.md "Web export")

The UI reads the keys written by `pipeline/export.py` today. `src/normalize.ts` maps them to internal names. The canonical key, where it differs, is in brackets.

**manifest.json**
- `built`, `n_cells`, `grid.crop` (360), `grid.cell_area_km2` (625), `grid.epsg`/`grid.res` (for the spec label).
- `static_layers[]`, `winter_layers[]`: byte order in `static.bin` / `winter-W.bin`.
- `layers{name: {scale, offset, unit, title}}`, decoded as byte*scale+offset, where 255 means no data. Optional per layer: `source`, `date` (may use `{W}`/`{W1}`), `unc` (text), `unc_layer` (auto-set to `<name>_sd` when that layer exists), `flags` (bitmask labels).
- `winters[{w, label, partial, ice_km2?}]`. `ice_km2` drives the "5% of ice area" line unless `summary.scale.arctic_ice_area_km2` is given. Optional: `default_winter` (otherwise the last winter).
- Optional `sources[]`. Otherwise these are built from `summary.sources` (the PROVENANCE dict: `dataset, authors, doi, url, licence`).

**Layer names used**: `h0`, `h0_sd`, `spread` [`h0_spread`] (falls back to static `disagree`), `fdd`, `hs`, `R`, `R_sd`, `p_without`, `p_with`, `uplift`, `blocked` (a share of draws, compared with `thresholds.blocked_frac`; a 0/1 flag also works), `sept_freq` [`sept_presence`], `excluded` [`excl`] (bits: 1 settlement, 2 protected, 4 shipping). Each can be static or per winter. A per-winter layer that is all 255 counts as absent for that winter.

**summary.json**
- `thresholds{survives_p_without, hopeless_p_with, uplift, blocked_frac, guard_m}`. The client classifies with the same precedence as `pipeline/survival.py`: survives > blocked > band > hopeless > low uplift.
- `scale{target_km2, mwh_per_km2, window_days, share_of_ice_area, source, throughput_default_km2_per_drone_day}`, with optional `throughput_min/max` and `arctic_ice_area_km2`.
- `calibration{site, winter, uncalibrated.diff_m, calibrated.diff_m, alpha, paper_diff_m, paper}`.
- `hindcast{auc_cell_year, spearman_vs_presence, band_overlap_with_marginal, beats_both, winters, built, command}`. Each of the first three holds `model / baseline_thin_ice / baseline_edge_distance` (`model_band`, `*_same_k` for overlap).
- `sensitivity{winter, base_band_km2, method, factors[{label, band_km2_low, band_km2_high}]}`.
- `cards{key: {meaning, why, not_proof_of, example}}`. A layer is hidden if its card is missing. Keys: `h0, disagree, fdd, hs, R, gap, sept_freq, excluded, uplift, calibration, hindcast, sensitivity, scale`. Optional, used when present: `p_without`, `p_with` (otherwise `uplift` is used), `band_area`, `energy`, `fleet` (otherwise `scale` is used).
- Optional: `ensemble_n` (method and spec copy) and `limits[{title, body}]` (extra accordion items).

**Also:** `cells.bin` holds uint16 LE (i, j) pairs. `land.json` is GeoJSON lon/lat in either winding order.

## Notes
- Cell geometry: exact ellipsoidal EASE2-N inverse (`src/ease2.ts`). Corners are projected once and cached as Path2D, and zoom is a canvas transform.
- Data load plus first render: about 0.8 s with the fixture (dev and prod). The boot sequence (1 s, skippable, off with reduced motion) runs in parallel.
- Markers are real settlement and strait positions. The Cambridge Bay test site is not drawn, because its coordinates are not public.
