"""Calibration of the growth scale alpha at Cambridge Bay (brief 5.2, eval test 2).

Field result (Real Ice et al., Earth's Future 2026, doi:10.1029/2025EF007894, winter 2024/25):
flooded areas up to 32 cm thicker than control by mid-May; snow 1-13 cm thinner.

Two-stage model at the site point (ERA5 forcing from data/interim/cambridge_bay_climate.csv):
  1 Nov -> 1 Jan: both areas grow under the same snow.
  1 Jan: flooding saturates the snow on the flooded area; that layer freezes into snow-ice
         (thickness phi * s_jan) and stops insulating. Snow falling later still insulates.
  1 Jan -> 15 May: growth with the remaining snow.
alpha (scale on the Stefan coefficient) is solved so flooded - control = 0.32 m, and again for
half that (0.16 m) to bracket the paper's "up to" wording. Everything here is in ASSUMPTIONS.md.
    python -m pipeline.growth
"""
import json, pathlib
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from . import physics

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSV = ROOT / "data" / "interim" / "cambridge_bay_climate.csv"
PAPER_DIFF_M = 0.32
H0_SITE = 0.10        # m, landfast ice on 1 Nov (ice forms in October at Cambridge Bay); low sensitivity
SNOW_PRE_JAN = 0.4    # fraction of winter snowfall before 1 Jan
PHI = 1.0             # saturated snow layer converts to the same thickness of snow-ice


def site_model(fdd, fdd_jan, snowfall, alpha):
    s_end = physics.snowfall_to_mean_depth(snowfall) * 2          # end-of-season depth
    s_jan = SNOW_PRE_JAN * s_end
    fdd_pre = max(fdd - fdd_jan, 0)
    h_jan = physics.stefan_growth(H0_SITE, fdd_pre, 0.5 * s_jan, alpha)
    post = 0.5 * (s_end - s_jan)
    control = physics.stefan_growth(h_jan, fdd_jan, s_jan + post, alpha)
    flooded = physics.stefan_growth(h_jan + PHI * s_jan, fdd_jan, post, alpha)
    return float(control), float(flooded)


def calibrate(row, target=PAPER_DIFF_M):
    f = lambda a: (lambda c, fl: fl - c)(*site_model(row.fdd, row.fdd_jan, row.snowfall, a)) - target
    lo, hi = 0.05, 6.0
    if f(lo) * f(hi) > 0:
        return None
    return brentq(f, lo, hi)


def piomas_near(lat=69.05, lon=-105.10, w=2024):
    """PIOMAS April thickness at the nearest ocean cell with data (model cross-check, brief 6.2)."""
    import xarray as xr
    from . import grid
    f = ROOT / "data" / "interim" / f"piomas_{w}.nc"
    if not f.exists():
        return None
    h = xr.open_dataset(f)["h_apr"].values
    i, j = (int(round(v)) for v in grid.lonlat_to_ij(lon, lat))
    for rad in range(0, 6):
        sub = h[max(i - rad, 0):i + rad + 1, max(j - rad, 0):j + rad + 1]
        sub = np.where(sub > 0.05, sub, np.nan)   # PIOMAS writes 0 where it does not resolve channels
        if np.isfinite(sub).any():
            return {"h_apr_m": float(np.nanmean(sub)), "radius_km": rad * 25,
                    "note": "PIOMAS does not resolve Dease Strait; nearest cells with ice"}
    return None


def main():
    if not CSV.exists():
        raise SystemExit("No Cambridge Bay forcing. Run the climate fetcher first (make fetch).")
    df = pd.read_csv(CSV, comment="#")
    r = df[df.winter == 2024].iloc[0]
    scan = {a: site_model(r.fdd, r.fdd_jan, r.snowfall, a) for a in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 6.0)}
    a32 = calibrate(r, PAPER_DIFF_M)
    a16 = calibrate(r, PAPER_DIFF_M / 2)
    # The flooded-control difference saturates below 32 cm (it tends to the snow-ice layer as alpha grows),
    # so alpha cannot be fitted to 32 cm. Keep the textbook value and carry +/-0.25 as uncertainty.
    alpha = a32 if a32 is not None else 1.0
    c, fl = site_model(r.fdd, r.fdd_jan, r.snowfall, alpha)
    pio = piomas_near()
    out = {
        "site": "Cambridge Bay, approx. 69.05N 105.10W (exact site not public)",
        "winter": "2024/25", "fdd_K_day": float(r.fdd), "fdd_from_jan": float(r.fdd_jan), "snowfall_m_we": float(r.snowfall),
        "uncalibrated": {"control_m": scan[1.0][0], "flooded_m": scan[1.0][1], "diff_m": scan[1.0][1] - scan[1.0][0]},
        "alpha_scan": {str(a): {"control_m": v[0], "diff_m": v[1] - v[0]} for a, v in scan.items()},
        "alpha_for_32cm": a32, "alpha_for_16cm": a16,
        "alpha": alpha, "alpha_sd": 0.25,
        "fit": "not reachable: difference saturates below 32 cm; alpha kept at 1.0" if a32 is None else "fitted to 32 cm",
        "calibrated": {"control_m": c, "flooded_m": fl, "diff_m": fl - c},
        "gap_to_paper_m": PAPER_DIFF_M - (fl - c),
        "paper_diff_m": PAPER_DIFF_M, "paper": "Real Ice et al. (2026) Earth's Future, doi:10.1029/2025EF007894",
        "piomas_crosscheck": pio,
        "fdd_ref_cambridge_bay_2024": float(r.fdd),
        "series": df.to_dict(orient="records"),
    }
    (ROOT / "data" / "interim" / "calibration.json").write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps({k: out[k] for k in ("uncalibrated", "alpha", "fit", "gap_to_paper_m", "piomas_crosscheck")}, indent=2, default=float))
    return out


if __name__ == "__main__":
    main()
