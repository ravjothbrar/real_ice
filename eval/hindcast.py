"""Observed-variability hindcast (brief section 6, test 3), plus label check (test 1).

For every winter w with start thickness and an observed September w+1:
  model score    = P_without (forecast mode, leave-one-out climatologies)
  baseline (a)   = start-of-winter thickness h0           ("thin ice = at risk")
  baseline (b)   = signed distance to the September-w ice edge (positive inside the pack)
Target: ice present (Sept mean SIC >= 0.15) in the cell in September w+1.
Metrics: ROC AUC over cell-years; Spearman of per-cell mean score vs observed presence frequency;
overlap of BAND cells with cells whose presence flips (20-80 %). Bootstrap CI by resampling winters.

    python -m eval.hindcast
"""
import json, pathlib, sys, time
import numpy as np
import pandas as pd
from scipy.ndimage import distance_transform_edt
from scipy.stats import spearmanr, rankdata
from pipeline import atlas as A, grid, survival

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "interim" / "hindcast.json"


def auc(score, y):
    score, y = np.asarray(score, float), np.asarray(y, bool)
    ok = np.isfinite(score)
    score, y = score[ok], y[ok]
    npos, nneg = y.sum(), (~y).sum()
    if npos == 0 or nneg == 0:
        return np.nan
    r = rankdata(score)
    return (r[y].sum() - npos * (npos + 1) / 2) / (npos * nneg)


def edge_distance(sic, land):
    ice = (np.nan_to_num(sic) >= 0.15) & ~land
    water = ~ice & ~land
    d_in = distance_transform_edt(~water)      # distance (cells) from water, for ice cells
    d_out = distance_transform_edt(~ice)       # distance from ice, for water cells
    return np.where(ice, d_in, -d_out) * grid.RES / 1000.0   # km


