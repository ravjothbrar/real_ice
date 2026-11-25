"""One-at-a-time tornado on BAND area (brief 5.9): WHAT MOVES THE ANSWER.

Each factor is pushed to a low and a high value (ranges in FACTORS, logged in ASSUMPTIONS.md);
band area (km2) is recomputed with the same random seed. Ranked by swing = |high - low|.
    python -m pipeline.sensitivity [winter]
"""
import json, pathlib, sys
import numpy as np
from . import atlas as A, survival, grid

FACTORS = {   # name: (label, low override, high override)
    "hs_scale":   ("Survival thickness (melt rate x melt days)", {"hs_scale": 0.8}, {"hs_scale": 1.2}),
    "h0_shift":   ("Start-of-winter thickness", {"h0_shift": -0.2}, {"h0_shift": 0.2}),
    "gain_scale": ("Flooding gain G", {"gain_scale": 0.5}, {"gain_scale": 1.5}),
    "fdd_scale":  ("Freezing degree days (ERA5)", {"fdd_scale": 0.9}, {"fdd_scale": 1.1}),
    "snow_scale": ("Snow insulation", {"snow_scale": 0.5}, {"snow_scale": 1.5}),
    "R_shift":    ("Retention (drift export)", {"R_shift": -0.15}, {"R_shift": 0.15}),
    "guard":      ("Thin-ice guard (0.6 m)", {"guard": 0.5}, {"guard": 0.7}),
    "threshold":  ("Uplift threshold", {"threshold": 0.15}, {"threshold": 0.25}),
}


def band_area(at, w, ov, alpha, n, seed=None, alpha_sd=0.0):
    g0 = survival.GUARD_M
    if "guard" in ov:
        survival.GUARD_M = ov["guard"]
    try:
        r = at.run(w, n=n, seed=w if seed is None else seed, alpha=alpha, alpha_sd=alpha_sd, ov=ov)
    finally:
        survival.GUARD_M = g0
    return float((r["cls"] == survival.BAND).sum() * grid.CELL_AREA_KM2)


def main(w=None, n=1000, alpha=1.0, at=None, alpha_sd=0.0):
    at = at or A.Atlas()
    w = w or max(k for k in at.thick if k <= 2024)
    base = band_area(at, w, {}, alpha, n, alpha_sd=alpha_sd)
    rows = []
    for k, (label, lo, hi) in FACTORS.items():
        a_lo, a_hi = band_area(at, w, lo, alpha, n, alpha_sd=alpha_sd), band_area(at, w, hi, alpha, n, alpha_sd=alpha_sd)
        rows.append({"factor": k, "label": label, "low": lo, "high": hi,
                     "band_km2_low": a_lo, "band_km2_high": a_hi, "swing_km2": abs(a_hi - a_lo)})
        print(f"{label:45s} {a_lo:>12,.0f} {a_hi:>12,.0f}", flush=True)
    rows.sort(key=lambda r: -r["swing_km2"])
    return {"winter": w, "n_draws": n, "base_band_km2": base, "method": "one-at-a-time, common random numbers",
            "factors": rows}


if __name__ == "__main__":
    cal = json.loads((pathlib.Path(__file__).resolve().parents[1] / "data" / "interim" / "calibration.json").read_text())
    at = A.Atlas(); at.fdd_ref = cal["fdd_ref_cambridge_bay_2024"]
    out = main(int(sys.argv[1]) if len(sys.argv) > 1 else None, at=at, alpha=cal["alpha"], alpha_sd=cal["alpha_sd"])
    p = pathlib.Path(__file__).resolve().parents[1] / "data" / "interim" / "sensitivity.json"
    p.write_text(json.dumps(out, indent=2))
