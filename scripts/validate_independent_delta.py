"""Compare base horizons with LROC stereo DTMs; no global calibration implied."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from numba import njit, prange
from pyproj import CRS, Transformer
from scipy.ndimage import map_coordinates

from app.engine.horizon import _bilinear, horizon_masks
from app.settings import HORIZON_AZIMUTH_COUNT, LUNAR_RADIUS_M
from scripts.calibrate_delta import matching_projection_parameters, sample_interior


@njit(parallel=True)
def outer_horizon(dem, cols, rows, observers, height, pixel, radius, max_distance, offsets):
    result = np.full((len(cols), HORIZON_AZIMUTH_COUNT), np.nan, dtype=np.float32)
    for i in prange(len(cols)):
        for az in range(HORIZON_AZIMUTH_COUNT):
            angle = 2 * math.pi * az / HORIZON_AZIMUTH_COUNT + offsets[i]
            best = -math.inf
            for step in range(int(radius / pixel) + 1, int(max_distance / pixel) + 1):
                distance = step * pixel
                elevation = _bilinear(dem, cols[i] + step * math.sin(angle), rows[i] - step * math.cos(angle))
                if math.isfinite(elevation):
                    dz = elevation - observers[i] - height - distance * distance / (2 * LUNAR_RADIUS_M)
                    best = max(best, math.atan2(dz, distance))
            if best != -math.inf:
                result[i, az] = math.degrees(best)
    return result


def elevation_offset(coarse, coarse_transform, fine, fine_transform):
    """Estimate a constant vertical offset using dispersed valid fine pixels."""
    step = max(1, round(80 / fine_transform.a))
    rows, cols = np.mgrid[step // 2:fine.shape[0]:step, step // 2:fine.shape[1]:step]
    rows, cols = rows.ravel(), cols.ravel()
    values = fine[rows, cols]
    x = fine_transform.c + (cols + 0.5) * fine_transform.a
    y = fine_transform.f - (rows + 0.5) * fine_transform.a
    bc = (x - coarse_transform.c) / coarse_transform.a - 0.5
    br = (coarse_transform.f - y) / coarse_transform.a - 0.5
    valid = np.isfinite(values) & (bc >= 0) & (br >= 0) & (bc < coarse.shape[1] - 1) & (br < coarse.shape[0] - 1)
    base = map_coordinates(coarse, [br[valid], bc[valid]], order=1, mode="constant", cval=np.nan)
    difference = base - values[valid]
    difference = difference[np.isfinite(difference)]
    if len(difference) < 100:
        raise ValueError("Insufficient common elevations for vertical alignment.")
    offset = float(np.median(difference))
    return offset, float(1.4826 * np.median(np.abs(difference - offset))), len(difference)


def run(paths: list[Path], data_dir: Path, artifact_dir: Path, output: Path, radius: float) -> dict:
    with np.load(artifact_dir / "grid.npz", allow_pickle=False) as grid:
        x, y, lat, lon, ids = (grid[k].copy() for k in ("x", "y", "lat", "lon", "ids"))
    with rasterio.open(data_dir / "dem/LDEM_80S_80MPP_ADJ.TIF") as source:
        transform, crs = source.transform, CRS.from_wkt(source.crs.to_wkt())
        coarse = source.read(1, masked=True).astype(np.float32).filled(np.nan)
    projection = Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)
    base_masks = {h: np.load(artifact_dir / f"horizon_{h}m.npy", mmap_mode="r", allow_pickle=False)
                  for h in (1, 5, 10)}
    reports = []
    pooled = {h: [] for h in base_masks}
    seen = set()
    for path in paths:
        with rasterio.open(path) as source:
            t = source.transform
            if not source.crs or not matching_projection_parameters(crs, CRS.from_wkt(source.crs.to_wkt())):
                raise ValueError(f"Incompatible projection: {path}")
            if t.b or t.d or t.e != -t.a or t.a <= 0:
                raise ValueError(f"Invalid raster transform: {path}")
            fine = source.read(1, masked=True).astype(np.float32).filled(np.nan)
        cols, rows = (x - t.c) / t.a - 0.5, (t.f - y) / t.a - 0.5
        eligible = np.flatnonzero(sample_interior(fine, cols, rows, t.a, radius))
        selected = np.array([i for i in eligible if str(ids[i]) not in seen], dtype=int)
        if len(selected) == 0:
            reports.append({"name": path.name, "eligible": len(eligible), "selected": 0})
            continue
        seen.update(map(str, ids[selected]))
        offset, nmad, count = elevation_offset(coarse, transform, fine, t)
        cc, rr = (x[selected] - transform.c) / transform.a - 0.5, (transform.f - y[selected]) / transform.a - 0.5
        nx, ny = projection.transform(lon[selected], lat[selected] + 0.00001)
        offsets = np.arctan2(nx - x[selected], ny - y[selected])
        observers = np.array([_bilinear(fine, c, r) + offset for c, r in zip(cols[selected], rows[selected], strict=True)])
        with path.open("rb") as f:
            sha256 = hashlib.file_digest(f, "sha256").hexdigest()
        item = {"name": path.name, "bytes": path.stat().st_size, "sha256": sha256,
                "pixelM": t.a, "eligible": len(eligible), "selected": len(selected),
                "ids": ids[selected].tolist(), "verticalOffsetM": offset, "verticalNMADM": nmad,
                "verticalPairs": count, "heights": {}}
        for height in base_masks:
            local = horizon_masks(fine, cols[selected], rows[selected], height, t.a, radius,
                                  HORIZON_AZIMUTH_COUNT, offsets)
            outer = outer_horizon(coarse, cc, rr, observers, height, transform.a, radius, 100_000, offsets)
            difference = np.maximum(local, outer) - np.asarray(base_masks[height][selected])
            if not np.isfinite(difference).all():
                raise ValueError(f"Incomplete horizon coverage: {path}")
            pooled[height].append(difference.astype(np.float64))
            item["heights"][str(height)] = {"signedP95Deg": float(np.percentile(difference, 95)),
                                           "fractionAbove025": float(np.mean(difference > 0.25))}
        reports.append(item)
        print(f"{path.name}: {len(selected)} distinct sites, offset {offset:.2f} m", flush=True)
    overall = {}
    for height, arrays in pooled.items():
        if arrays:
            diff = np.concatenate(arrays)
            overall[str(height)] = {"locations": len(diff), "signedP95Deg": float(np.percentile(diff, 95)),
                                    "absoluteP95Deg": float(np.percentile(np.abs(diff), 95)),
                                    "fractionAbove025": float(np.mean(diff > 0.25))}
    result = {"method": "LROC stereo local horizon plus 80 m DEM outside local disk; median vertical offset per tile",
              "radiusM": radius, "sites": reports, "overall": overall}
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--artifact-dir", type=Path, default=Path("artifacts"))
    parser.add_argument("--radius", type=float, default=250)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.radius <= 0:
        parser.error("radius must be positive")
    report = run(args.paths, args.data_dir, args.artifact_dir, args.output, args.radius)
    print(json.dumps(report["overall"], indent=2))


if __name__ == "__main__":
    main()
