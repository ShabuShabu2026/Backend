"""Objective calculations on explicitly supplied source geometries."""

from pathlib import Path

import geopandas as gpd
import numpy as np
import shapely
from numpy.typing import NDArray
from pyproj import CRS, Transformer

from app.settings import (
    GEOLOGY_CLIP_LAT_DEG,
    GEOLOGY_RADIUS_M,
    LARGE_CRATER_DIAMETER_KM,
    REFERENCE_PERCENTILE,
)

GEOLOGY_PATH = Path("geology/Unified_Geologic_Map_of_the_Moon_GIS/Lunar_GIS/Shapefiles/GeoUnits.shp")
CRATER_ARCHIVE = Path("craters/goransalamuniccar_mooncraters.zip")
CRATER_MEMBER = "GoranSalamuniccar_MoonCraters/LU78287GT_GIS/LU78287GT_Moon2000.shp"
GEOLOGY_UNIT_FIELD = "FIRST_Unit"


def load_geology(data_dir: Path, crs: CRS) -> gpd.GeoDataFrame:
    path = data_dir / GEOLOGY_PATH
    if not path.is_file():
        raise FileNotFoundError(f"Required geology shapefile is missing: {path}")
    geology = gpd.read_file(path, columns=[GEOLOGY_UNIT_FIELD])
    if geology.crs is None or GEOLOGY_UNIT_FIELD not in geology.columns:
        raise ValueError("Geology CRS or unit code field is missing.")
    projection = Transformer.from_crs(geology.crs.geodetic_crs, geology.crs, always_xy=True)
    left, cutoff = projection.transform(-180, GEOLOGY_CLIP_LAT_DEG)
    right, _ = projection.transform(180, GEOLOGY_CLIP_LAT_DEG)
    _, pole = projection.transform(0, -90)
    region = shapely.box(left, pole - 1, right, cutoff)
    geology = geology[geology.geometry.notna() & geology.geometry.intersects(region)].copy()
    geology.geometry = shapely.intersection(shapely.make_valid(geology.geometry.array), region)
    geology = geology.to_crs(crs)
    geology.geometry = shapely.make_valid(geology.geometry.array)
    return geology


def load_craters(data_dir: Path, crs: CRS) -> gpd.GeoDataFrame:
    path = data_dir / CRATER_ARCHIVE
    if not path.is_file():
        raise FileNotFoundError(f"Required crater catalog is missing: {path}")
    uri = "/vsizip/" + path.resolve().as_posix() + "/" + CRATER_MEMBER
    craters = gpd.read_file(uri, columns=["Radius_km"])
    if craters.crs is None or "Radius_km" not in craters:
        raise ValueError("Crater CRS or radius field is missing.")
    craters = craters[craters["Radius_km"] >= LARGE_CRATER_DIAMETER_KM / 2].copy()
    return craters.to_crs(crs)


def geology_counts(x: NDArray, y: NDArray, geology: gpd.GeoDataFrame) -> NDArray:
    geometry = geology.geometry.to_numpy()
    units = geology[GEOLOGY_UNIT_FIELD].fillna("").astype(str).to_numpy()
    if not len(geometry):
        raise ValueError("The geology dataset is empty.")
    _, codes = np.unique(units, return_inverse=True)
    pairs = shapely.STRtree(geometry).query(shapely.points(x, y), predicate="dwithin", distance=GEOLOGY_RADIUS_M)
    if pairs.shape[1] == 0:
        return np.zeros(len(x), dtype=int)
    nonempty = units[pairs[1]] != ""
    unique = np.unique(np.column_stack((pairs[0][nonempty], codes[pairs[1][nonempty]])), axis=0)
    return np.bincount(unique[:, 0], minlength=len(x))


def nearest_distances(x: NDArray, y: NDArray, geometries: NDArray) -> NDArray:
    geometries = np.asarray(geometries, dtype=object)
    valid = geometries[~(shapely.is_empty(geometries) | shapely.is_missing(geometries))]
    if not len(valid):
        raise ValueError("The objective geometry dataset is empty.")
    points = shapely.points(np.asarray(x), np.asarray(y))
    tree = shapely.STRtree(valid)
    return np.asarray(shapely.distance(points, valid[tree.nearest(points)]), dtype=float)


def percentile_reference(values: NDArray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        raise ValueError("The objective reference distribution is empty.")
    return float(np.percentile(values, REFERENCE_PERCENTILE))


def proximity_scores(distances: NDArray, reference: float) -> NDArray:
    if not np.isfinite(reference) or reference < 0:
        raise ValueError("Objective reference must be finite and nonnegative.")
    distances = np.asarray(distances, dtype=float)
    if reference == 0:
        return np.where(distances == 0, 1.0, 0.0)
    return np.clip(1.0 - distances / reference, 0.0, 1.0)
