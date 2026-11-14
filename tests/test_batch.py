import numpy as np
import pytest

from app.engine.batch import visibility_windows
from app.engine.visibility import longest_false_run, site_visibility
from app.settings import LUNAR_RADIUS_M


@pytest.mark.parametrize("sun_mode,sun_name", [(0, "PARTIAL"), (1, "HALF_DISK"), (2, "FULL")])
@pytest.mark.parametrize("earth_mode,earth_name", [(0, "UPPER_EDGE"), (1, "CENTER_DELTA"), (2, "FULL")])
def test_batch_matches_single_site_visibility(sun_mode, sun_name, earth_mode, earth_name) -> None:
    times = np.arange(72)
    angle = times * (2 * np.pi / 24)
    sun = np.column_stack((LUNAR_RADIUS_M + 1000 * np.sin(angle), np.full(72, 100_000), np.zeros(72)))
    earth = np.column_stack((LUNAR_RADIUS_M + 500 * np.cos(angle), np.full(72, 100_000), np.zeros(72)))
    radii_sun = np.full(72, 0.25)
    radii_earth = np.full(72, 1.0)
    masks = np.tile(np.linspace(-0.1, 0.1, 720), (2, 1))
    lat, lon = np.array([0.0, -0.001]), np.array([0.0, 0.001])
    metrics, invalid = visibility_windows(lat, lon, masks, earth, sun, radii_earth, radii_sun,
                                          24, 1, sun_mode, earth_mode)
    assert not invalid.any()
    for i in range(2):
        actual = site_visibility(lat[i], lon[i], masks[i], earth, sun, radii_earth, radii_sun,
                                 sun_name, earth_name)
        for day in range(3):
            window = slice(24 * day, 24 * (day + 1))
            expected = [np.mean(actual["sunVisible"][window]), np.mean(actual["earthVisible"][window]),
                        longest_false_run(actual["sunVisible"][window]),
                        longest_false_run(actual["earthVisible"][window]),
                        np.count_nonzero(actual["sunDiskVisibleFraction"][window] < 0.5)]
            np.testing.assert_allclose(metrics[i, day], expected)
