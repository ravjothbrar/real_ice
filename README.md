# Survival Gap Atlas

Where would winter ice thickening change whether Arctic sea ice survives the summer?

An open, explainable map that fuses satellite thickness, ice drift, concentration and reanalysis
weather, runs a per-cell ensemble, and shows the band between "survives anyway" and "hopeless".

*Independent project built for Real Ice. Not affiliated.* Exploratory; never a deployment recommendation.

Status: under construction. See `CLAUDE.md` for the brief, `ASSUMPTIONS.md` and `RESULTS.md` for the record.

```
make setup   # python deps
make test    # unit + physics tests
make all     # pipeline end to end (needs cached data in data/raw)
```

## Hosting (GitHub Pages)

The site is static. `.github/workflows/pages.yml` builds `web/` and deploys `web/dist` on every push to `main` that touches `web/`
(or run it by hand from the Actions tab). Live URL once enabled: https://ravjothbrar.github.io/real_ice/

One-time setup: repo **Settings → Pages → Source: GitHub Actions**. The exported data in `web/public/data/` is committed,
so Pages needs no Python. To refresh it: `make all`, commit `web/public/data`, push.
