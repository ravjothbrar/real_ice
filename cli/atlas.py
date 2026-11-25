"""atlas: the command-line face of the exported atlas (reads web/public/data).

  python cli/atlas.py cell 69.05N -105.10E [--winter 2024]
  python cli/atlas.py band --winter 2024 --threshold 0.2
  python cli/atlas.py scale --km2 1000000 [--throughput 0.1]
"""
import argparse, json, pathlib, sys
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline import grid, scale as S  # noqa: E402

D = ROOT / "web" / "public" / "data"


def load(w=None):
    if not (D / "manifest.json").exists():
        sys.exit("No data. Run: make export")
    m = json.loads((D / "manifest.json").read_text())
    N = m["n_cells"]
    cells = np.fromfile(D / "cells.bin", "<u2").reshape(N, 2)
    w = w or max(x["w"] for x in m["winters"] if not x["partial"])
    raw = np.fromfile(D / f"winter-{w}.bin", np.uint8).reshape(-1, N)
    st = np.fromfile(D / "static.bin", np.uint8).reshape(-1, N)
    dec = lambda b, k: np.where(b == 255, np.nan, b * m["layers"][k]["scale"] + m["layers"][k]["offset"])
    L = {k: dec(raw[i], k) for i, k in enumerate(m["winter_layers"])}
    L.update({k: dec(st[i], k) for i, k in enumerate(m["static_layers"])})
    return m, cells, L, w


def coord(s):
    v = float(s.rstrip("NSEWnsew")); return -v if s[-1:] in "SWsw" else v


def classify(L, thr):
    s = json.loads((D / "summary.json").read_text())["thresholds"]
    c = np.zeros(len(L["uplift"]), int)
    c[L["p_with"] <= s["hopeless_p_with"]] = 3
    c[L["uplift"] >= thr] = 2
    c[(L["blocked"] >= s["blocked_frac"]) & (L["p_without"] < s["survives_p_without"])] = 4
    c[L["p_without"] >= s["survives_p_without"]] = 1
    return c


def main():
    ap = argparse.ArgumentParser(prog="atlas")
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("cell"); c.add_argument("lat"); c.add_argument("lon"); c.add_argument("--winter", type=int)
    b = sp.add_parser("band"); b.add_argument("--winter", type=int); b.add_argument("--threshold", type=float, default=0.2)
    s = sp.add_parser("scale"); s.add_argument("--km2", type=float, default=1e6); s.add_argument("--throughput", type=float, default=0.1)
    a = ap.parse_args()
    if a.cmd == "scale":
        r = S.scale(a.km2, a.throughput)
        print(f"area {r['area_km2']:,.0f} km2 | energy {r['energy_twh']:.2f} TWh at 8 MWh/km2 (Ocean Visions)")
        print(f"fleet {r['fleet']:,.0f} drones | {r['fleet_label']}")
        return
    m, cells, L, w = load(a.winter)
    if a.cmd == "band":
        cls = classify(L, a.threshold)
        names = ["below threshold", "survives anyway", "BAND", "hopeless", "blocked (<0.6 m)"]
        print(f"winter {w}/{str(w+1)[-2:]}  threshold {a.threshold}")
        for k, n in enumerate(names):
            print(f"  {n:18s} {(cls == k).sum() * grid.CELL_AREA_KM2:>12,.0f} km2")
        return
    i, j = grid.lonlat_to_ij(coord(a.lon), coord(a.lat))
    d = (cells[:, 0] - i) ** 2 + (cells[:, 1] - j) ** 2
    k = int(np.argmin(d))
    print(f"nearest ice-capable cell ({np.sqrt(d[k]) * 25:.0f} km away)  i={cells[k,0]} j={cells[k,1]}  winter {w}/{str(w+1)[-2:]}")
    for name, v in L.items():
        if np.isfinite(v[k]):
            print(f"  {m['layers'][name]['title']:45s} {v[k]:.3f} {m['layers'][name]['unit']}")


if __name__ == "__main__":
    main()
