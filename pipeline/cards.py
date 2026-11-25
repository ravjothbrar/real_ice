"""Signal-guide cards: exactly four lines per layer/metric. Meaning / Why it matters / Not proof of / Example.
Example lines are computed from the exported data, never typed in."""
import numpy as np
from . import survival, grid

BOX = {  # lat0, lat1, lon0, lon1
    "Beaufort": (72, 77, -150, -130), "Fram Strait": (78, 81, -10, 10),
    "north of Greenland": (83, 87, -100, -60), "Laptev": (73, 78, 110, 135),
}


def _box(at, name):
    a, b, c, d = BOX[name]
    return (at.lat >= a) & (at.lat < b) & (at.lon >= c) & (at.lon < d)


def _med(v, m):
    v = np.asarray(v, float)[m]
    v = v[np.isfinite(v)]
    return float(np.median(v)) if v.size else None


def _fmt(x, nd=2):
    return None if x is None else f"{x:,.{nd}f}"


def build(at, runs, st, summary):
    w = max(k for k in runs if k <= 2024)
    lab = f"{w}/{str(w + 1)[-2:]}"
    r = runs[w]
    h0 = r["inputs"]["h0"]
    win = next(x for x in summary["winters"] if x["w"] == w)
    cards = {}

    def add(key, meaning, why, notp, example):
        if example:
            cards[key] = {"meaning": meaning, "why": why, "not_proof_of": notp, "example": example}

    bh, gh = _med(h0, _box(at, "Beaufort")), _med(h0, _box(at, "north of Greenland"))
    add("h0", "Satellite ice thickness in November, averaged across the products available that winter.",
        "Thin start-of-winter ice needs more growth, or help, to reach a thickness that lasts the summer.",
        "Exact thickness: radar thickness depends on assumed snow depth and density, and early-winter retrievals are biased.",
        bh and gh and f"November {w}: median {_fmt(bh)} m in the Beaufort vs {_fmt(gh)} m north of Greenland (products: {', '.join(r['inputs'] and at.thick[w]['products'])}).")
    d = _med(st["disagree"], np.isfinite(st["disagree"]))
    add("disagree", "Mean absolute difference between thickness products in the same cell and month.",
        "Where products disagree, every downstream number is less certain; the spread feeds the ensemble.",
        "Which product is right. Disagreement only shows where to distrust them all.",
        d and f"Median disagreement across overlapping winters: {_fmt(d)} m.")
    cb = _med(st["fdd"], np.abs(at.lat - 69.0) + np.abs(at.lon + 105) < 1.5)
    ca = _med(st["fdd"], at.lat > 85)
    add("fdd", "Freezing degree days, 1 Nov - 15 May: how cold and how long the winter is (ERA5 climatology).",
        "Cold drives natural growth and the extra growth flooding unlocks.",
        "Growth itself. ERA5 is warm-biased over sea ice in cold conditions (Wang et al. 2019), so FDD is likely low.",
        ca and f"Central Arctic (>85N) median {_fmt(ca, 0)} K day" + (f"; near Cambridge Bay {_fmt(cb, 0)} K day." if cb else "."))
    bhs, chs = _med(st["hs"], _box(at, "Beaufort")), _med(st["hs"], at.lat > 85)
    add("hs", "Thickness needed by mid-May to last the melt season: melt rate x melt days (van Dijke et al. 2022 regimes).",
        "The finish line every cell is measured against.",
        "A measured threshold. It blends two regional melt regimes by latitude; the weakest assumption in the atlas.",
        bhs and chs and f"Beaufort median {_fmt(bhs)} m vs central Arctic {_fmt(chs)} m.")
    fr, gr = _med(st["R"], _box(at, "Fram Strait")), _med(st["R"], _box(at, "north of Greenland"))
    add("R", "Share of ice seeded in a cell on 1 November still in ice-covered water on 15 September (OSI SAF drift).",
        "Thickened ice that drifts out of the Arctic is lost, however thick it is.",
        "Multi-year retention. Summer drift is partly model-filled; 75 km drift vs 25 km cells.",
        fr is not None and gr is not None and f"Fram Strait {_fmt(fr)} vs north of Greenland {_fmt(gr)} (mean over years).")
    tgt = summary["scale"]["target_km2"]
    add("gap", "Cells where thickening raises the survival probability by at least the threshold (default 0.2).",
        "This is where thickening could change the outcome, not where ice survives anyway or is hopeless.",
        "A place to deploy. No ecology, community consent or logistics are included.",
        f"{lab}: band {win['band_km2']:,.0f} km2 ({win['band_km2'] / tgt:.0%} of Real Ice's 1,000,000 km2/yr target).")
    sf = st["sept_freq"]
    m = np.isfinite(sf)
    if m.any():
        flip = float(((sf >= 0.2) & (sf <= 0.8))[m].mean())
        add("sept_freq", "Fraction of Septembers 2012-2025 with ice (concentration >= 15%) in the cell (OSI SAF).",
            "Cells that flip between years are where a nudge could matter; the hindcast tests the band against them.",
            "That ice in that cell came from that cell: ice moves.",
            f"{flip:.0%} of ice-capable cells were ice-covered in 20-80% of Septembers.")
    ex = int((st["excluded"] > 0).sum())
    add("excluded", "Cells within 50 km of a settlement or a hand-drawn shipping corridor (approximate, not ASTD).",
        "Operations near people and ships need consent and coordination.",
        "Safety elsewhere. Indigenous use areas and ringed seal habitat are not in open data: community consent required.",
        f"{ex * grid.CELL_AREA_KM2:,.0f} km2 flagged; {win['band_excl_km2']:,.0f} km2 of the {lab} band falls inside.")
    add("uplift", "P(survive with thickening) minus P(survive without), from 1,000 Monte Carlo draws per cell.",
        "Ranks cells by what thickening changes, not by how thin they are.",
        "That thickening works at scale: the gain prior comes from one 1 km site, 2024/25.",
        f"Gain prior: triangular 0 / {survival.GAIN['mode']:.2f} / {survival.GAIN['max']:.2f} m, scaled by cold.")
    pw = _med(r["p_without"], np.isfinite(r["p_without"]))
    pf = _med(r["p_with"], np.isfinite(r["p_with"]))
    add("p_without", "Probability the cell's ice is thick enough by mid-May to last the summer and stays in the Arctic, with no intervention.",
        "The baseline every thickening scenario is measured against; this is what the hindcast tests.",
        "A forecast for one summer: it uses climatological weather, not the coming season's.",
        pw is not None and f"{lab}: median over ice-covered cells {pw:.2f}.")
    add("p_with", "The same probability with a flooding gain added wherever start ice is at least 0.6 m.",
        "Its gap to P(without) is the uplift that defines the band.",
        "That the gain is achievable everywhere: it is extrapolated from one site by how cold each cell is.",
        pf is not None and f"{lab}: median over ice-covered cells {pf:.2f}.")
    cal = summary.get("calibration")
    if cal:
        add("calibration", "Two-stage growth model at Cambridge Bay, scaled by one factor alpha to the 2024/25 field result.",
            "Ties the growth physics to the only published thickening experiment.",
            "Accuracy at 25 km: one 1 km site, one winter, approximate coordinates.",
            f"Uncalibrated difference {cal['uncalibrated']['diff_m'] * 100:.0f} cm vs paper 32 cm; alpha = {cal['alpha']:.2f}.")
    h = summary.get("hindcast")
    if h:
        a = h["auc_cell_year"]
        add("hindcast", "Does P(survive without) predict where ice is present the next September, 2012-2025?",
            "A band drawn from a model that cannot hindcast would be decoration.",
            "Skill for thickened ice: no thickened ice exists at this scale to test against.",
            f"AUC model {a['model']:.3f} vs thin-ice {a['baseline_thin_ice']:.3f} vs ice-edge distance {a['baseline_edge_distance']:.3f}"
            + (f"; growth-only component {summary['hindcast_diagnosis']['thermo_margin']:.3f} (post hoc)." if summary.get("hindcast_diagnosis") else "."))
    s = summary.get("sensitivity")
    if s and s.get("factors"):
        top = s["factors"][0]
        add("sensitivity", "Band area recomputed with each input pushed low and high, one at a time.",
            "Shows which assumption the answer leans on.",
            "Interactions between inputs; one-at-a-time misses them.",
            f"{top['label']}: band {top['band_km2_low']:,.0f} to {top['band_km2_high']:,.0f} km2 ({s['winter']}/{str(s['winter'] + 1)[-2:]}).")
    add("scale", "Band area against Real Ice's scale plan: energy at 8 MWh/km2, fleet from an assumed drone throughput.",
        "Tests whether the plan's 1,000,000 km2/yr fits where thickening matters.",
        "Feasibility. Drone throughput is not public: the fleet number is an assumption.",
        f"{lab} band x 8 MWh/km2 = {win['band_km2'] * 8 / 1e6:.2f} TWh.")
    return cards
