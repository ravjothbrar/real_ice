"""Export the atlas to web/public/data (format: docs/CONTRACT.md, "Web export").
    python -m pipeline.export
"""
import json, pathlib, shutil, time
import numpy as np
from . import atlas as A, grid, survival, scale, cards

ROOT = pathlib.Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "public" / "data"
INTERIM = ROOT / "data" / "interim"

# name: (scale, offset, unit, title)
STATIC_LAYERS = {
    "sept_freq":  (1 / 254, 0.0, "fraction", "September ice presence 2012-2025 (observed)"),
    "fdd":        (25.0, 0.0, "K day", "Freezing degree days (ERA5 climatology)"),
    "hs":         (0.015, 0.0, "m", "Survival thickness"),
    "R":          (1 / 254, 0.0, "fraction", "Retention to 15 September"),
    "R_sd":       (1 / 254, 0.0, "fraction", "Retention year-to-year spread"),
    "disagree":   (0.01, 0.0, "m", "Thickness product disagreement"),
    "excluded":   (1.0, 0.0, "bits", "Exclusions: 1 settlement, 2 protected, 4 shipping"),
    "region":     (1.0, 0.0, "code", "Region"),
    "depth":      (5.0, 0.0, "m", "Water depth"),
}
WINTER_LAYERS = {
    "h0":        (0.025, 0.0, "m", "Start-of-winter thickness (November)"),
    "h0_sd":     (0.01, 0.0, "m", "Start thickness uncertainty"),
    "spread":    (0.01, 0.0, "m", "Between-product spread"),
    "h_end":     (0.025, 0.0, "m", "Modelled mid-May thickness"),
    "p_without": (1 / 254, 0.0, "probability", "P(survive) without thickening"),
    "p_with":    (1 / 254, 0.0, "probability", "P(survive) with thickening"),
    "uplift":    (1 / 254, 0.0, "probability", "Uplift"),
    "blocked":   (1 / 254, 0.0, "fraction", "Share of draws below the 0.6 m guard"),
    "gain":      (0.005, 0.0, "m", "Mean flooding gain applied"),
    "sept_obs":  (1.0, 0.0, "0/1", "Ice observed in the following September"),
}


def q(v, s, o):
    v = np.asarray(v, float)
    b = np.rint((v - o) / s)
    return np.where(np.isfinite(b), np.clip(b, 0, 254), 255).astype(np.uint8)


