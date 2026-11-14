"""Compare 80 m and 5 m horizon masks over a common local coverage radius."""

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np
import rasterio
from numba import njit, prange
from pyproj import CRS, Transformer
from scipy.ndimage import distance_transform_edt

from app.engine.horizon import _bilinear, horizon_masks
from app.settings import (
    CALIBRATION_HEIGHT_M,
    CALIBRATION_LOCAL_RADIUS_M,
    CALIBRATION_RANDOM_SEED,
    CALIBRATION_SAMPLES_PER_SITE,
    HORIZON_AZIMUTH_COUNT,
    HORIZON_MAX_DISTANCE_M,
    LUNAR_RADIUS_M,
)

SITE_DEMS = (
    Path("Site01/Site01_final_adj_5mpp_surf.tif"),
    Path("Site04/Site04_final_adj_5mpp_surf.tif"),
    Path("Site07/Site07_final_adj_5mpp_surf.tif"),
    Path("Site11/Site11_final_adj_5mpp_surf.tif"),
)


def sample_interior(dem: np.ndarray, cols: np.ndarray, rows: np.ndarray,
                    pixel_size: float, radius: float) -> np.ndarray:
    """Find locations whose full comparison disk contains valid raster pixels."""
    valid = np.isfinite(dem)
    padded = np.pad(valid, 1, constant_values=False)
    distance = distance_transform_edt(padded, sampling=pixel_size)[1:-1, 1:-1]
    c, r = np.floor(cols).astype(np.int64), np.floor(rows).astype(np.int64)
    inside = (c >= 0) & (c < dem.shape[1]) & (r >= 0) & (r < dem.shape[0])
    result = np.zeros(len(cols), dtype=bool)
    result[inside] = distance[r[inside], c[inside]] >= radius + 2 * pixel_size
    return result


def summarize_differences(coarse: np.ndarray, fine: np.ndarray) -> dict[str, float | int]:
    if coarse.shape != fine.shape:
        raise ValueError("Compared masks must have the same dimensions.")
    difference = np.asarray(fine, dtype=float) - np.asarray(coarse, dtype=float)
    if not np.isfinite(difference).all() or difference.size == 0:
        raise ValueError("Compared masks contain missing values or no samples.")
    return {"siteCount": int(difference.shape[0]), "azimuthCount": int(difference.shape[1]),
            "signedP95Deg": float(np.percentile(difference, 95)),
            "absoluteP95Deg": float(np.percentile(np.abs(difference), 95)),
            "meanSignedDeg": float(np.mean(difference))}


def matching_projection_parameters(base: CRS, fine: CRS) -> bool:
    """Compare projection geometry when fine DEM WKT lacks a named datum."""
    left, right = base.coordinate_operation, fine.coordinate_operation
    if left is None or right is None or left.method_name != right.method_name:
        return False
    if (not np.isclose(base.ellipsoid.semi_major_metre, fine.ellipsoid.semi_major_metre, rtol=0, atol=1e-6)
            or not np.isclose(base.ellipsoid.semi_minor_metre, fine.ellipsoid.semi_minor_metre, rtol=0, atol=1e-6)
            or not np.isclose(base.prime_meridian.longitude, fine.prime_meridian.longitude, rtol=0, atol=1e-8)):
        return False
    if len(base.axis_info) != len(fine.axis_info) or any(
        a.direction != b.direction or not np.isclose(a.unit_conversion_factor, b.unit_conversion_factor, rtol=0, atol=1e-12)
        for a, b in zip(base.axis_info, fine.axis_info, strict=True)
    ):
        return False
    a = {p.name: (p.value, p.unit_conversion_factor) for p in left.params}
    b = {p.name: (p.value, p.unit_conversion_factor) for p in right.params}
    return a.keys() == b.keys() and all(np.allclose(a[key], b[key], rtol=0, atol=1e-8) for key in a)


