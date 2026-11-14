import geopandas as gpd
import numpy as np
import shapely

from app.engine.objectives import (
    geology_counts,
    nearest_distances,
    percentile_reference,
    proximity_scores,
)


def test_psr_distance_and_proximity() -> None:
    square = shapely.box(0, 0, 2, 2)
    distances = nearest_distances(np.array([1, 5]), np.array([1, 1]), np.array([square]))
    np.testing.assert_allclose(distances, [0, 3])
    np.testing.assert_allclose(proximity_scores(distances, 3), [1, 0])
    assert percentile_reference(np.array([0, 100])) == 95


def test_geology_counts_distinct_units_not_polygons() -> None:
    data = gpd.GeoDataFrame({"FIRST_Unit": ["A", "A", "B"]}, geometry=[
        shapely.box(0, 0, 1, 1), shapely.box(2, 0, 3, 1), shapely.box(40000, 0, 40001, 1),
    ])
    result = geology_counts(np.array([0.0, 40000.0]), np.array([0.0, 0.0]), data)
    assert result.tolist() == [1, 1]
