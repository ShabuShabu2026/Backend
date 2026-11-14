import logging
from pathlib import Path
from typing import Any

import rasterio
from rasterio.errors import RasterioError

logger = logging.getLogger(__name__)


def load_metadata(paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, path in paths.items():
        if not path.is_file():
            result[name] = {"exists": False}
            continue
        try:
            with rasterio.open(path) as raster:
                result[name] = {
                    "exists": True,
                    "shape": [raster.height, raster.width],
                    "res": list(raster.res),
                    "dtype": raster.dtypes[0],
                    "crs": str(raster.crs) if raster.crs else None,
                }
        except (RasterioError, OSError) as exc:
            logger.warning("Cannot open raster %s: %s", path, exc)
            result[name] = {"exists": True, "error": "Unable to read raster metadata"}
    return result
