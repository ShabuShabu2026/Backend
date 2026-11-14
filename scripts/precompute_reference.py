"""Build fixed roughness and PSR reference distributions from the base grid."""

import hashlib
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
from pyproj import CRS

from app.engine.objectives import (
    CRATER_ARCHIVE,
    GEOLOGY_PATH,
    geology_counts,
    load_craters,
    load_geology,
    nearest_distances,
    percentile_reference,
    proximity_scores,
)


def main() -> None:
    grid_path = Path("artifacts/grid.npz")
    psr_path = Path("data/psr/LPSR_80S_20MPP_ADJ.SHP")
    for path in (grid_path, psr_path):
        if not path.is_file():
            raise SystemExit(f"Required dataset is missing: {path}")
    with np.load(grid_path, allow_pickle=False) as grid:
        x, y, roughness = (grid[key].copy() for key in ("x", "y", "roughness"))
        crs = CRS.from_wkt(str(grid["crs"].item()))
    finite = np.sort(roughness[np.isfinite(roughness)])
    if not len(finite):
        raise SystemExit("The grid contains no finite roughness values.")
    psr = gpd.read_file(psr_path)
    if psr.crs is None:
        raise SystemExit("The PSR shapefile has no CRS.")
    if psr.crs != crs:
        psr = psr.to_crs(crs)
    distances = nearest_distances(x, y, psr.geometry.to_numpy())
    reference = percentile_reference(distances)
    np.save("artifacts/roughness_reference.npy", finite, allow_pickle=False)
    np.save("artifacts/objective_polar_volatiles.npy", proximity_scores(distances, reference), allow_pickle=False)
    with grid_path.open("rb") as stream:
        grid_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    report = {"psrDistanceP95M": reference, "gridPointCount": len(x),
              "gridSha256": grid_hash, "unavailableObjectives": []}
    geology = None
    if (Path("data") / GEOLOGY_PATH).is_file():
        geology = load_geology(Path("data"), crs)
        counts = geology_counts(x, y, geology)
        geology_ref = percentile_reference(counts)
        geology_scores = np.zeros(len(x)) if geology_ref == 0 else np.clip(counts / geology_ref, 0, 1)
        np.save("artifacts/objective_planetary_processes.npy", geology_scores, allow_pickle=False)
        report["geologyUnitsP95"] = geology_ref
    else:
        report["unavailableObjectives"].append("PLANETARY_PROCESSES")
    if geology is not None and (Path("data") / CRATER_ARCHIVE).is_file():
        craters = load_craters(Path("data"), crs)
        crater_distances = nearest_distances(x, y, craters.geometry.to_numpy())
        crater_ref = percentile_reference(crater_distances)
        impact_scores = 0.5 * geology_scores + 0.5 * proximity_scores(crater_distances, crater_ref)
        np.save("artifacts/objective_impact_history.npy", impact_scores, allow_pickle=False)
        report["craterDistanceP95M"] = crater_ref
    else:
        report["unavailableObjectives"].append("IMPACT_HISTORY")
    Path("artifacts/reference.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved references for {len(x)} grid points.")
    print("Unavailable objectives:", ", ".join(report["unavailableObjectives"]) or "none")


if __name__ == "__main__":
    main()
