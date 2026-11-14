"""Disk visibility and uninterrupted interval helpers."""

import numpy as np
from numba import njit
from numpy.typing import NDArray

from app.engine.sky import local_direction
from app.settings import EARTH_DELTA_DEG


def sun_disk_fraction(x: NDArray) -> NDArray:
    x = np.clip(np.asarray(x, dtype=float), -1, 1)
    return 1 - (np.arccos(x) - x * np.sqrt(np.maximum(0, 1 - x * x))) / np.pi


@njit
def longest_false_run(values: NDArray) -> int:
    longest = current = 0
    for value in values:
        current = 0 if value else current + 1
        longest = max(longest, current)
    return longest


def horizon_at_azimuth(mask: NDArray, azimuth_deg: NDArray) -> NDArray:
    mask = np.asarray(mask, dtype=float)
    if mask.ndim != 1 or len(mask) == 0 or not np.all(np.isfinite(mask)):
        raise ValueError("A complete finite horizon mask is required.")
    position = (np.asarray(azimuth_deg, dtype=float) % 360) * len(mask) / 360
    lower = np.floor(position).astype(int) % len(mask)
    fraction = position - np.floor(position)
    return mask[lower] * (1 - fraction) + mask[(lower + 1) % len(mask)] * fraction


def site_visibility(latitude: float, longitude: float, mask: NDArray, earth: NDArray,
                    sun: NDArray, rho_earth: NDArray, rho_sun: NDArray,
                    sun_criterion: str, earth_criterion: str) -> dict[str, NDArray]:
    sun_az, sun_el = local_direction(latitude, longitude, sun)
    earth_az, earth_el = local_direction(latitude, longitude, earth)
    sun_horizon = horizon_at_azimuth(mask, sun_az)
    earth_horizon = horizon_at_azimuth(mask, earth_az)
    if np.any(np.asarray(rho_sun) <= 0):
        raise ValueError("Sun angular radius must be positive.")
    x = (sun_el - sun_horizon) / rho_sun
    fraction = sun_disk_fraction(x)
    if sun_criterion == "PARTIAL":
        sun_visible = x > -1
    elif sun_criterion == "HALF_DISK":
        sun_visible = x >= 0
    elif sun_criterion == "FULL":
        sun_visible = x >= 1
    else:
        raise ValueError("Unknown Sun visibility criterion.")
    if earth_criterion == "UPPER_EDGE":
        earth_visible = earth_el + rho_earth > earth_horizon
    elif earth_criterion == "CENTER_DELTA":
        earth_visible = earth_el > earth_horizon + EARTH_DELTA_DEG
    elif earth_criterion == "FULL":
        earth_visible = earth_el - rho_earth > earth_horizon
    else:
        raise ValueError("Unknown Earth visibility criterion.")
    return {"sunAzimuthDeg": sun_az, "sunElevationDeg": sun_el,
            "earthAzimuthDeg": earth_az, "earthElevationDeg": earth_el,
            "sunDiskVisibleFraction": fraction, "sunVisible": sun_visible,
            "earthVisible": earth_visible}
