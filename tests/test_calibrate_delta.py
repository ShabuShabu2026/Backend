import numpy as np
import pytest
from pyproj import CRS

from app.settings import LUNAR_RADIUS_M
from scripts.calibrate_delta import (
    coarse_outer_horizon,
    matching_projection_parameters,
    sample_interior,
    summarize_differences,
)


def test_calibration_uses_only_fully_covered_locations() -> None:
    dem = np.zeros((21, 21), dtype=np.float32)
    dem[5, 5] = np.nan
    cols = np.array([10.0, 1.0, 5.0])
    rows = np.array([10.0, 1.0, 5.0])
    assert sample_interior(dem, cols, rows, 5, 10).tolist() == [True, False, False]


def test_difference_summary_and_missing_values() -> None:
    coarse = np.array([[0, 2], [1, 4]])
    fine = np.array([[1, 0], [2, 7]])
    result = summarize_differences(coarse, fine)
    assert result["siteCount"] == 2
    assert result["azimuthCount"] == 2
    assert result["absoluteP95Deg"] == pytest.approx(2.85)
    with pytest.raises(ValueError, match="missing"):
        summarize_differences(coarse, np.full((2, 2), np.nan))


def test_outer_horizon_uses_fine_observer_elevation() -> None:
    dem = np.zeros((9, 9), dtype=np.float32)
    result = coarse_outer_horizon(dem, np.array([4.0]), np.array([4.0]), np.array([5.0]),
                                  80, 80, 160, 4, np.zeros(1))
    expected = np.degrees(np.arctan2(-6 - 160**2 / (2 * LUNAR_RADIUS_M), 160))
    np.testing.assert_allclose(result, expected, atol=1e-6)


def test_projection_comparison_rejects_different_parameters() -> None:
    base = CRS.from_proj4("+proj=stere +lat_0=-90 +lon_0=0 +R=1737400 +units=m")
    same = CRS.from_wkt(base.to_wkt())
    shifted = CRS.from_proj4("+proj=stere +lat_0=-90 +lon_0=10 +R=1737400 +units=m")
    assert matching_projection_parameters(base, same)
    assert not matching_projection_parameters(base, shifted)
