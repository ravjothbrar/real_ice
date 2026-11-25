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

## Retention and concentration
- SIC source (EUMETSAT OSI SAF, MET Norway THREDDS, OPeNDAP subsets, CC BY 4.0): OSI-450-a1 CDR v3.1 (DOI 10.15770/EUM_SAF_OSI_0023) to 2020-12; OSI-430-a ICDR v3.0 2021-01..2025-09 (production stopped 2025-09-30); OSI-438 ICDR v3.0 (AMSR2) from 2025-10. All on the full EASE2-N 25 km grid (432x432, xc[0] = -5387.5 km); our grid is cells [36:396] exactly (asserted on x/y values), so no resampling.
- September SIC = OSI SAF monthly mean files; Sep 2025 has no monthly file, so it is the mean of the 26 available OSI-430-a dailies (25-28 Sep missing). September presence = fraction of 2012-2025 with monthly-mean SIC >= 0.15.
- Daily gaps: retention endpoints use the nearest available day within +/-5 days (only case: 15 Sep 2024 -> 18 Sep 2024, OSI-430-a gap 12-17 Sep).
- Sensor switch: on 15 Sep 2025 OSI-430-a (SSMIS) gives 5.24 M km2 at SIC >= 0.15 and OSI-438 (AMSR2) 4.62 M km2 (agree on 87% of the union); the extra 430-a cells are mostly within 50 km of land (median SIC 0.29), i.e. coarse-footprint coastal spillover. Winter 2025 endpoints come from OSI-438, so R(2025) is not directly comparable with 2011-2024 near coasts. Coastal cells also show spurious "always present" September ice in sept_presence (isolated yellow coastal pixels).
- Drift: OSI-455 CDR v1.0 (DOI 10.15770/EUM_SAF_OSI_0012, EASE2 75 km, 24 h) to 2020-12-31; OSI-435 ICDR v0.1 "demonstrational" (same grid/algorithm) 2021-01..2025-12; OSI-405-d NRT v3.1 (62.5 km polar stereographic, 48 h) Jan-Sep 2026. Licence: OSI-455/435 EUMETSAT terms (free use, show "Copyright EUMETSAT"); OSI-405 CC BY 4.0.
- Summer drift: OSI-455/435 summers (May/Jun-Sep) are 100% wind-driven free-drift vectors (status flags 23-25) in JJA in every winter 2011-2024: summer motion is a model, not satellite tracking. OSI-405 (2026) does have summer vectors (~1,500 valid in July vs ~2,150 in January, ~760 in September) but no wind gap filling; 16-18 Aug 2026 files are missing (particles held still those days).
- OSI-405 handling: 48 h displacement halved for each daily step (file starting day d-1 used for step ending day d); start/end points transformed to EPSG:6931, gridded linearly onto the 75 km EASE2 grid, NaN > 80 km from any valid vector.
- Retention method: 4 particles per seed cell (2x2 stratified, jitter within each quadrant, RNG seed = W), seeded where SIC >= 0.15 on 1 Nov W 12 UTC; midpoint RK2, daily steps, bilinear interpolation of displacement on the native 75 km grid with weights renormalised over valid corners. Where no corner has a vector the particle is held still that day (choice: hold still rather than invent motion). Held particle-days: 35-40% of all, 28-32% of Nov-Apr in 2011-2024 (mostly CAA/landfast, coastal Siberian shelf, Hudson Bay and marginal seas where OSI SAF masks vectors near coasts/edges, plus open water after melt); 2025: 22% (gridded OSI-405 reaches further into coasts).
- Domain: drift crop +/-3600 km (75 km cells 24..119); particles leaving the +/-3562.5 km centre box are not retained. 7-38 seed cells per winter lie outside it (Hudson/James Bay south, Caspian): R = NaN, R_n = 0 there.
- R is endpoint-only (brief 5.5): SIC >= 0.15 in the particle's 25 km cell on 15 Sep W+1. With 4 particles moving nearly together, R per cell is close to binary in any one winter; use the multi-winter distribution.
- Politeness/volume: ~464 MB estimated DAP payload (ledger in data/raw/osisaf/_ledger.json; 103 MB cached compressed). Requests serial with >= 1 s between datasets (each netCDF-C OPeNDAP open issues DDS+DAS+data back to back). UA set through ~/.dodsrc (HTTP.USERAGENT).

## Climate and static layers
(pipeline/fetch/era5.py, pipeline/fetch/piomas.py, pipeline/fetch/static_layers.py, pipeline/climate.py; 25 Nov 2026)

