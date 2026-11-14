import numpy as np
from rasterio.transform import from_origin

from scripts.calibrate_delta import coarse_outer_horizon
from scripts.validate_independent_delta import elevation_offset, outer_horizon


def test_vertical_alignment_recovers_constant_offset() -> None:
    base = np.full((20, 20), 120, dtype=np.float32)
    fine = np.full((400, 400), 117, dtype=np.float32)
    offset, dispersion, count = elevation_offset(
        base, from_origin(0, 1600, 80, 80), fine, from_origin(0, 1600, 4, 4)
    )
    assert offset == 3
    assert dispersion == 0
    assert count >= 100


def test_generalized_outer_horizon_matches_one_meter_baseline() -> None:
    dem = np.zeros((9, 9), dtype=np.float32)
    cols = rows = np.array([4.0])
    observer = np.array([5.0])
    offsets = np.array([0.0])
    expected = coarse_outer_horizon(dem, cols, rows, observer, 80, 80, 160, 720, offsets)
    actual = outer_horizon(dem, cols, rows, observer, 1, 80, 80, 160, offsets)
    np.testing.assert_allclose(actual, expected, atol=1e-6)
