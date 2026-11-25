"""Assemble per-winter survival atlas: ensemble h0 + climatological forcing + retention -> MC -> classes.

Forecast mode (see ASSUMPTIONS.md): a winter uses its own start-of-winter thickness and the
climatology of every other input. `loo=True` leaves the target winter out of the climatologies.
"""
import json
import numpy as np
from . import grid, inputs, physics, survival

POLE_FILL_LAT = 86.5


def _fill_pole(h, lat=grid.LAT):
    """Altimeter orbits leave a hole near the pole. Fill cells north of 86.5N that are NaN with the
    median of valid cells in the 84.5-86.5N ring (documented in ASSUMPTIONS.md)."""
    h = h.copy()
    ring = (lat >= 84.5) & (lat < POLE_FILL_LAT) & np.isfinite(h)
    hole = (lat >= POLE_FILL_LAT) & ~np.isfinite(h)
    if ring.sum() > 20 and hole.any():
        h[hole] = np.nanmedian(h[ring])
    return h, hole


class Atlas:
    def __init__(self):
        self.static = inputs.static()
        self.winters = inputs.winters_available()
        self.climate = {w: c for w in range(2005, 2027) if (c := inputs.climate(w))}
        self.ret = {w: r for w in range(2005, 2027) if (r := inputs.retention(w)) is not None}
        self.thick = {w: t for w in self.winters if (t := inputs.thickness(w))}
        for w, t in self.thick.items():
            for k in ("h0", "h0_sd"):
                t[k], hole = _fill_pole(t[k])
            t["pole_filled"] = hole
        self.sept_years, self.sic_sept, self.sept_freq = inputs.sept()
        self._cells()
        self.fdd_ref = None

    # ice-capable cells: ocean cells that had start-of-winter ice in any winter, or ice in any September
    def _cells(self):
        land = self.static.get("land", np.zeros((grid.CROP, grid.CROP))) > 0.5
        any_ice = np.zeros((grid.CROP, grid.CROP), bool)
        for t in self.thick.values():
            any_ice |= np.isfinite(t["h0"]) & (t["h0"] > 0)
        if self.sept_freq is not None:
            any_ice |= np.nan_to_num(self.sept_freq) > 0
        self.mask = any_ice & ~land
        self.ii, self.jj = np.nonzero(self.mask)
        self.lat, self.lon = grid.LAT[self.mask], grid.LON[self.mask]

    def cells(self, a):
        return a[self.mask]

    def clim(self, var, exclude=None):
        stack = [c[var] for w, c in self.climate.items() if var in c and w != exclude]
        return np.nanmean(np.stack(stack), 0) if stack else None

    def R_samples(self, exclude=None):
        """(cells, years) retention samples; target winter excluded when exclude is set."""
        ys = [w for w in sorted(self.ret) if w != exclude]
        if not ys:
            return np.ones((self.mask.sum(), 1))
        return np.stack([self.cells(self.ret[w]) for w in ys], 1)

    def inputs_for(self, w, loo=False, ov=None):
        ov = ov or {}
        ex = w if loo else None
        t = self.thick[w]
        h0 = self.cells(t["h0"]) * ov.get("h0_scale", 1.0) + ov.get("h0_shift", 0.0)
        h0_sd = self.cells(t["h0_sd"])
        fdd = self.cells(self.clim("fdd", ex)) * ov.get("fdd_scale", 1.0)
        snow = physics.snowfall_to_mean_depth(self.cells(self.clim("snowfall", ex))) * ov.get("snow_scale", 1.0)
        melt = self.cells(self.clim("melt_days", ex)) * ov.get("melt_scale", 1.0)
        hs, hs_sd = physics.survival_thickness(self.lat, melt)
        hs = hs * ov.get("hs_scale", 1.0)
        R = self.R_samples(ex)
        if "R_shift" in ov:
            R = np.clip(R + ov["R_shift"], 0, 1)
        return dict(h0=h0, h0_sd=h0_sd, fdd=np.nan_to_num(fdd), snow=np.nan_to_num(snow),
                    hs=np.nan_to_num(hs, nan=9.9), hs_sd=np.nan_to_num(hs_sd), R_samples=R, melt=melt)

    def run(self, w, loo=False, n=1000, seed=0, alpha=1.0, alpha_sd=0.0, ov=None, gain=None):
        x = self.inputs_for(w, loo, ov)
        ok = np.isfinite(x["h0"])
        res = {k: np.full(ok.shape, np.nan) for k in
               ("p_without", "p_with", "uplift", "blocked", "h_end", "h_end_sd", "gain")}
        g = dict(survival.GAIN, **(gain or {}))
        if ov and "gain_scale" in ov:
            g = {k: v * ov["gain_scale"] for k, v in g.items()}
        if ok.any():
            out = survival.monte_carlo(
                h0=x["h0"][ok], h0_sd=x["h0_sd"][ok], fdd=x["fdd"][ok], snow=x["snow"][ok],
                hs=x["hs"][ok], hs_sd=x["hs_sd"][ok], R_samples=x["R_samples"][ok],
                fdd_ref=self.fdd_ref or float(np.nanmedian(x["fdd"][ok])), n=n, seed=seed,
                alpha=alpha, alpha_sd=alpha_sd, gain=g)
            for k in res:
                res[k][ok] = out[k]
        thr = (ov or {}).get("threshold", survival.THRESHOLDS["uplift"])
        guard_ov = (ov or {}).get("guard")
        cls = np.full(ok.shape, 255, np.uint8)
        if ok.any():
            cls[ok] = survival.classify({k: res[k][ok] for k in res}, threshold=thr)
        res.update(cls=cls, ok=ok, inputs=x)
        return res


def excluded(atlas):
    s = atlas.static
    bits = np.zeros(atlas.mask.sum(), np.uint8)
    for b, k in enumerate(("excl_settlement", "excl_protected", "excl_shipping")):
        if k in s:
            bits |= (atlas.cells(s[k]) > 0.5).astype(np.uint8) << b
    return bits
