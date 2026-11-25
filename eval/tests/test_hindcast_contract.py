"""The hindcast must exist and be reported before anything is claimed (brief 6.3)."""
import json, pathlib, pytest
ROOT = pathlib.Path(__file__).resolve().parents[2]
H = ROOT / "data" / "interim" / "hindcast.json"

@pytest.mark.skipif(not H.exists(), reason="run `make hindcast` first")
def test_hindcast_reports_both_baselines():
    h = json.loads(H.read_text())
    for k in ("model", "baseline_thin_ice", "baseline_edge_distance"):
        assert k in h["spearman_vs_presence"] and k in h["auc_cell_year"]
    assert "beats_both" in h
