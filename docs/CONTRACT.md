# Internal data contract

All gridded intermediates live in `data/interim/` as NetCDF on the grid in `pipeline/grid.py`
(EASE2-N 25 km, 360 x 360, dims `(y, x)` with `y` = row i from top, `x` = column j from left;
store `lat`/`lon` 2-D coords too). float32, NaN = no data. Winter label `W` = the year the winter
STARTS (winter 2024 = Nov 2024 - Apr 2025, survival judged at Sep 2025).

| File | Vars | Owner |
|---|---|---|
| `thick_cpom_W.nc` | `h0` (m, mean of first reliable month, see attrs), `h0_unc` (m, product uncertainty), `h_apr` (m, April thickness for growth check) | thickness |
| `thick_petty_W.nc` | `h0`, `h0_unc`, `h_apr` (W = 2018..2024) | thickness |
| `thick_awi_W.nc` | `h0`, `h0_unc` (whatever winters are reachable, must include 2026 partial) | thickness |
| `thick_disagreement.nc` | per pair abs diff of `h0`, mean over common winters | thickness |
| `sic_sept.nc` | `sic_sept` (year, y, x): September mean concentration 0-1, years 2011..2025 | motion |
| `sept_presence.nc` | `freq` (y, x): fraction of years 2012..2025 with Sept SIC >= 0.15 | motion |
| `retention_W.nc` | `R` (y, x) fraction of particles seeded 1 Nov of W that sit in SIC >= 0.15 on 15 Sep W+1; `R_n` particles | motion |
| `climate_W.nc` | `fdd` (K day, 1 Nov W -> 15 May W+1, T_f = -1.8 C), `melt_days` (days T2m > 0 C, 1 May - 15 Sep W+1), `snowfall` (m w.e., 1 Nov -> 30 Apr) | climate |
| `static.nc` | `land` (0/1), `depth` (m, positive down), `excl_settlement`, `excl_protected`, `excl_shipping` (0/1, buffers in attrs), `region` (int code) | climate |
| `piomas_W.nc` | `h_nov`, `h_apr`, `snow_apr` cross-check fields | climate |

Point series (CSV under `data/interim/`):
- `cambridge_bay_climate.csv`: winter, fdd, melt_days, snowfall for the point 69.07N, -105.05E + ~7 km offshore (site approximate; exact coordinates not public).

Provenance: each fetcher calls `pipeline.http.record(name, dataset=, url=, doi=, licence=, files=[{name, sha256, bytes}], notes=)`.
Sanity plots: `eval/figs/<name>.png` (polar view, colourbar, title with source + date).

## Web export (owner: lead; consumed by web/)
`web/public/data/`:
- `manifest.json`: grid info, `n_cells`, `winters` list with `{w, label, partial}`, `layers` dict
  `{name: {scale, offset, unit, title}}` (value = byte * scale + offset; byte 255 = no data), sources, built date.
- `cells.bin`: Uint16 little-endian pairs (i, j) for the N ice-capable cells.
- `static.bin`: Uint8 layers in manifest.static_layers order, each N bytes.
- `winter-W.bin`: Uint8 layers in manifest.winter_layers order, each N bytes.
- `summary.json`: headline numbers, calibration, hindcast scores, sensitivity tornado, scale inputs, signal-guide cards.
- `land.json`: Natural Earth 50m land, clipped north of 45N, GeoJSON (lon/lat).
