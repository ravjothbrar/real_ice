# Assumptions

Every guess, constant and threshold, with where it came from. Newest at the bottom of each section.

## Grid
- EASE-Grid 2.0 North 25 km (EPSG:6931), central 360x360 block (+/-4,500 km). Equal-area: 625 km2 per cell. (NSIDC EASE2 spec.)

## Environment
- Data hosts reached through an allow-listed proxy. No Copernicus CDS key, no NASA Earthdata login used (decision 25 Nov 2026): ERA5 read from Google's public ARCO-ERA5 copy; NSIDC ice age dropped for v1.
- DTU multi-altimeter thickness (1.7 GB) skipped by owner decision, 25 Nov 2026.

## Evaluation labels (eval/labels.csv)
- 25 places labelled by Claude (at Ravjoth's request, 25 Nov 2026) from published literature, before any model output existed. Citations written from memory: column `verified` = `citation-from-memory` until Ravjoth checks each one. The labels are not produced by the atlas model, so they are independent of it, but they are not expert-labelled.
- Mapping used in evaluation: likely-survives-anyway -> expect high P_without; marginal -> expect BAND or mid P_without; likely-melts-out -> expect low P_without; export-zone -> expect low retention R.

## Physics constants (pipeline/physics.py)
- k_i = 2.0 W/m/K, rho_i = 917 kg/m3, L_f = 3.34e5 J/kg (brief; textbook). T_f = -1.8 C.
- Snow: k_s = 0.30 W/m/K (Sturm et al. 2002), rho_s = 330 kg/m3 (Warren et al. 1999). Season-mean snow depth = half the total winter snowfall converted at rho_s; wind loss to leads ignored, so insulation is overestimated where snowfall is high.
- Growth law: Stefan with snow layer, (h + r s)^2 = (h0 + r s)^2 + alpha a FDD, r = k_i/k_s (Leppäranta 1993 form). alpha calibrated at Cambridge Bay (P4).
- Melt regime weight: linear in latitude 75N (Beaufort-type, 2.1-2.7 cm/day) -> 85N (Transpolar-type, 0.8-1.4 cm/day), van Dijke et al. (2022). This proxies ice age / drift character because NSIDC ice age is not used. Weakest assumption.

## Survival Monte Carlo (pipeline/survival.py)
- N = 1,000 draws per cell. Common random numbers for with/without so uplift >= 0 per draw.
- Flooding gain G ~ triangular(0, 0.32, 0.70) m (paper up-to-32 cm as mode; Real Ice scale model 70 cm as max), scaled by FDD_cell / FDD_CambridgeBay(2024/25).
- Guard: G = 0 in any draw whose start thickness < 0.6 m (van Dijke et al. 2022). A cell is BLOCKED when >= 50% of its draws are below the guard and it does not survive anyway.
- Class thresholds (fixed before evaluation): SURVIVES ANYWAY P_without >= 0.7; HOPELESS P_with <= 0.2; BAND uplift >= 0.2 (slider).
- FDD uncertainty 8% (1 sd); snow insulation multiplied by U(0.5, 1.5).
- Forecast mode: each winter uses only start-of-winter thickness plus climatological FDD, melt days, snowfall and retention (all years; leave-one-out in the hindcast). Weather of the winter itself is not used, so the hindcast is a fair forecast test against baselines that also use only start-of-winter information.
- Second-flooding scenario: not implemented. The paper reports twice-flooded areas thickened more but no number we can use without inventing one.

## Scale (pipeline/scale.py)
- 1,000,000 km2/yr target, 8 MWh/km2, ~$6bn/yr at scale: Ocean Visions roadmap page. Ice-safe window 90 days (January-March, ARIA PDF). Drone throughput is not public: a user slider labelled ASSUMPTION.

## Thickness
- h0 (start-of-winter thickness) = November mean of winter W; h_apr = April mean of W+1. October not used (thin-ice retrievals biased thin, brief section 4). Stored in each file's `h0_choice` attr.
- CPOM: the brief's EOCIS URL (www.cpom.ucl.ac.uk/eocis/...) is 404; used the CPOM sea-ice portal NTC monthly CryoSat-2 product (5 km sparse points, EPSG:3411, v001, Warren-99 snow halved on FYI), https://www.cpom.ucl.ac.uk/seaice/download.php?region=Arctic. Regrid: bin mean of 5 km points per 25 km cell, cells with < 3 points dropped. No licence stated on the portal or in the files: confirm with CPOM before redistribution.
- CPOM has no retrieval-uncertainty variable: `h0_unc` = mean of `thk_stdev` (spread of measurements per 5 km point), a variability proxy that excludes systematic snow error.
- Petty IS2SMGPSIT-V1 (CC-BY-4.0): h0 uses `ice_volume_per_grid_cell_area` (= cell-mean ice_thickness / SIC, masked SIC < 0.15), i.e. ice-only thickness comparable with CPOM, not the cell-mean `ice_thickness`. `h0_unc` = GP s.d. scaled by 1/SIC. Read via HTTP Range, every 3rd day (days 1,4,...,28) to stay under the 1 GB rule; monthly mean = mean of those days (NaN if < 50% valid). Nearest neighbour EPSG:3411 25 km -> EASE2 25 km.
- QC (both products): negative 25 km means clipped to 0; means > 8 m set NaN as coast/land artefacts (counts in `qc_*` attrs; CPOM 0-5 cells per month).
- AWI CS2SMOS not fetched: ftp.awi.de resets TLS on 443 (FTP-only server), the proxy carries HTTPS only, spaces.awi.de is refused (403), ESA route needs EO Sign-In on smos-diss.eo.esa.int (not allow-listed). Substitute for the current season: thick_cpom_2026.nc from CPOM's NRT 14-day product (2-15 Nov 2026; initial orbits, not final quality; attr partial=1; h_apr all NaN). Being 14 days, it has CryoSat-2 orbit gaps (~9,300 valid cells vs ~11,000-12,000 for a full November).
- DTU thickness skipped by owner decision.