### ERA5 route and sampling
- No CDS key. ERA5 read from Google's public ARCO-ERA5 copy (gs://gcp-public-data-arco-era5 via https://storage.googleapis.com). WeatherBench2 stores end on 10 Jan 2023, so they were not used. Every ARCO store holds one hour per chunk over the whole globe (0.25 deg chunk is about 2.3 MB). Reading those chunks directly would have cost tens of GB.
- Cheap route: the `co/` stores on the native N320 reduced Gaussian grid. Their points run north to south, so the 81,209 points north of 45N are the first 62% of the first 512 KB blosc block. Only the leading part of byte-streams 1-3 is fetched with HTTP Range requests, and the LZ4 prefix is decoded in pure Python. Byte 0, the lowest 8 mantissa bits, is set to its midpoint. Checked against a full decode: max error 0.0033 K for T2m and 3e-8 m for snowfall. One hourly field costs about 120 KB for T2m and about 100 KB for winter snowfall.
- T2m daily mean = mean of the 00 and 12 UTC analyses (12 h apart, so the first diurnal harmonic cancels) for 1 Nov-15 May. From 16 May to 15 Sep there is ONE analysis per day, alternating 00/12 UTC, to stay inside the budget. Winter 2024 (the paper winter) has both samples all year. This makes melt_days noisier than fdd. Check for Jun-Aug 2025, north of 70N, alternating single sample vs 2-sample mean: mean difference -0.6 days, mean absolute difference 1.8 days, 95th percentile 5 days (out of 92).
- Snowfall: the co forecast store holds 1-hour accumulations per step (checked: not cumulative). Daily snowfall = 24 x one hourly value. The valid hour rotates through all 24 hours, v = (7 + 5*ordinal) mod 24, so the seasonal sum has no diurnal bias. Check for Nov 2024 against 4 samples/day: domain-mean ratio 0.99-1.01 (unbiased). The per-point monthly ratio IQR is 0.73-1.24, so expect roughly +/-10% per point over a 6-month season.
- ERA5T (preliminary) is used after 30 Jun 2026. The co t2m store has no chunks for August 2026, although its attrs claim data to 31 Oct 2026. Those 31 hours were read from the 0.25 deg `ar/` store (rows 90-45N) and interpolated bilinearly to the native points. The co store ends 31 Oct 2026. Winter 2026 (partial): FDD from 1 to 17 Nov 2026 only, from the 0.25 deg `ar/` store (rows 90-45N, bilinear). melt_days and snowfall are NaN.
- Interpolation to the 25 km grid: linear in longitude along the two bracketing Gaussian rows, then linear in latitude. Cells south of the last row held (~45.1N) are NaN. Values are kept over land; mask them with static.land.
- Definitions: T_f = -1.8 C. fdd = sum of max(T_f - T_daily, 0) over 1 Nov W-15 May W+1. fdd_jan uses 1 Jan-15 May W+1 and fdd_mar uses 1 Jan-31 Mar W+1. melt_days = days with daily-mean T2m > 0 C, 1 May-15 Sep W+1 (max 138). snowfall = m water equivalent, 1 Nov W-30 Apr W+1.
- Known bias: ERA5 has a warm bias in 2 m temperature over Arctic sea ice in cold, clear conditions, up to several K (Wang et al. 2019, The Cryosphere 13, 1661-1679, doi:10.5194/tc-13-1661-2019; citation from memory, check). ERA5 FDD is therefore probably biased LOW over pack ice. The calibration alpha at Cambridge Bay partly absorbs this locally, but not regionally.
- The ~31 km ERA5 cells around Cambridge Bay mix land and sea. Over land, summer T2m runs warmer, which inflates melt_days at the coastal site.
- CARRA2 skipped for v1.

### Cambridge Bay point
- Hamlet 69.117N, 105.06W. Real Ice reports its site is about 7 km away over water deeper than 20 m. The exact coordinates are NOT public. 69.05N, 105.10W is used as the approximate site; it is an assumption, not a location.
- GEBCO_2026 at that point: median depth 9 m within 2 km. Only 1-11% of a 5-9 km ring around the hamlet is deeper than 20 m in GEBCO. Either GEBCO is coarse or poorly surveyed here, or the real site lies elsewhere around the bay. Do not use this point for the >20 m criterion.

### PIOMAS
- PIOMAS v2.1 monthly heff and snow, from pscfiles.apl.uw.edu/zhang/PIOMAS/data/v2.1/ (flat little-endian float32, 12 x 120 x 360 per year), with grid.dat for scalar points. It is MODEL output, not observation.
- Linear (Delaunay) regrid in EPSG:6931. Cells more than 60 km from any PIOMAS node are NaN.
- h_nov = Nov W, h_apr = Apr W+1, snow_apr = Apr W+1, for W = 2011-2024. heff.H2026 held only Jan-Feb 2026 when accessed, so W = 2025 is missing.
- The PSC table labels `snow` "snow depth (water equivalent)", and the values (~0.06 m at the pole in April) fit that label. The units were taken from the table, not verified further.

