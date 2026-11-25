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
