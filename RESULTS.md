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
