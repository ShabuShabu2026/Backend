from pathlib import Path

import numpy as np
import pytest
from pyproj import CRS

from app.engine.grid import build_grid
from app.engine.terrain import DatasetUnavailableError
from scripts.precompute_grid import precompute


def test_grid_is_aligned_and_stable() -> None:
    crs = CRS.from_proj4("+proj=stere +lat_0=-90 +lon_0=0 +R=1737400 +units=m")
    grid = build_grid(crs, spacing=10000)
    assert np.any((grid.x == 0) & (grid.y == 0))
    assert grid.ids[0] == "LSP-0001"
    assert np.all(grid.lat <= -85 + 1e-9)
    assert np.all((-180 <= grid.lon) & (grid.lon < 180))
    assert np.array_equal(grid.ids, build_grid(crs, spacing=10000).ids)


def test_missing_raster_does_not_create_artifact(tmp_path: Path) -> None:
    output = tmp_path / "artifacts/grid.npz"
    with pytest.raises(DatasetUnavailableError, match="Required raster is missing"):
        precompute(tmp_path, output)
    assert not output.exists()
