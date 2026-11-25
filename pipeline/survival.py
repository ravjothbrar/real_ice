"""Monte Carlo survival probabilities, uplift and band classes (brief 5.6-5.7)."""
import numpy as np
from . import physics

NONE, SURVIVES, BAND, HOPELESS, BLOCKED = 0, 1, 2, 3, 4
CLASS_NAMES = {NONE: "BELOW THRESHOLD", SURVIVES: "SURVIVES ANYWAY", BAND: "BAND",
               HOPELESS: "HOPELESS", BLOCKED: "BLOCKED (<0.6 m)"}
THRESHOLDS = {"survives_p_without": 0.7, "hopeless_p_with": 0.2, "uplift": 0.2, "blocked_frac": 0.5}

GUARD_M = 0.6                       # van Dijke et al. (2022): do not flood ice thinner than 0.6 m
GAIN = {"min": 0.0, "mode": 0.32, "max": 0.70}   # m; paper (up to 32 cm), Real Ice scale model (70 cm)
FDD_SD_FRAC = 0.08                  # ERA5 FDD uncertainty (warm bias over sea ice, Wang et al. 2019)
SNOW_RANGE = (0.5, 1.5)             # multiplicative uncertainty on snow insulation


def monte_carlo(h0, h0_sd, fdd, snow, hs, hs_sd, R_samples, fdd_ref, n=1000, seed=0,
                alpha=1.0, alpha_sd=0.0, gain=None, chunk=1500, return_draws=False):
    """Per-cell survival probabilities. All inputs 1-D over cells; R_samples (cells, years) with NaN gaps.
    Common random numbers are used for with/without so uplift >= 0 draw by draw."""
    gain = gain or GAIN
    rng = np.random.default_rng(seed)
    N = len(h0)
    out = {k: np.zeros(N) for k in ("p_without", "p_with", "uplift", "blocked", "h_end", "h_end_sd", "gain")}
    for a in range(0, N, chunk):
        b = min(N, a + chunk); m = b - a
        H0 = np.maximum(h0[a:b, None] + h0_sd[a:b, None] * rng.standard_normal((m, n)), 0.02)
        F = fdd[a:b, None] * (1 + FDD_SD_FRAC * rng.standard_normal((m, n)))
        S = snow[a:b, None] * rng.uniform(*SNOW_RANGE, (m, n))
        AL = alpha + alpha_sd * rng.standard_normal((1, n))
        HE = physics.stefan_growth(H0, F, S, np.maximum(AL, 0.05))
        HS = hs[a:b, None] + hs_sd[a:b, None] * rng.standard_normal((m, n))
        ratio = np.where(fdd_ref > 0, np.maximum(F, 0) / fdd_ref, 0)
        G = rng.triangular(gain["min"], gain["mode"], gain["max"], (m, n)) * ratio
        blocked = H0 < GUARD_M
        G = np.where(blocked, 0.0, G)
        Rs = R_samples[a:b]
        idx = rng.integers(0, Rs.shape[1], (m, n))
        R = np.take_along_axis(Rs, idx, 1)
        R = np.where(np.isfinite(R), R, np.nanmean(Rs, 1, keepdims=True) if Rs.size else 0)
        R = np.nan_to_num(R, nan=0.0)
        sw = (HE >= HS) * R
        sf = (HE + G >= HS) * R
        out["p_without"][a:b] = sw.mean(1)
        out["p_with"][a:b] = sf.mean(1)
        out["uplift"][a:b] = (sf - sw).mean(1)
        out["blocked"][a:b] = blocked.mean(1)
        out["h_end"][a:b] = HE.mean(1)
        out["h_end_sd"][a:b] = HE.std(1)
        out["gain"][a:b] = G.mean(1)
    return out


def classify(out, threshold=THRESHOLDS["uplift"], t=THRESHOLDS):
    pw, pf, u, bl = (np.asarray(out[k]) for k in ("p_without", "p_with", "uplift", "blocked"))
    cls = np.full(pw.shape, NONE, dtype=np.uint8)
    cls[pf <= t["hopeless_p_with"]] = HOPELESS
    cls[u >= threshold] = BAND
    cls[(bl >= t["blocked_frac"]) & (pw < t["survives_p_without"])] = BLOCKED
    cls[pw >= t["survives_p_without"]] = SURVIVES
    return cls
