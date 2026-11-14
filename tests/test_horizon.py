import numpy as np

from app.engine.horizon import horizon_masks
from app.settings import LUNAR_RADIUS_M


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


def test_numba_matches_independent_reference_for_five_points() -> None:
    rng = np.random.default_rng(42)
    dem = rng.uniform(-20, 20, size=(21, 21))
    cols = np.array([5.0, 8.0, 10.0, 12.0, 15.0])
    rows = np.array([5.0, 8.0, 10.0, 12.0, 15.0])
    actual = horizon_masks(dem, cols, rows, 1, 80, 240, 8, np.zeros(5))
    expected = np.empty((5, 8))
    for point in range(5):
        site = dem[int(rows[point]), int(cols[point])]
        for az in range(8):
            angle = az * np.pi / 4
            angles = []
            for step in range(1, 4):
                col = cols[point] + step * np.sin(angle)
                row = rows[point] - step * np.cos(angle)
                left, top = int(np.floor(col)), int(np.floor(row))
                dx, dy = col - left, row - top
                upper = np.interp(dx, [0, 1], dem[top, left:left + 2])
                lower = np.interp(dx, [0, 1], dem[top + 1, left:left + 2])
                height = np.interp(dy, [0, 1], [upper, lower])
                distance = step * 80
                angles.append(np.degrees(np.arctan2(height - site - 1 - distance**2 / (2 * LUNAR_RADIUS_M), distance)))
            expected[point, az] = max(angles)
    np.testing.assert_allclose(actual, expected, atol=1e-5)
