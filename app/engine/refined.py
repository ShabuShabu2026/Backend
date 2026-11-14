"""On-demand refined grid calculations for an existing analysis."""

import math
from typing import Any

import geopandas as gpd
import numpy as np
import rasterio
from pyproj import CRS, Transformer

from app.config import Settings
from app.engine.analysis import evaluate_site
from app.engine.artifacts import Artifacts
from app.engine.horizon import horizon_masks
from app.engine.objectives import (
    geology_counts,
    load_craters,
    load_geology,
    nearest_distances,
    proximity_scores,
)
from app.engine.terrain import sample_raster
from app.settings import (
    GRID_LATITUDE_LIMIT_DEG,
    HORIZON_AZIMUTH_COUNT,
    HORIZON_MAX_DISTANCE_M,
)


def refined_sites(analysis: dict[str, Any], bounds: tuple[float, float, float, float],
                  spacing: float, artifacts: Artifacts, settings: Settings) -> list[dict[str, Any]]:
    grid = artifacts.grid
    crs = CRS.from_wkt(str(grid["crs"].item()))
    if crs.geodetic_crs is None:
        raise ValueError("DEM geographic coordinate system is missing.")
    forward = Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)
    inverse = Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True)
    edge_x, edge_y = forward.transform(0, GRID_LATITUDE_LIMIT_DEG)
    radius = math.hypot(edge_x, edge_y)
    xmin, ymin, xmax, ymax = bounds
    xmin, ymin, xmax, ymax = max(xmin, -radius), max(ymin, -radius), min(xmax, radius), min(ymax, radius)
    if xmin > xmax or ymin > ymax:
        return []
    col0, col1 = math.ceil(xmin / spacing), math.floor(xmax / spacing)
    row0, row1 = math.ceil(ymin / spacing), math.floor(ymax / spacing)
    if col0 > col1 or row0 > row1:
        return []
    cols, rows = np.meshgrid(np.arange(col0, col1 + 1), np.arange(row1, row0 - 1, -1))
    cols, rows = cols.ravel(), rows.ravel()
    x, y = cols * spacing, rows * spacing
    inside = x * x + y * y <= radius * radius
    cols, rows, x, y = cols[inside], rows[inside], x[inside], y[inside]
    if not len(x):
        return []
    cache = analysis.setdefault("refined", {})
    # Canonical coordinates keep identical points stable when the viewport changes.
    keys = [(round(float(px), 7), round(float(py), 7)) for px, py in zip(x, y, strict=True)]
    if "baseCoordinates" not in analysis:
        analysis["baseCoordinates"] = {
            (round(float(site["x"]), 7), round(float(site["y"]), 7)): site
            for site in analysis["sites"]
        }
    base = analysis["baseCoordinates"]
    for key in keys:
        if key in base:
            cache[key] = base[key]
    missing = [i for i, key in enumerate(keys) if key not in cache]
    if missing:
        xx, yy = x[missing], y[missing]
        lon, lat = inverse.transform(xx, yy)
        lon, lat = np.asarray(lon), np.asarray(lat)
        lon = (lon + 180) % 360 - 180
        data_dir = settings.data_dir
        dem_path = data_dir / "dem/LDEM_80S_80MPP_ADJ.TIF"
        slope_path = data_dir / "terrain/LDSM_80S_80MPP_ADJ.TIF"
        roughness_path = data_dir / "terrain/LDRM_80S_50MPP_ADJ_ROUGH_100M.TIF"
        slope = sample_raster(slope_path, xx, yy, crs)
        roughness = sample_raster(roughness_path, xx, yy, crs)
        with rasterio.open(dem_path) as src:
            transform = src.transform
            dem = src.read(1, masked=True).astype(np.float32).filled(np.nan)
        north_x, north_y = forward.transform(lon, lat + 0.00001)
        offsets = np.arctan2(north_x - xx, north_y - yy)
        dem_cols = (xx - transform.c) / transform.a - 0.5
        dem_rows = (transform.f - yy) / transform.a - 0.5
        body = analysis["request"]
        masks = horizon_masks(dem, dem_cols, dem_rows, body.advanced.heightM, transform.a,
                              HORIZON_MAX_DISTANCE_M, HORIZON_AZIMUTH_COUNT, offsets)
        other: np.ndarray | None = None
        if body.objective == "POLAR_VOLATILES":
            psr_path = data_dir / "psr/LPSR_80S_20MPP_ADJ.SHP"
            if not psr_path.is_file():
                raise FileNotFoundError(f"Required PSR dataset is missing: {psr_path}")
            psr = gpd.read_file(psr_path)
            if psr.crs != crs:
                psr = psr.to_crs(crs)
            other = proximity_scores(nearest_distances(xx, yy, psr.geometry.to_numpy()),
                                     artifacts.reference["psrDistanceP95M"])
        elif body.objective in ("PLANETARY_PROCESSES", "IMPACT_HISTORY"):
            geology = load_geology(data_dir, crs)
            counts = geology_counts(xx, yy, geology)
            reference = artifacts.reference["geologyUnitsP95"]
            other = np.zeros(len(xx)) if reference == 0 else np.clip(counts / reference, 0, 1)
            if body.objective == "IMPACT_HISTORY":
                craters = load_craters(data_dir, crs)
                distances = nearest_distances(xx, yy, craters.geometry.to_numpy())
                other = 0.5 * other + 0.5 * proximity_scores(distances, artifacts.reference["craterDistanceP95M"])
        next_id = analysis.setdefault("nextSiteId", len(grid["ids"]) + 1)
        created: list[tuple[int, dict[str, Any]]] = []
        for offset, point_index in enumerate(missing):
            score = None if other is None else float(other[offset])
            result = evaluate_site(body, float(lat[offset]), float(lon[offset]), float(slope[offset]),
                                   float(roughness[offset]), masks[offset], artifacts.sky,
                                   artifacts.roughness_reference, score)
            result.pop("hourly")
            result.update({"siteId": f"LSP-{next_id:04d}", "lat": float(lat[offset]),
                           "lon": float(lon[offset]), "x": float(xx[offset]), "y": float(yy[offset]),
                           "slopeDeg": float(slope[offset]), "roughnessM": float(roughness[offset]),
                           "horizon": masks[offset].copy(), "objectiveScore": score})
            created.append((point_index, result))
            next_id += 1
        for index, result in created:
            cache[keys[index]] = result
            analysis["byId"][result["siteId"]] = result
        analysis["nextSiteId"] = next_id
    return [cache[key] for key in keys]
