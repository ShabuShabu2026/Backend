import numpy as np

from app.engine.sky import local_direction
from app.engine.visibility import (
    horizon_at_azimuth,
    longest_false_run,
    site_visibility,
    sun_disk_fraction,
)
from app.settings import LUNAR_RADIUS_M


def test_sun_fraction_and_darkness() -> None:
    np.testing.assert_allclose(sun_disk_fraction(np.array([-1, 0, 1])), [0, 0.5, 1])
    assert longest_false_run(np.array([False, False, True, False])) == 2


def test_local_body_direction() -> None:
    site = np.array([LUNAR_RADIUS_M, 0, 0])
    _, elevation = local_direction(0, 0, site + [1000, 0, 0])
    assert np.isclose(elevation, 90)
    azimuth, elevation = local_direction(0, 0, site + [0, 1000, 0])
    assert np.isclose(azimuth, 90)
    assert np.isclose(elevation, 0)


def test_horizon_wrap_and_visibility_criteria() -> None:
    np.testing.assert_allclose(horizon_at_azimuth(np.array([0, 10, 20, 30]), np.array([315, 360])), [15, 0])
    site = np.array([LUNAR_RADIUS_M, 0, 0])
    body = np.array([site + [0, 1000, 0]])
    result = site_visibility(0, 0, np.zeros(4), body, body, np.array([1.0]), np.array([1.0]),
                             "HALF_DISK", "UPPER_EDGE")
    assert result["sunVisible"].tolist() == [True]
    assert result["earthVisible"].tolist() == [True]
    assert np.isclose(result["sunDiskVisibleFraction"][0], 0.5)