@njit(parallel=True)
def coarse_outer_horizon(dem: np.ndarray, cols: np.ndarray, rows: np.ndarray, observer_elevations: np.ndarray,
                         pixel_size: float, inner_radius: float, max_distance: float,
                         azimuth_count: int, offsets: np.ndarray) -> np.ndarray:
    """Use coarse terrain beyond the fine patch, measured from each fine DEM observer."""
    output = np.full((len(cols), azimuth_count), np.nan, dtype=np.float32)
    for i in prange(len(cols)):
        observer = observer_elevations[i] + CALIBRATION_HEIGHT_M
        for az in range(azimuth_count):
            angle = 2 * math.pi * az / azimuth_count + offsets[i]
            best = -math.inf
            for step in range(int(inner_radius / pixel_size) + 1, int(max_distance / pixel_size) + 1):
                distance = step * pixel_size
                elevation = _bilinear(dem, cols[i] + step * math.sin(angle), rows[i] - step * math.cos(angle))
                if math.isfinite(elevation):
                    delta = elevation - observer - distance * distance / (2 * LUNAR_RADIUS_M)
                    best = max(best, math.atan2(delta, distance))
            if best != -math.inf:
                output[i, az] = math.degrees(best)
    return output


def load_base_masks(grid_path: Path) -> np.ndarray:
    directory = grid_path.parent
    manifest = json.loads((directory / "horizon_manifest.json").read_text(encoding="utf-8"))
    with grid_path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if (manifest.get("gridSha256") != digest or CALIBRATION_HEIGHT_M not in manifest.get("heightsM", [])
            or manifest.get("azimuthCount") != HORIZON_AZIMUTH_COUNT):
        raise ValueError("The existing horizon masks do not match the grid or calibration height.")
    masks = np.load(directory / f"horizon_{CALIBRATION_HEIGHT_M}m.npy", mmap_mode="r", allow_pickle=False)
    if masks.shape != (manifest.get("gridPointCount"), HORIZON_AZIMUTH_COUNT):
        raise ValueError("The existing horizon mask dimensions do not match the manifest.")
    return masks


