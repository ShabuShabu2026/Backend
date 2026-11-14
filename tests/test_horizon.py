import numpy as np

from app.engine.horizon import horizon_masks


def test_wall_due_north_and_flat_curvature() -> None:
    dem = np.zeros((9, 9), dtype=np.float64)
    cols = np.array([4.0])
    rows = np.array([4.0])
    flat = horizon_masks(dem, cols, rows, 0, 80, 160, 4, np.zeros(1))
    assert np.all(flat < 0)
    dem[2, 4] = 80
    wall = horizon_masks(dem, cols, rows, 0, 80, 160, 4, np.zeros(1))
    assert 26 < wall[0, 0] < 27
    assert wall[0, 1] < 0
