"""Thermodynamic ice growth and survival thickness. Pure functions, vectorised.

Growth: Stefan's law with a snow layer (Leppäranta 1993 form):
    (h + r s)^2 = (h0 + r s)^2 + alpha * a * FDD,   r = k_i / k_s,  a = 2 k_i / (rho_i L_f)
FDD in K day (converted to K s inside a). alpha is the single calibration scale (brief 5.2).
"""
import numpy as np

CONSTANTS = {
    "k_i": 2.0,        # W m-1 K-1, thermal conductivity of sea ice (textbook ~2.0-2.2; Untersteiner 1964)
    "k_s": 0.30,       # W m-1 K-1, snow on sea ice (Sturm et al. 2002 report ~0.3 for Arctic sea-ice snow)
    "rho_i": 917.0,    # kg m-3, pure ice
    "L_f": 3.34e5,     # J kg-1, latent heat of fusion of fresh ice (sea ice lower; kept as brief states)
    "T_f": -1.8,       # deg C, seawater freezing point (salinity ~33)
    "rho_s": 330.0,    # kg m-3, settled snow on sea ice (Warren et al. 1999 climatology ~300-340)
}
SECONDS_PER_DAY = 86400.0
A_STEFAN = 2 * CONSTANTS["k_i"] / (CONSTANTS["rho_i"] * CONSTANTS["L_f"]) * SECONDS_PER_DAY  # m2 per K day
R_SNOW = CONSTANTS["k_i"] / CONSTANTS["k_s"]

# van Dijke et al. (2022) melt-season decay rates over 91 melt days (cm/day) -> survival thickness
MELT_RATE = {"beaufort": (2.1, 2.7), "transpolar": (0.8, 1.4)}
MELT_DAYS_REF = 91


def stefan_growth(h0, fdd, snow_depth=0.0, alpha=1.0):
    """End-of-season thickness (m) from start thickness h0 (m), FDD (K day), mean snow depth (m)."""
    h0, fdd, s = np.asarray(h0, float), np.maximum(np.asarray(fdd, float), 0), np.asarray(snow_depth, float)
    rs = R_SNOW * s
    return np.sqrt((h0 + rs) ** 2 + alpha * A_STEFAN * fdd) - rs


def snowfall_to_mean_depth(snowfall_m_we):
    """Season-mean snow depth from total winter snowfall (m water equivalent).
    Snow accumulates roughly linearly, so the season mean is about half the end depth.
    Wind loss to leads ignored (biases insulation high)."""
    return 0.5 * np.asarray(snowfall_m_we, float) * 1000.0 / CONSTANTS["rho_s"]


def transpolar_weight(lat):
    """0 = Beaufort-type melt regime, 1 = Transpolar-type. Linear in latitude 75N -> 85N.
    Proxy for ice age / drift character (NSIDC ice age not used in v1). Weakest assumption."""
    return np.clip((np.asarray(lat, float) - 75.0) / 10.0, 0.0, 1.0)


def melt_rate(lat):
    """Mean and half-range of melt decay rate (m/day) for each cell."""
    w = transpolar_weight(lat)
    lo = (1 - w) * MELT_RATE["beaufort"][0] + w * MELT_RATE["transpolar"][0]
    hi = (1 - w) * MELT_RATE["beaufort"][1] + w * MELT_RATE["transpolar"][1]
    return (lo + hi) / 200.0, (hi - lo) / 200.0


def survival_thickness(lat, melt_days):
    """hs = melt_rate * melt_days (m). Returns (mean, sd)."""
    m, half = melt_rate(lat)
    md = np.asarray(melt_days, float)
    return m * md, half / np.sqrt(3) * md  # sd of a uniform over the stated range