def main(n=1000):
    t0 = time.time()
    WEB.mkdir(parents=True, exist_ok=True)
    at = A.Atlas()
    cal = json.loads((INTERIM / "calibration.json").read_text()) if (INTERIM / "calibration.json").exists() else None
    alpha = cal["alpha"] if cal else 1.0
    alpha_sd = cal["alpha_sd"] if cal else 0.0
    if cal:
        at.fdd_ref = cal["fdd_ref_cambridge_bay_2024"]
    N = int(at.mask.sum())
    np.stack([at.ii, at.jj], 1).astype("<u2").tofile(WEB / "cells.bin")

    # static
    Rs = at.R_samples()
    first_w = max(w for w in at.thick if w <= 2024)
    x = at.inputs_for(first_w)
    dis = None
    p = INTERIM / "thick_disagreement.nc"
    if p.exists():
        import xarray as xr
        ds = xr.open_dataset(p)
        vs = [v for v in ds.data_vars if ds[v].ndim == 2 and ds[v].shape == (grid.CROP, grid.CROP) and not v.startswith("n_") and "count" not in v]
        if vs:
            dis = at.cells(np.nanmean(np.stack([ds[v].values for v in vs]), 0))
    st = {
        "sept_freq": at.cells(at.sept_freq) if at.sept_freq is not None else np.full(N, np.nan),
        "fdd": x["fdd"], "hs": x["hs"], "R": np.nanmean(Rs, 1), "R_sd": np.nanstd(Rs, 1),
        "disagree": dis if dis is not None else np.full(N, np.nan),
        "excluded": A.excluded(at), "region": at.cells(at.static["region"]) if "region" in at.static else np.zeros(N),
        "depth": at.cells(at.static["depth"]) if "depth" in at.static else np.full(N, np.nan),
    }
    np.concatenate([q(st[k], s, o) for k, (s, o, *_ ) in STATIC_LAYERS.items()]).tofile(WEB / "static.bin")

    yidx = {int(y): k for k, y in enumerate(at.sept_years)} if at.sept_years is not None else {}
    winters, runs = [], {}
    for w in sorted(at.thick):
        r = at.run(w, n=n, seed=w, alpha=alpha, alpha_sd=alpha_sd)
        runs[w] = r
        t = at.thick[w]
        so = at.cells(at.sic_sept[yidx[w + 1]]) >= 0.15 if (w + 1) in yidx else np.full(N, np.nan)
        so = np.where(np.isfinite(at.cells(at.sic_sept[yidx[w + 1]])) if (w + 1) in yidx else False, so, np.nan).astype(float)
        L = {"h0": r["inputs"]["h0"], "h0_sd": r["inputs"]["h0_sd"], "spread": at.cells(t["spread"]),
             "h_end": r["h_end"], "p_without": r["p_without"], "p_with": r["p_with"], "uplift": r["uplift"],
             "blocked": r["blocked"], "gain": r["gain"], "sept_obs": so}
        np.concatenate([q(L[k], s, o) for k, (s, o, *_) in WINTER_LAYERS.items()]).tofile(WEB / f"winter-{w}.bin")
        cls = r["cls"]
        area = lambda c: float((cls == c).sum() * grid.CELL_AREA_KM2)
        winters.append({
            "w": w, "label": f"{w}/{str(w + 1)[-2:]}", "partial": w >= 2026,
            "products": t["products"], "ice_km2": float(r["ok"].sum() * grid.CELL_AREA_KM2),
            "band_km2": area(survival.BAND), "survives_km2": area(survival.SURVIVES),
            "hopeless_km2": area(survival.HOPELESS), "blocked_km2": area(survival.BLOCKED),
            "below_km2": area(survival.NONE),
            "band_excl_km2": float(((cls == survival.BAND) & (st["excluded"] > 0)).sum() * grid.CELL_AREA_KM2),
            "observed_next_sept": (w + 1) in yidx and w + 1 <= 2025,
        })
        print(w, winters[-1]["band_km2"], f"{time.time() - t0:.0f}s", flush=True)

    hind = json.loads((INTERIM / "hindcast.json").read_text()) if (INTERIM / "hindcast.json").exists() else None
    sens = json.loads((INTERIM / "sensitivity.json").read_text()) if (INTERIM / "sensitivity.json").exists() else None
    prov = json.loads((ROOT / "data" / "PROVENANCE.json").read_text()) if (ROOT / "data" / "PROVENANCE.json").exists() else {}
    manifest = {
        "built": time.strftime("%Y-%m-%d"),
        "grid": {"epsg": grid.EPSG, "res": grid.RES, "crop": grid.CROP, "half": grid.HALF,
                 "cell_area_km2": grid.CELL_AREA_KM2},
        "n_cells": N,
        "winters": winters,
        "static_layers": list(STATIC_LAYERS), "winter_layers": list(WINTER_LAYERS),
        "layers": {k: {"scale": s, "offset": o, "unit": u, "title": tt}
                   for k, (s, o, u, tt) in {**STATIC_LAYERS, **WINTER_LAYERS}.items()},
        "classes": survival.CLASS_NAMES,
    }
    summary = {
        "built": manifest["built"],
        "thresholds": {"survives_p_without": survival.THRESHOLDS["survives_p_without"],
                       "hopeless_p_with": survival.THRESHOLDS["hopeless_p_with"],
                       "uplift": survival.THRESHOLDS["uplift"], "blocked_frac": survival.THRESHOLDS["blocked_frac"],
                       "guard_m": survival.GUARD_M},
        "gain_prior_m": survival.GAIN,
        "scale": {"target_km2": scale.TARGET_KM2, "mwh_per_km2": scale.ENERGY_MWH_PER_KM2,
                  "window_days": scale.ICE_SAFE_WINDOW_DAYS, "cost_usd_per_year_at_scale": 6e9,
                  "cost_usd_10yr": 43e9, "share_of_ice_area": 0.05,
                  "source": "Ocean Visions, Arctic sea-ice thickening roadmap page (accessed 2026)",
                  "throughput_default_km2_per_drone_day": 0.1,
                  "throughput_note": "ASSUMPTION: drone throughput is not public."},
        "calibration": cal and {k: v for k, v in cal.items() if k != "series"},
        "hindcast": hind and {k: v for k, v in hind.items() if k != "labels"},
        "labels": hind and hind.get("labels"),
        "sensitivity": sens,
        "winters": winters,
        "cambridge_bay": {"lat": 69.05, "lon": -105.10, "note": "Site approximate: ~7 km from the hamlet; exact coordinates not public."},
        "sources": prov,
    }
    summary["cards"] = cards.build(at, runs, st, summary)
    (WEB / "manifest.json").write_text(json.dumps(manifest, indent=1, default=float))
    (WEB / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
    lj = INTERIM / "land.json"
    if lj.exists() and not (WEB / "land.json").exists():
        shutil.copy(lj, WEB / "land.json")
    tot = sum(f.stat().st_size for f in WEB.iterdir())
    print(f"exported {N} cells, {len(winters)} winters, {tot/1e6:.2f} MB in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
