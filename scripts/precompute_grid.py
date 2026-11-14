"""Build base-grid terrain samples as an offline artifact."""

import argparse
from pathlib import Path

import numpy as np
import rasterio
from pyproj import CRS

from app.engine.grid import build_grid
from app.engine.terrain import DatasetUnavailableError, sample_raster


def precompute(data_dir: Path, output: Path) -> int:
    dem = data_dir / "dem/LDEM_80S_80MPP_ADJ.TIF"
    slope = data_dir / "terrain/LDSM_80S_80MPP_ADJ.TIF"
    roughness = data_dir / "terrain/LDRM_80S_50MPP_ADJ_ROUGH_100M.TIF"
    for path in (dem, slope, roughness):
        if not path.is_file():
            raise DatasetUnavailableError(f"Required raster is missing: {path}")
    with rasterio.open(dem) as dataset:
        if dataset.crs is None:
            raise DatasetUnavailableError(f"DEM has no CRS: {dem}")
        crs = CRS.from_wkt(dataset.crs.to_wkt())
    grid = build_grid(crs)
    arrays = {name: sample_raster(path, grid.x, grid.y, crs) for name, path in (
        ("elevation", dem), ("slope", slope), ("roughness", roughness),
    )}
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, ids=grid.ids, x=grid.x, y=grid.y, lat=grid.lat,
                        lon=grid.lon, crs=crs.to_wkt(), **arrays)
    return len(grid.ids)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/grid.npz"))
    args = parser.parse_args()
    try:
        count = precompute(args.data_dir, args.output)
    except (DatasetUnavailableError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(f"Saved {count} grid points to {args.output}")


if __name__ == "__main__":
    main()