### Static layers (static.nc)
- land: Natural Earth 50m land, rasterised at 5 km (25 sub-cells per cell). A cell is land when its land fraction is > 0.5; land_frac is kept as well.
- depth: only the GEBCO_2026 15-arcsec subset for a Cambridge Bay box (106.5-103.5W, 68.6-69.6N) was fetched, through the GEBCO subsetting app's queue API. Depth = mean ocean depth of the GEBCO points in each cell, and is NaN everywhere else. A full 45-90N subset at 15 arcsec is about 1.9 GB, over the 1 GB rule. IBCAO 5.2 at 400 m is hosted on dap.ceda.ac.uk, which is not on the allowed-host list. Ravjoth needs to decide whether to fetch either.
- excl_settlement: Natural Earth 10m populated places with latitude > 55N, buffered by 50 km. Distances are taken in EASE2 metres (equal-area, so distance distortion is small).
- excl_protected: all zeros, "not available". No open, licence-clean pan-Arctic marine protected-area layer was reachable. Zeros do NOT mean there are no protected areas.
- excl_shipping: hand-curated, approximate centrelines for the Northwest Passage southern route (Bering Strait, Alaska coast, Amundsen Gulf, Dolphin and Union Strait, Coronation Gulf, Cambridge Bay, Queen Maud Gulf, Rae/James Ross Strait, Franklin Strait, Peel Sound, Barrow Strait, Lancaster Sound, Baffin Bay, Davis Strait) and for the Northern Sea Route (Murmansk approach, Kara Gate, Kara Sea, Dikson, Vilkitsky Strait, Laptev, Sannikov, East Siberian Sea, Pevek, Bering Strait). Buffer 50 km. Vertices are in data/hand_curated/shipping_corridors.geojson. Not ASTD.
- region: lon/lat boxes, applied in the order 3, 6, 7, 2, 1, 4, 5; the first match wins and land cells are 0:
  - 3 Canadian Archipelago: lon -125..-80, lat 66.5..82; plus Nares lon -80..-60, lat 78..82
  - 6 Baffin/Hudson/Labrador: lon -100..-45, lat 45..78
  - 7 Bering/Okhotsk: lon >= 135E or <= -157, lat 40..66.5
  - 2 Transpolar: lat >= 82 (all longitudes); plus lon 100..180, lat 68..82 (Laptev, East Siberian)
  - 1 Beaufort (incl. Chukchi): lon -180..-125, lat 66.5..82
  - 4 Barents-Kara: lon 15..100, lat 68..82; plus White Sea lon 32..45, lat 63..68
  - 5 Greenland/Fram: lon -45..15, lat 60..82
  - 0 other (Baltic, Gulf of Alaska, etc.)
- web/public/data/land.json: Natural Earth 50m land clipped to >= 45N, simplified with a 0.05 deg tolerance (topology preserved), coordinates rounded to 0.001 deg.
- Transfer: ERA5 about 1.38 GB in total (all runs and checks), single thread, identified UA, about 60k HTTP range requests. PIOMAS about 19 MB, Natural Earth about 3 MB, GEBCO 0.8 MB.
- Cambridge Bay, winters 2023 and 2024 are the two warmest in 2011-2025 (FDD about 3,850 K day against 4,380-4,740 for the others). The 2024/25 paper winter was therefore a warm winter for this site.

## Calibration and evaluation decisions (lead, 25 Nov 2026)
- Cambridge Bay two-stage model: ice on 1 Nov 0.10 m; 40% of winter snowfall before 1 Jan; flooding on 1 Jan converts the existing snow layer into an equal thickness of snow-ice (phi = 1) and that layer stops insulating; later snow still insulates. Result in RESULTS.md. alpha could not reach 32 cm, so it stays at 1.0 with sd 0.25.
- G is scaled by FDD_cell / 3,843 K day (ERA5 Cambridge Bay 2024/25 point).
- Pole hole: cells north of 86.5N without thickness take the median of 84.5-86.5N for that winter.
- Ice-capable cells: ocean cells with a November thickness retrieval in any winter or September ice in any year (17,736 cells).
- The hindcast ran once with all inputs before any change (run 1, data/interim/hindcast_run1.json). Changes after run 1: none to physics or thresholds. Added: strict-JSON export, a diagnosis script, alignment of sensitivity settings with the export (same seeds, alpha sd).
- Initial map view is the latest complete winter (2025/26). 2026/27 uses CPOM near-real-time thickness for 2-15 Nov 2026 only and is labelled partial.