def main(n=400):
    t0 = time.time()
    at = A.Atlas()
    if at.sic_sept is None:
        sys.exit("No September concentration. Run the motion fetchers first.")
    land = at.static.get("land", np.zeros((grid.CROP, grid.CROP))) > 0.5
    yidx = {int(y): k for k, y in enumerate(at.sept_years)}
    rows = []
    per_winter = {}
    for w in at.winters:
        if w + 1 not in yidx or w not in yidx or w not in at.thick:
            continue
        if w + 1 > 2025:
            continue
        res = at.run(w, loo=True, n=n, seed=w)
        y = at.cells(at.sic_sept[yidx[w + 1]]) >= 0.15
        obs_ok = np.isfinite(at.cells(at.sic_sept[yidx[w + 1]]))
        h0 = res["inputs"]["h0"]
        ed = at.cells(edge_distance(at.sic_sept[yidx[w]], land))
        ok = res["ok"] & obs_ok
        df = pd.DataFrame({"w": w, "cell": np.nonzero(ok)[0], "model": res["p_without"][ok],
                           "thin": h0[ok], "edge": ed[ok], "y": y[ok], "cls": res["cls"][ok],
                           "uplift": res["uplift"][ok]})
        rows.append(df)
        per_winter[w] = {m: auc(df[m], df.y) for m in ("model", "thin", "edge")}
        print(w, {k: round(v, 3) for k, v in per_winter[w].items()}, f"{time.time()-t0:.0f}s", flush=True)
    D = pd.concat(rows, ignore_index=True)
    names = {"model": "model", "thin": "baseline_thin_ice", "edge": "baseline_edge_distance"}

    aucs = {names[m]: auc(D[m], D.y) for m in names}
    # bootstrap over winters
    rng = np.random.default_rng(0)
    ws = D.w.unique()
    boot = {m: [] for m in ("thin", "edge")}
    for _ in range(500):
        pick = rng.choice(ws, len(ws))
        S = pd.concat([D[D.w == k] for k in pick])
        a_m = auc(S.model, S.y)
        for m in boot:
            boot[m].append(a_m - auc(S[m], S.y))
    ci = {f"model_minus_{names[m]}": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
          for m, v in boot.items()}

    # per-cell: mean score vs observed presence frequency over the same years
    G = D.groupby("cell").agg(model=("model", "mean"), thin=("thin", "mean"), edge=("edge", "mean"),
                              freq=("y", "mean"), n=("y", "size"), band=("cls", lambda c: (c == survival.BAND).mean()))
    G = G[G.n >= max(3, int(0.6 * len(ws)))]
    sp = {names[m]: float(spearmanr(G[m], G.freq).statistic) for m in names}
    marginal = (G.freq >= 0.2) & (G.freq <= 0.8)
    band_cells = G.band >= 0.5
    overlap = float(marginal[band_cells].mean()) if band_cells.any() else float("nan")
    # baselines' "band": the same number of cells with mid-range scores
    def mid_overlap(col):
        k = int(band_cells.sum())
        if k == 0:
            return float("nan")
        r = G[col].rank(pct=True)
        q = (r - r[marginal].median()).abs().nsmallest(k).index   # cells nearest the marginal median
        return float(marginal.loc[q].mean())
    beats = all(aucs["model"] > aucs[b] for b in ("baseline_thin_ice", "baseline_edge_distance")) and \
        all(sp["model"] > sp[b] for b in ("baseline_thin_ice", "baseline_edge_distance"))

    out = {
        "built": time.strftime("%Y-%m-%d"), "command": "python -m eval.hindcast", "n_draws": n,
        "winters": [int(w) for w in ws], "cell_years": int(len(D)), "cells": int(len(G)),
        "auc_cell_year": aucs, "auc_diff_ci95_bootstrap_winters": ci,
        "spearman_vs_presence": sp,
        "band_overlap_with_marginal": {"model_band": overlap, "base_rate": float(marginal.mean()),
                                       "n_band_cells": int(band_cells.sum()),
                                       "baseline_thin_ice_same_k": mid_overlap("thin"),
                                       "baseline_edge_distance_same_k": mid_overlap("edge")},
        "per_winter_auc": {int(k): v for k, v in per_winter.items()},
        "beats_both": bool(beats),
    }
    out["labels"] = label_check(at, D)
    OUT.write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps({k: out[k] for k in ("auc_cell_year", "spearman_vs_presence", "band_overlap_with_marginal", "beats_both")}, indent=2, default=float))
    return out


def label_check(at, D):
    L = pd.read_csv(ROOT / "eval" / "labels.csv")
    cellmap = -np.ones((grid.CROP, grid.CROP), int)
    cellmap[at.ii, at.jj] = np.arange(len(at.ii))
    mean_p = D.groupby("cell").model.mean()
    Rm = np.nanmean(at.R_samples(), 1)
    out = []
    for r in L.itertuples():
        i, j = (int(round(v)) for v in grid.lonlat_to_ij(r.lon, r.lat))
        best = None
        for rad in range(0, 4):           # nearest evaluated cell within 3 cells (75 km)
            for di in range(-rad, rad + 1):
                for dj in range(-rad, rad + 1):
                    ii, jj = i + di, j + dj
                    if 0 <= ii < grid.CROP and 0 <= jj < grid.CROP and cellmap[ii, jj] >= 0 and cellmap[ii, jj] in mean_p.index:
                        best = cellmap[ii, jj]; break
                if best is not None: break
            if best is not None: break
        out.append({"id": r.id, "place": r.place, "label": r.label,
                    "p_without": None if best is None else float(mean_p[best]),
                    "R": None if best is None else float(Rm[best])})
    df = pd.DataFrame(out)
    summ = df.groupby("label")[["p_without", "R"]].mean().round(3).to_dict(orient="index")
    # simple ordinal agreement: survives > marginal > melts-out on P_without; export-zone lowest R
    return {"rows": out, "by_label": summ}


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 400)
