"""Parallel base-grid visibility aggregation without storing hourly matrices."""

import math

import numpy as np
from numba import njit, prange

from app.settings import EARTH_DELTA_DEG, LUNAR_RADIUS_M


@njit
def _position(body, ux, uy, uz, ex, ey, nx, ny, nz):
    dx = body[0] - LUNAR_RADIUS_M * ux
    dy = body[1] - LUNAR_RADIUS_M * uy
    dz = body[2] - LUNAR_RADIUS_M * uz
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length == 0:
        return math.nan, math.nan
    elevation = math.degrees(math.asin(min(1.0, max(-1.0, (dx * ux + dy * uy + dz * uz) / length))))
    azimuth = math.degrees(math.atan2(dx * ex + dy * ey, dx * nx + dy * ny + dz * nz)) % 360.0
    return azimuth, elevation


@njit
def _mask_value(mask, azimuth):
    pos = (azimuth % 360.0) * len(mask) / 360.0
    lower = math.floor(pos) % len(mask)
    fraction = pos - math.floor(pos)
    return mask[lower] * (1 - fraction) + mask[(lower + 1) % len(mask)] * fraction


@njit(parallel=True)
def visibility_windows(latitudes, longitudes, masks, earth, sun, rho_earth, rho_sun,
                       stay_hours, search_days, sun_mode, earth_mode):
    """Return per-site/day ratios, longest runs and continuous Sun violations."""
    points, span = len(latitudes), len(earth)
    days = 2 * search_days + 1
    metrics = np.empty((points, days, 5), dtype=np.float64)
    invalid = np.zeros(points, dtype=np.bool_)
    for i in prange(points):
        lat, lon = math.radians(latitudes[i]), math.radians(longitudes[i])
        ux, uy, uz = math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)
        ex, ey = -math.sin(lon), math.cos(lon)
        nx, ny, nz = -math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat)
        sun_visible = np.empty(span, dtype=np.bool_)
        earth_visible = np.empty(span, dtype=np.bool_)
        sun_half = np.empty(span, dtype=np.bool_)
        for t in range(span):
            saz, sel = _position(sun[t], ux, uy, uz, ex, ey, nx, ny, nz)
            eaz, eel = _position(earth[t], ux, uy, uz, ex, ey, nx, ny, nz)
            if not math.isfinite(saz) or not math.isfinite(eaz) or rho_sun[t] <= 0:
                invalid[i] = True
                break
            sh = _mask_value(masks[i], saz)
            eh = _mask_value(masks[i], eaz)
            if not math.isfinite(sh) or not math.isfinite(eh):
                invalid[i] = True
                break
            sun_x = (sel - sh) / rho_sun[t]
            sun_half[t] = sun_x >= 0
            if sun_mode == 0:
                sun_visible[t] = sun_x > -1
            elif sun_mode == 1:
                sun_visible[t] = sun_half[t]
            else:
                sun_visible[t] = sun_x >= 1
            if earth_mode == 0:
                earth_visible[t] = eel + rho_earth[t] > eh
            elif earth_mode == 1:
                earth_visible[t] = eel > eh + EARTH_DELTA_DEG
            else:
                earth_visible[t] = eel - rho_earth[t] > eh
        if invalid[i]:
            continue
        for day in range(days):
            sun_count = earth_count = dark_run = blackout_run = dark_max = blackout_max = violations = 0
            for t in range(day * 24, day * 24 + stay_hours):
                if sun_visible[t]:
                    sun_count += 1
                    dark_run = 0
                else:
                    dark_run += 1
                    dark_max = max(dark_max, dark_run)
                if earth_visible[t]:
                    earth_count += 1
                    blackout_run = 0
                else:
                    blackout_run += 1
                    blackout_max = max(blackout_max, blackout_run)
                if not sun_half[t]:
                    violations += 1
            metrics[i, day, 0] = sun_count / stay_hours
            metrics[i, day, 1] = earth_count / stay_hours
            metrics[i, day, 2] = dark_max
            metrics[i, day, 3] = blackout_max
            metrics[i, day, 4] = violations
    return metrics, invalid
