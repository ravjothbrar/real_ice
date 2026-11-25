import numpy as np
from pipeline import grid

def test_pole_at_centre():
    i, j = grid.lonlat_to_ij(0.0, 90.0)
    assert abs(i - (grid.CROP / 2 - 0.5)) < 1e-6 and abs(j - (grid.CROP / 2 - 0.5)) < 1e-6

def test_roundtrip():
    i, j = grid.lonlat_to_ij(grid.LON[10, 20], grid.LAT[10, 20])
    assert np.allclose([i, j], [10, 20], atol=1e-6)