def run(data_dir: Path, grid_path: Path, output: Path) -> dict:
    base_path = data_dir / "dem/LDEM_80S_80MPP_ADJ.TIF"
    missing = [p for p in [base_path, grid_path, *(data_dir / "site_dem" / s for s in SITE_DEMS)] if not p.is_file()]
    if missing:
        raise FileNotFoundError("Required data is missing: " + ", ".join(map(str, missing)))
    with np.load(grid_path, allow_pickle=False) as grid:
        x, y, lat, lon, ids = (grid[k].copy() for k in ("x", "y", "lat", "lon", "ids"))
    base_masks = load_base_masks(grid_path)
    if len(base_masks) != len(x):
        raise ValueError("The existing horizon masks do not have one row per grid point.")
    with rasterio.open(base_path) as base:
        base_transform, base_crs = base.transform, base.crs
        if base_crs is None:
            raise ValueError("The base DEM has no CRS.")
        coarse_dem = base.read(1, masked=True).astype(np.float32).filled(np.nan)
    if base_transform.b != 0 or base_transform.d != 0 or base_transform.e != -base_transform.a:
        raise ValueError("The base DEM must have square north-up pixels.")
    crs = CRS.from_wkt(base_crs.to_wkt())
    project = Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)
    started = time.perf_counter()
    differences = []
    hybrid_differences = []
    site_reports = []
    for site_number, relative in enumerate(SITE_DEMS):
        path = data_dir / "site_dem" / relative
        with rasterio.open(path) as source:
            transform = source.transform
            if source.crs is None or not matching_projection_parameters(crs, CRS.from_wkt(source.crs.to_wkt())):
                raise ValueError(f"Site DEM projection parameters differ from the base DEM: {path}")
            if transform.b != 0 or transform.d != 0 or transform.e != -transform.a or transform.a <= 0:
                raise ValueError(f"Site DEM is not north-up with square pixels: {path}")
            fine_dem = source.read(1, masked=True).astype(np.float32).filled(np.nan)
        fine_cols = (x - transform.c) / transform.a - 0.5
        fine_rows = (transform.f - y) / transform.a - 0.5
        eligible = np.flatnonzero(sample_interior(fine_dem, fine_cols, fine_rows, transform.a,
                                                  CALIBRATION_LOCAL_RADIUS_M))
        if not len(eligible):
            raise ValueError(f"No fully covered comparison sites in {path}.")
        count = min(CALIBRATION_SAMPLES_PER_SITE, len(eligible))
        selected = np.random.default_rng(CALIBRATION_RANDOM_SEED + site_number).choice(eligible, count, replace=False)
        north_x, north_y = project.transform(lon[selected], lat[selected] + 0.00001)
        offsets = np.arctan2(north_x - x[selected], north_y - y[selected])
        coarse_cols = (x[selected] - base_transform.c) / base_transform.a - 0.5
        coarse_rows = (base_transform.f - y[selected]) / base_transform.a - 0.5
        coarse = horizon_masks(coarse_dem, coarse_cols, coarse_rows, CALIBRATION_HEIGHT_M, base_transform.a,
                               CALIBRATION_LOCAL_RADIUS_M, HORIZON_AZIMUTH_COUNT, offsets)
        fine = horizon_masks(fine_dem, fine_cols[selected], fine_rows[selected], CALIBRATION_HEIGHT_M, transform.a,
                             CALIBRATION_LOCAL_RADIUS_M, HORIZON_AZIMUTH_COUNT, offsets)
        site_summary = summarize_differences(coarse, fine)
        fine_elevations = np.array([_bilinear(fine_dem, c, r) for c, r in
                                    zip(fine_cols[selected], fine_rows[selected], strict=True)])
        outer = coarse_outer_horizon(coarse_dem, coarse_cols, coarse_rows, fine_elevations, base_transform.a,
                                    CALIBRATION_LOCAL_RADIUS_M, HORIZON_MAX_DISTANCE_M,
                                    HORIZON_AZIMUTH_COUNT, offsets)
        if not np.isfinite(outer).all():
            raise ValueError(f"The outer coarse DEM does not cover every horizon ray: {path}")
        hybrid = np.maximum(fine, outer)
        baseline = np.asarray(base_masks[selected])
        hybrid_summary = summarize_differences(baseline, hybrid)
        site_reports.append({"site": relative.parts[0], "eligiblePointCount": len(eligible),
                             "sampledGridIds": ids[selected].tolist(),
                             "demPath": str(path), "local": site_summary, "hybrid100km": hybrid_summary})
        differences.append(fine.astype(np.float64) - coarse.astype(np.float64))
        hybrid_differences.append(hybrid.astype(np.float64) - baseline.astype(np.float64))
        print(f"{relative.parts[0]}: {count} sites, local absolute P95 {site_summary['absoluteP95Deg']:.4f}, "
              f"hybrid absolute P95 {hybrid_summary['absoluteP95Deg']:.4f} degrees", flush=True)
    signed = np.concatenate(differences, axis=0)
    hybrid_signed = np.concatenate(hybrid_differences, axis=0)
    report = {"method": "Compare 5 m and 80 m over the same 2 km radius; hybrid uses 5 m inside 2 km and 80 m outside, not a full 100 km high-resolution DEM.",
              "radiusM": CALIBRATION_LOCAL_RADIUS_M, "heightM": CALIBRATION_HEIGHT_M,
              "samplesPerSiteLimit": CALIBRATION_SAMPLES_PER_SITE, "randomSeed": CALIBRATION_RANDOM_SEED,
              "sites": site_reports, "totalSiteCount": int(signed.shape[0]),
              "uniqueSiteCount": len({item for site in site_reports for item in site["sampledGridIds"]}),
              "totalAzimuthSamples": int(signed.size), "signedP95Deg": float(np.percentile(signed, 95)),
              "absoluteP95Deg": float(np.percentile(np.abs(signed), 95)),
              "meanSignedDeg": float(np.mean(signed)),
              "hybridSignedP95Deg": float(np.percentile(hybrid_signed, 95)),
              "hybridAbsoluteP95Deg": float(np.percentile(np.abs(hybrid_signed), 95)),
              "hybridMeanSignedDeg": float(np.mean(hybrid_signed)), "elapsedSeconds": time.perf_counter() - started}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--grid", type=Path, default=Path("artifacts/grid.npz"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/delta_calibration.json"))
    args = parser.parse_args()
    try:
        result = run(args.data_dir, args.grid, args.output)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print(f"Total: {result['totalSiteCount']} sites; local signed P95 {result['signedP95Deg']:.4f}, "
          f"local absolute P95 {result['absoluteP95Deg']:.4f}, hybrid signed P95 "
          f"{result['hybridSignedP95Deg']:.4f}, hybrid absolute P95 {result['hybridAbsoluteP95Deg']:.4f} degrees. "
          "Default margin was not changed.")


if __name__ == "__main__":
    main()
