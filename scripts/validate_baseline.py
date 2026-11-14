"""Compare 2027 horizon-based annual visibility with the PGDA 69 baselines."""

import time
from pathlib import Path

import numpy as np
import rasterio
from pyproj import CRS

from app.engine.artifacts import load_artifacts
from app.engine.batch import visibility_windows
from app.engine.terrain import sample_raster
from app.settings import BASELINE_SAMPLE_COUNT, BASELINE_SYSTEMATIC_BIAS_THRESHOLD


def main() -> None:
    started = time.perf_counter()
    artifacts = load_artifacts(Path("artifacts"))
    grid = artifacts.grid
    crs = CRS.from_wkt(str(grid["crs"].item()))
    count = min(BASELINE_SAMPLE_COUNT, len(grid["ids"]))
    indices = np.random.default_rng(0).choice(len(grid["ids"]), count, replace=False)
    paths = [Path("data/baseline/AVGVISIB_85S_060M_201608.LBL"),
             Path("data/baseline/AVGVISIB_85S_060M_201608_EARTH.LBL")]
    reference = []
    for path in paths:
        raw = sample_raster(path, grid["x"][indices], grid["y"][indices], crs)
        with rasterio.open(path) as dataset:
            reference.append(raw * dataset.scales[0] + dataset.offsets[0])
    metrics, invalid = visibility_windows(
        grid["lat"][indices], grid["lon"][indices], artifacts.masks[1][indices],
        artifacts.sky["r_earth"], artifacts.sky["r_sun"], artifacts.sky["rho_earth"],
        artifacts.sky["rho_sun"], len(artifacts.sky["time"]), 0, 0, 0,
    )
    if np.any(invalid):
        raise ValueError("One or more sampled sites have invalid sky or horizon data.")
    estimates = metrics[:, 0, :2]
    for i, label in enumerate(("Sun", "Earth")):
        valid = np.isfinite(reference[i]) & np.isfinite(estimates[:, i])
        if valid.sum() < 2:
            raise ValueError(f"Not enough valid {label} baseline samples.")
        diff = estimates[valid, i] - reference[i][valid]
        corr = float(np.corrcoef(estimates[valid, i], reference[i][valid])[0, 1])
        bias = float(np.mean(diff))
        print(f"{label}: N={valid.sum()} correlation={corr:.6f} MAE={np.mean(np.abs(diff)):.6f} bias={bias:.6f}")
        if abs(bias) >= BASELINE_SYSTEMATIC_BIAS_THRESHOLD:
            print(f"Warning: {label} mean bias meets or exceeds {BASELINE_SYSTEMATIC_BIAS_THRESHOLD:.2f}.")
    print(f"Elapsed seconds: {time.perf_counter() - started:.2f}")


if __name__ == "__main__":
    main()
