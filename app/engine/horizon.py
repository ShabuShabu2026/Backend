"""Horizon ray marching on a north-up, square-pixel lunar DEM."""

import math

import numpy as np
from numba import njit, prange

from app.settings import LUNAR_RADIUS_M


@njit
def _bilinear(dem: np.ndarray, col: float, row: float) -> float:
    c0, r0 = math.floor(col), math.floor(row)
    if c0 < 0 or r0 < 0 or c0 + 1 >= dem.shape[1] or r0 + 1 >= dem.shape[0]:
        return np.nan
    a, b = col - c0, row - r0
    return (dem[r0, c0] * (1 - a) * (1 - b) + dem[r0, c0 + 1] * a * (1 - b)
            + dem[r0 + 1, c0] * (1 - a) * b + dem[r0 + 1, c0 + 1] * a * b)


@njit(parallel=True)
def horizon_masks(dem: np.ndarray, cols: np.ndarray, rows: np.ndarray, height_m: float,
                  pixel_size_m: float, max_distance_m: float,
                  azimuth_count: int, north_offsets_rad: np.ndarray) -> np.ndarray:
    """Return elevation angles in degrees, with azimuth clockwise from north."""
    result = np.full((len(cols), azimuth_count), np.nan, dtype=np.float32)
    for i in prange(len(cols)):
        site = _bilinear(dem, cols[i], rows[i])
        if not np.isfinite(site):
            continue
        for az in range(azimuth_count):
            angle = 2 * math.pi * az / azimuth_count + north_offsets_rad[i]
            best = -math.inf
            for step in range(1, int(max_distance_m / pixel_size_m) + 1):
                distance = step * pixel_size_m
                col = cols[i] + step * math.sin(angle)
                row = rows[i] - step * math.cos(angle)
                elevation = _bilinear(dem, col, row)
                if np.isfinite(elevation):
                    dz = elevation - site - height_m - distance * distance / (2 * LUNAR_RADIUS_M)
                    best = max(best, math.atan2(dz, distance))
            if best != -math.inf:
                result[i, az] = best * 180 / math.pi
    return result
