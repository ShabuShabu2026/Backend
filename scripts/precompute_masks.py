"""Precompute horizon masks from the DEM and an existing base grid."""

import argparse
import time
from pathlib import Path

import numpy as np
import rasterio
from pyproj import CRS, Transformer

from app.engine.horizon import horizon_masks
from app.settings import (
    HEIGHTS_M,
    HORIZON_AZIMUTH_COUNT,
    HORIZON_COMPARISON_DISTANCE_M,
    HORIZON_COMPARISON_SAMPLE_COUNT,
    HORIZON_MAX_DISTANCE_M,
)


def run(grid_path: Path, dem_path: Path, output_dir: Path) -> None:
    if not grid_path.is_file():
        raise FileNotFoundError(f"Required grid artifact is missing: {grid_path}")
    if not dem_path.is_file():
        raise FileNotFoundError(f"Required DEM is missing: {dem_path}")
    with np.load(grid_path, allow_pickle=False) as grid:
        x, y, lon, lat = (grid[k].copy() for k in ("x", "y", "lon", "lat"))
    with rasterio.open(dem_path) as source:
        transform = source.transform
        if transform.b != 0 or transform.d != 0 or transform.a <= 0 or transform.e != -transform.a:
            raise ValueError("DEM must have square north-up pixels.")
        if source.crs is None:
            raise ValueError("DEM CRS is missing.")
        dem = source.read(1, masked=True).astype(np.float32).filled(np.nan)
        crs = CRS.from_wkt(source.crs.to_wkt())
    project = Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)
    north_x, north_y = project.transform(lon, np.minimum(lat + 0.00001, 0))
    offsets = np.arctan2(north_x - x, north_y - y)
    cols = (x - transform.c) / transform.a - 0.5
    rows = (transform.f - y) / transform.a - 0.5
    output_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    for height in HEIGHTS_M:
        output = np.lib.format.open_memmap(output_dir / f"horizon_{height}m.npy", mode="w+",
                                          dtype="float32", shape=(len(x), HORIZON_AZIMUTH_COUNT))
        for i in range(0, len(x), 256):
            sl = slice(i, min(i + 256, len(x)))
            output[sl] = horizon_masks(dem, cols[sl], rows[sl], height, transform.a,
                                       HORIZON_MAX_DISTANCE_M, HORIZON_AZIMUTH_COUNT, offsets[sl])
        output.flush()
        del output
    count = min(len(x), HORIZON_COMPARISON_SAMPLE_COUNT)
    indices = np.random.default_rng(0).choice(len(x), count, replace=False)
    short = horizon_masks(dem, cols[indices], rows[indices], HEIGHTS_M[0], transform.a,
                          HORIZON_COMPARISON_DISTANCE_M, HORIZON_AZIMUTH_COUNT, offsets[indices])
    long = np.load(output_dir / f"horizon_{HEIGHTS_M[0]}m.npy", mmap_mode="r")[indices]
    print(f"Maximum 100 km / 50 km difference: {np.nanmax(np.abs(long - short)):.6f} degrees")
    print(f"Elapsed: {time.perf_counter() - start:.2f} seconds")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid", type=Path, default=Path("artifacts/grid.npz"))
    parser.add_argument("--dem", type=Path, default=Path("data/dem/LDEM_80S_80MPP_ADJ.TIF"))
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    try:
        run(args.grid, args.dem, args.output_dir)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
