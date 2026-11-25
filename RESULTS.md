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
