import pandas as pd, pathlib
from pipeline import grid
L = pd.read_csv(pathlib.Path(__file__).resolve().parents[1] / "labels.csv")

def test_labels_shape():
    assert len(L) == 25
    assert set(L.label) == {"likely-survives-anyway", "marginal", "likely-melts-out", "export-zone"}
    assert L.source.str.len().min() > 10

def test_labels_on_grid():
    i, j = grid.lonlat_to_ij(L.lon.values, L.lat.values)
    assert ((i >= 0) & (i < grid.CROP) & (j >= 0) & (j < grid.CROP)).all()
