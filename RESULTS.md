# Results

Every evaluation number, with the command that produced it.

## Thickness disagreement
Command: `python -m pipeline.thickness` (writes data/interim/thick_disagreement.nc; 25 Nov 2026).
Per cell, mean over common winters of |h0_a - h0_b| (h0 = November mean thickness); summary over cells with >= 1 common winter.

| Pair | Winters | Cells | Median abs diff | 90th pct | Mean signed diff (a - b) |
|---|---|---|---|---|---|
| CPOM - Petty | 2018-2024 (7) | 14,654 | 0.511 m | 0.879 m | +0.349 m (CPOM thicker) |
| CPOM - AWI | none: AWI unreachable | - | - | - | - |
| Petty - AWI | none: AWI unreachable | - | - | - | - |

Largest disagreement: north of Greenland / Canadian Archipelago coast and the Greenland Sea export edge (map: eval/figs/thick_disagreement_cpom_petty.png).

## Retention sanity
Command: `python -m pipeline.retention` (box = mean of R over seeded cells in the lat/lon box; seeded cells in box shown as n).

| Box | n cells | mean R 2011-2024 | min-max (winter) | 2025 (lower quality) |
|---|---|---|---|---|
| Fram Strait (78-81N, 10W-10E) | 214 | 0.018 | 0.000-0.182 | 0.00 |
| N Greenland / CAA (83-87N, 60-100W) | 278 | 0.924 | 0.599-0.972 | 0.66 |
| Beaufort (72-77N, 130-150W) | 535 | 0.378 | 0.000-0.704 | 0.01 |
| Laptev (73-78N, 110-135E) | 630 | 0.596 | 0.254-0.840 | 0.34 |

Per winter 2011..2025: Fram 0.03 0.00 0.02 0.01 0.18 0.00 0.00 0.00 0.01 0.00 0.00 0.00 0.00 0.00 0.00; N Greenland/CAA 0.89 0.94 0.97 0.94 0.97 0.60 0.96 0.96 0.94 0.95 0.96 0.95 0.94 0.95 0.66; Beaufort 0.00 0.02 0.47 0.52 0.61 0.01 0.55 0.57 0.17 0.70 0.11 0.57 0.56 0.41 0.01; Laptev 0.65 0.62 0.72 0.82 0.59 0.56 0.29 0.75 0.63 0.41 0.75 0.47 0.25 0.84 0.34.
Pan-Arctic mean R over seeded cells: 0.44-0.61 per winter. Fram low and N Greenland/CAA high as expected; Beaufort (72-77N box, southern gyre) varies 0-0.7 with the September edge (0 in 2011/12 and 2016/17), lower than "Beaufort Gyre interior high R" would suggest for this box; Laptev box is higher than an export-shelf expectation (northern half of the box keeps September ice; landfast cells are held still).
Sept presence (2012-2025): 3,910 cells with frequency in (0.2, 0.8); 5,218 cells always present. Figures: eval/figs/sept_presence.png, retention_winters.png (2012, 2019, 2023), retention_mean.png.

## Calibration at Cambridge Bay (eval test 2)
Command: `python -m pipeline.growth` (25 Nov 2026). Output: data/interim/calibration.json.
- ERA5 at approx. 69.05N 105.10W, winter 2024/25: FDD 3,843 K day (warmest winter of 2011-2025 at the point), snowfall 0.075 m w.e.
- Two-stage model, textbook constants (alpha = 1): control 1.55 m, flooded 1.81 m, **flooded minus control 25.8 cm vs paper's "up to 32 cm"; gap 6.2 cm (19%)**.
- alpha cannot be fitted to 32 cm: the difference rises with alpha but saturates (alpha 0.5: 23.1 cm; 1: 25.8 cm; 2: 28.1 cm; 5: 30.2 cm). alpha kept at 1.0, carried with sd 0.25.
- PIOMAS cross-check fails at this scale: PIOMAS does not resolve Dease Strait; nearest ice cells (25 km) give April thickness 0.23 m, not usable. The site's historical thickness record was not fetched. Control-thickness check therefore not done.

