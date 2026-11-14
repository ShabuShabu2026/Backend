"""Moon-fixed local direction calculations."""

from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from app.settings import LUNAR_RADIUS_M


def load_sky_table(path: Path) -> dict[str, NDArray]:
    if not path.is_file():
        raise FileNotFoundError(f"Required sky table is missing: {path}")
    with np.load(path, allow_pickle=False) as data:
        return {name: data[name] for name in ("time", "r_earth", "r_sun", "rho_sun", "rho_earth")}


def local_direction(latitude_deg: float, longitude_deg: float, body: NDArray) -> tuple[NDArray, NDArray]:
    lat, lon = np.deg2rad([latitude_deg, longitude_deg])
    up = np.array([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])
    east = np.array([-np.sin(lon), np.cos(lon), 0.0])
    north = np.cross(up, east)
    direction = np.asarray(body) - LUNAR_RADIUS_M * up
    length = np.linalg.norm(direction, axis=-1)
    if np.any(length == 0):
        raise ValueError("Body position must not coincide with the site.")
    elevation = np.rad2deg(np.arcsin(np.clip(direction @ up / length, -1, 1)))
    azimuth = np.rad2deg(np.arctan2(direction @ east, direction @ north)) % 360
    return azimuth, elevation
