"""Load and validate the offline artifacts required by the analysis API."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from app.engine.sky import load_sky_table
from app.settings import HEIGHTS_M, HORIZON_AZIMUTH_COUNT


@dataclass(frozen=True)
class Artifacts:
    grid: dict[str, NDArray]
    sky: dict[str, NDArray]
    masks: dict[int, NDArray]
    roughness_reference: NDArray
    objectives: dict[str, NDArray]
    reference: dict


def load_artifacts(directory: Path) -> Artifacts:
    grid_path = directory / "grid.npz"
    if not grid_path.is_file():
        raise FileNotFoundError(f"Required grid artifact is missing: {grid_path}")
    with np.load(grid_path, allow_pickle=False) as source:
        grid = {key: source[key] for key in ("ids", "x", "y", "lat", "lon", "elevation", "slope", "roughness", "crs")}
    count = len(grid["ids"])
    if not count or any(len(grid[key]) != count for key in ("x", "y", "lat", "lon", "elevation", "slope", "roughness")):
        raise ValueError("Grid artifact has inconsistent columns.")
    if (len(np.unique(grid["ids"])) != count or
            any(not np.all(np.isfinite(grid[key])) for key in ("x", "y", "lat", "lon", "elevation", "slope", "roughness"))):
        raise ValueError("Grid artifact contains duplicate identifiers or invalid values.")
    manifest = json.loads((directory / "horizon_manifest.json").read_text(encoding="utf-8"))
    with grid_path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if (manifest.get("gridSha256") != digest or manifest.get("gridPointCount") != count
            or manifest.get("heightsM") != list(HEIGHTS_M)
            or manifest.get("azimuthCount") != HORIZON_AZIMUTH_COUNT):
        raise ValueError("Horizon mask manifest does not match the grid.")
    sky = load_sky_table(directory / "sky_table.npz")
    if not len(sky["time"]) or any(len(sky[key]) != len(sky["time"]) for key in ("r_earth", "r_sun", "rho_sun", "rho_earth")):
        raise ValueError("Sky artifact has inconsistent columns.")
    if (np.any(np.diff(sky["time"].astype("datetime64[h]")) != np.timedelta64(1, "h"))
            or any(not np.all(np.isfinite(sky[key])) for key in ("r_earth", "r_sun", "rho_sun", "rho_earth"))):
        raise ValueError("Sky artifact has invalid timestamps or values.")
    if (sky["r_earth"].shape != (len(sky["time"]), 3) or sky["r_sun"].shape != (len(sky["time"]), 3)
            or np.any(sky["rho_sun"] <= 0) or np.any(sky["rho_earth"] <= 0)):
        raise ValueError("Sky artifact has invalid body positions or angular radii.")
    masks: dict[int, NDArray] = {}
    for height in HEIGHTS_M:
        mask = np.load(directory / f"horizon_{height}m.npy", mmap_mode="r", allow_pickle=False)
        if mask.shape != (count, HORIZON_AZIMUTH_COUNT):
            raise ValueError(f"Horizon mask dimensions do not match the grid: {height} m.")
        masks[height] = mask
    roughness = np.load(directory / "roughness_reference.npy", allow_pickle=False)
    if roughness.ndim != 1 or not len(roughness) or not np.all(np.isfinite(roughness)) or np.any(np.diff(roughness) < 0):
        raise ValueError("Roughness reference must be a sorted finite array.")
    reference = json.loads((directory / "reference.json").read_text(encoding="utf-8"))
    if reference.get("gridPointCount") != count or reference.get("gridSha256") != digest:
        raise ValueError("Reference artifact does not match the grid.")
    objectives = {}
    for objective in ("POLAR_VOLATILES", "PLANETARY_PROCESSES", "IMPACT_HISTORY"):
        path = directory / f"objective_{objective.lower()}.npy"
        if path.is_file() and objective not in reference.get("unavailableObjectives", []):
            scores = np.load(path, mmap_mode="r", allow_pickle=False)
            if scores.shape != (count,):
                raise ValueError(f"Objective artifact does not match the grid: {objective}")
            if not np.all(np.isfinite(scores)) or np.any((scores < 0) | (scores > 1)):
                raise ValueError(f"Objective artifact contains invalid scores: {objective}")
            objectives[objective] = scores
    return Artifacts(grid, sky, masks, roughness, objectives, reference)
