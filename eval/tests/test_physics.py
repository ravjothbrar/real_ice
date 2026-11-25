"""Physics unit tests (brief section 6, test 4). Written before any tuning."""
import numpy as np
import pytest
from pipeline import physics, survival, scale


def test_growth_monotonic_in_fdd():
    fdd = np.linspace(0, 6000, 50)
    for h0 in (0.1, 0.6, 1.5):
        for snow in (0.0, 0.2):
            h = physics.stefan_growth(h0, fdd, snow_depth=snow)
            assert np.all(np.diff(h) > 0)
            assert h[0] == pytest.approx(h0)


def test_snow_insulates():
    assert physics.stefan_growth(0.5, 4000, snow_depth=0.3) < physics.stefan_growth(0.5, 4000, snow_depth=0.0)


def test_constants_logged():
    c = physics.CONSTANTS
    assert 1.9 <= c["k_i"] <= 2.3 and 900 <= c["rho_i"] <= 930 and 3.3e5 <= c["L_f"] <= 3.4e5


def _mc(h0, hs=1.5, R=None, n=2000, **kw):
    h0 = np.atleast_1d(np.asarray(h0, float))
    R_samples = np.ones((h0.size, 5)) if R is None else R
    return survival.monte_carlo(
        h0=h0, h0_sd=np.full(h0.size, 0.05), fdd=np.full(h0.size, 2000.0),
        snow=np.full(h0.size, 0.1), hs=np.full(h0.size, hs), hs_sd=np.full(h0.size, 0.05),
        R_samples=R_samples, fdd_ref=2000.0, n=n, seed=1, **kw)


def test_flooding_never_below_guard():
    out = _mc([0.2, 0.3, 0.4])  # all draws (sd 5 cm) stay below the 0.6 m guard
    assert np.all(out["blocked"] > 0.99)
    assert np.allclose(out["p_with"], out["p_without"])
    assert np.allclose(out["uplift"], 0.0)


def test_uplift_zero_when_survives_anyway():
    out = _mc([4.0], hs=1.0)
    assert out["p_without"][0] > 0.99
    assert out["uplift"][0] < 0.01


def test_uplift_nonnegative_and_probabilities_bounded():
    out = _mc(np.linspace(0.1, 3, 40))
    for k in ("p_without", "p_with", "uplift", "blocked"):
        assert np.all((out[k] >= 0) & (out[k] <= 1))
    assert np.all(out["p_with"] >= out["p_without"] - 1e-12)


def test_retention_scales_probability():
    h0 = np.array([3.0, 3.0])
    R = np.array([[1.0] * 5, [0.5] * 5])
    out = _mc(h0, hs=1.0, R=R)
    assert out["p_without"][1] == pytest.approx(0.5 * out["p_without"][0], abs=0.02)


def test_band_area_shrinks_when_survival_thickness_rises():
    h0 = np.linspace(0.6, 1.2, 200)   # thin-to-medium start thickness: bulk below hs
    areas = []
    for hs in (1.6, 2.0, 2.4):
        out = _mc(h0, hs=hs, n=800)
        cls = survival.classify(out, threshold=0.2)
        areas.append(int((cls == survival.BAND).sum()))
    assert areas[0] > areas[1] > areas[2], areas


def test_classify_codes():
    out = {"p_without": np.array([0.9, 0.3, 0.05, 0.1]), "p_with": np.array([0.95, 0.7, 0.1, 0.1]),
           "uplift": np.array([0.05, 0.4, 0.05, 0.0]), "blocked": np.array([0, 0, 0, 1.0])}
    cls = survival.classify(out, threshold=0.2)
    assert list(cls) == [survival.SURVIVES, survival.BAND, survival.HOPELESS, survival.BLOCKED]


def test_scale_numbers():
    s = scale.scale(1_000_000, throughput_km2_per_drone_day=1.0, window_days=90)
    assert s["energy_twh"] == pytest.approx(8.0)          # 8 MWh/km2 x 1e6 km2 (Ocean Visions)
    assert s["fleet"] == pytest.approx(1_000_000 / 90, rel=1e-6)
    assert s["assumption"] and "ASSUMPTION" in s["fleet_label"]
