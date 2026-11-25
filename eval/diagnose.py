"""Component diagnosis for the hindcast: which part of P_without carries (or loses) skill?
    python -m eval.diagnose
"""
import json, numpy as np, pandas as pd
from scipy.stats import spearmanr
from pipeline import atlas as A
from eval.hindcast import auc, edge_distance, ROOT

at = A.Atlas()
land = at.static["land"] > 0.5
yidx = {int(y): k for k, y in enumerate(at.sept_years)}
rows = []
for w in at.winters:
    if w + 1 not in yidx or w + 1 > 2025 or w not in yidx:
        continue
    r = at.run(w, loo=True, n=300, seed=w)
    x = r["inputs"]
    sic = at.cells(at.sic_sept[yidx[w + 1]])
    ok = r["ok"] & np.isfinite(sic)
    Rm = np.nanmean(x["R_samples"], 1)
    rows.append(pd.DataFrame({"w": w, "y": (sic >= .15)[ok], "model": r["p_without"][ok],
        "thermo_margin": (r["h_end"] - x["hs"])[ok], "R_clim": Rm[ok], "thin": x["h0"][ok],
        "edge": at.cells(edge_distance(at.sic_sept[yidx[w]], land))[ok],
        "sept_clim_loo": np.nanmean(np.stack([at.cells(at.sic_sept[yidx[k]] >= .15) for k in range(2012, 2026) if k != w + 1 and k in yidx]), 0)[ok]}))
D = pd.concat(rows)
out = {c: round(auc(D[c], D.y), 3) for c in D.columns if c not in ("w", "y")}
out["share_thermo_margin_positive"] = round(float((D.thermo_margin > 0).mean()), 3)
print(json.dumps(out, indent=1))
(ROOT / "data" / "interim" / "diagnose.json").write_text(json.dumps(out, indent=1))
