"""Build pole-aligned grids in the source DEM coordinate system."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from pyproj import CRS, Transformer

from app.settings import GRID_LATITUDE_LIMIT_DEG, GRID_SPACING_M


@dataclass(frozen=True)
class Grid:
    ids: NDArray
    x: NDArray
    y: NDArray
    lat: NDArray
    lon: NDArray


def build_grid(crs: CRS, spacing: int = GRID_SPACING_M) -> Grid:
    if spacing <= 0:
        raise ValueError("Grid spacing must be positive.")
    geographic = crs.geodetic_crs
    if geographic is None:
        raise ValueError("DEM CRS has no geographic base CRS.")
    forward = Transformer.from_crs(geographic, crs, always_xy=True)
    inverse = Transformer.from_crs(crs, geographic, always_xy=True)
    x_limit, y_limit = forward.transform(0, GRID_LATITUDE_LIMIT_DEG)
    radius = float(np.hypot(x_limit, y_limit))
    count = int(np.ceil(radius / spacing))
    axis = np.arange(-count, count + 1, dtype=np.int64) * spacing
    x, y = np.meshgrid(axis, axis[::-1])
    keep = x * x + y * y <= radius * radius
    xs, ys = x[keep], y[keep]
    lon, lat = inverse.transform(xs, ys)
    lon = (np.asarray(lon) + 180) % 360 - 180
    lat = np.asarray(lat)
    valid = np.isfinite(lat) & (lat <= GRID_LATITUDE_LIMIT_DEG + 1e-9)
    xs, ys, lon, lat = xs[valid], ys[valid], lon[valid], lat[valid]
    ids = np.array([f"LSP-{i:04d}" for i in range(1, len(xs) + 1)])
    return Grid(ids=ids, x=xs, y=ys, lat=lat, lon=lon)