## Hindcast (eval test 3) — run 1, pre-registered, first full-data run, no parameter changed afterwards
Command: `python -m eval.hindcast 400` (25 Nov 2026). Output: data/interim/hindcast.json (copy: hindcast_run1.json).
Winters 2011-2024 (start thickness Nov W, presence Sept W+1, Septembers 2012-2025); 189,265 cell-years, 13,336 cells. Forecast mode, leave-one-out climatologies.

| Metric | Atlas P_without | (a) thin ice | (b) distance to Sept edge |
|---|---|---|---|
| AUC, presence next September (cell-years) | **0.843** | 0.862 | 0.918 |
| Spearman, per-cell mean vs presence frequency | **0.701** | 0.889 | 0.917 |
| Share of BAND cells that flip (20-80%) | **0.07** (15 cells) | 0.80 | 0.93 |

Bootstrap over winters (500), 95% CI of AUC difference: model - thin [-0.051, +0.015]; model - edge [-0.105, -0.038].
**Verdict: does not beat either baseline.** Behind thin-ice by 0.019 AUC (not significant) and ice-edge distance by 0.075 AUC (significant).

### Post-hoc diagnosis (after run 1; not a pre-registered claim)
Command: `python -m eval.diagnose`. AUC of each component on the same cell-years:
- growth-only margin (mid-May thickness - survival thickness): **0.931** (beats both baselines)
- climatological retention R alone: 0.786
- full model (growth x retention): 0.843
- reference not in the brief: climatology of other Septembers (leave-one-out): 0.956 (beats everything)
- share of cell-years with positive growth margin: 0.677

Reading: the thermodynamics carry skill; multiplying by Lagrangian retention lowers Eulerian skill because R scores whether the cell's ice stays in the Arctic, not whether the cell has ice in September. Kept the brief's definition for the map (thickened ice that drifts out is lost), and report both.

## Label check (eval test 1)
Same run. Mean P_without at the 25 labelled places: likely-survives-anyway 0.78 > marginal 0.65 > likely-melts-out 0.03. Mean R: export-zone 0.23 (lowest of the four classes alongside melts-out 0.39). Ordering matches the literature labels.

## Band area and Real Ice scale (brief 5.8)
Command: `python -m pipeline.export` (1,000 draws, alpha 1.0 +/- 0.25). Band = uplift >= 0.2.
Band area by winter (km2): 2011/12 14,375; 12/13 4,375; 13/14 2,500; 14/15 5,625; 15/16 7,500; 16/17 3,750; 17/18 25,000; 18/19 36,250; 19/20 31,250; 20/21 28,125; 21/22 27,500; 22/23 23,750; 23/24 17,500; **24/25 11,250**; 25/26 8,750; 26/27 (partial) 3,125.
2024/25: band 11,250 km2 = **1.1% of the 1,000,000 km2/yr target**; 8,750 km2 outside exclusion buffers. Energy for the band at 8 MWh/km2: 0.09 TWh (target: 8 TWh).
Largest band: 2018/19, 36,250 km2 (3.6% of target).

## Sensitivity (brief 5.9)
Command: `python -m pipeline.sensitivity 2024` (one-at-a-time, 1,000 draws, common random numbers). Base band 2024/25: 11,250 km2.

| Factor (low / high) | Band low | Band high |
|---|---|---|
| Start thickness (-0.2 / +0.2 m) | 3,125 | 70,000 |
| Flooding gain G (x0.5 / x1.5) | 0 | 48,750 |
| Uplift threshold (0.15 / 0.25) | 45,625 | 3,750 |
| Thin-ice guard (0.5 / 0.7 m) | 32,500 | 4,375 |
| Survival thickness (x0.8 / x1.2) | 5,625 | 21,250 |
| Retention (-0.15 / +0.15) | 5,625 | 11,875 |
| Snow insulation (x0.5 / x1.5) | 7,500 | 14,375 |
| FDD (x0.9 / x1.1) | 8,750 | 10,625 |

Start thickness and flooding gain move the answer most; even the most generous single change keeps the band under 7% of the target.
