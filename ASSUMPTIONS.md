# Assumptions

Every guess, constant and threshold, with where it came from. Newest at the bottom of each section.

## Grid
- EASE-Grid 2.0 North 25 km (EPSG:6931), central 360x360 block (+/-4,500 km). Equal-area: 625 km2 per cell. (NSIDC EASE2 spec.)

## Environment
- Data hosts reached through an allow-listed proxy. No Copernicus CDS key, no NASA Earthdata login used (decision 25 Nov 2026): ERA5 read from Google's public ARCO-ERA5 copy; NSIDC ice age dropped for v1.
- DTU multi-altimeter thickness (1.7 GB) skipped by owner decision, 25 Nov 2026.
