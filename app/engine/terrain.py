"""Sample terrain rasters without modifying the source datasets."""

from pathlib import Path

import numpy as np
import rasterio
from numpy.typing import NDArray
from pyproj import CRS, Transformer


class DatasetUnavailableError(RuntimeError):
    """A required input dataset is missing or cannot be used."""


def sample_raster(path: Path, x: NDArray, y: NDArray, source_crs: CRS) -> NDArray:
    if not path.is_file():
        raise DatasetUnavailableError(f"Required raster is missing: {path}")
    with rasterio.open(path) as raster:
        if raster.crs is None:
            raise DatasetUnavailableError(f"Raster has no CRS: {path}")
        transformer = Transformer.from_crs(source_crs, raster.crs, always_xy=True)
        xs, ys = transformer.transform(x, y)
        samples = list(raster.sample(zip(xs, ys, strict=True), indexes=1, masked=True))
        values = np.ma.array(samples).reshape(-1).filled(np.nan)
        return np.asarray(values, dtype=np.float64)
