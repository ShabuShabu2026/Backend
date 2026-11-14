from itertools import product
from pathlib import Path
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient

from app.config import Settings
from app.engine.artifacts import Artifacts
from app.engine.scoring import calculate_weights
from app.main import create_app
from app.settings import OBJECTIVES


def test_preview_and_objectives(tmp_path: Path) -> None:
    with TestClient(create_app(Settings(data_dir=tmp_path, artifacts_dir=tmp_path, database_url=None))) as client:
        assert len(client.get("/config").json()["objectives"]) == 8
        params = {"missionType": "CREWED", "powerRequirement": "NORMAL",
                  "communicationDependency": "NORMAL", "objective": "GENERAL"}
        result = client.get("/weights", params=params)
        assert result.status_code == 200
        assert result.json() == {"importance": [3, 5, 5, 3, None],
                                 "normalizedWeights": [0.1875, 0.3125, 0.3125, 0.1875, None],
                                 "otherIncluded": False}
        assert client.get("/weights", params={**params, "importanceWeights": "3,5,5,3,6"}).status_code == 400
        assert client.get("/weights", params={**params, "objective": "INVALID"}).json()["error"]["code"] == "INVALID_REQUEST"
        assert client.get("/weights").status_code == 400


def test_analysis_does_not_fabricate_results(tmp_path: Path) -> None:
    request = {"landingDate": "2027-03-05", "stayDays": 6, "missionType": "CREWED",
               "objective": "GENERAL", "powerRequirement": "NORMAL",
               "communicationDependency": "NORMAL"}
    with TestClient(create_app(Settings(data_dir=tmp_path, artifacts_dir=tmp_path, database_url=None))) as client:
        result = client.post("/analyses", json=request)
        assert result.status_code == 503
        assert result.json()["error"]["code"] == "DATA_NOT_READY"
        result = client.post("/analyses", json={**request, "objective": "UNKNOWN"})
        assert result.status_code == 400
        result = client.post("/analyses", json={**request, "landingDate": "2027-01-01"})
        assert result.json()["error"]["code"] == "DATE_OUT_OF_RANGE"
        bad_weights = {**request, "advanced": {"importanceWeights": [True, 3, 3, 3, 3]}}
        assert client.post("/analyses", json=bad_weights).status_code == 400
        assert client.get("/analyses/missing/grid", params={"bbox": "0,0,1,1"}).json()["error"]["code"] == "ANALYSIS_NOT_FOUND"
        assert client.get("/analyses/missing/grid", params={"bbox": "1,0,0,1"}).status_code == 400


def test_all_preview_presets_match_shared_weight_calculation(tmp_path: Path) -> None:
    with TestClient(create_app(Settings(data_dir=tmp_path, artifacts_dir=tmp_path, database_url=None))) as client:
        for mission, power, comm, objective in product(
            ("CREWED", "UNCREWED"), ("LOW", "NORMAL", "HIGH"),
            ("INDEPENDENT", "NORMAL", "CRITICAL"), (o[0] for o in OBJECTIVES),
        ):
            params = {"missionType": mission, "powerRequirement": power,
                      "communicationDependency": comm, "objective": objective}
            response = client.get("/weights", params=params)
            assert response.status_code == 200
            assert response.json() == calculate_weights(mission, power, comm, objective)


def test_preview_matches_analysis_for_all_presets(tmp_path: Path) -> None:
    size = 4
    grid = {"ids": np.array([f"LSP-{i:04}" for i in range(1, size + 1)]),
            "x": np.array([-1000, 1000, -1000, 1000]), "y": np.array([1000, 1000, -1000, -1000]),
            "lat": np.zeros(size), "lon": np.zeros(size), "slope": np.zeros(size),
            "roughness": np.zeros(size), "crs": np.array("test CRS")}
    times = np.arange(np.datetime64("2027-03-05T00", "h"), np.datetime64("2027-03-06T00", "h"))
    sky = {"time": times, "r_earth": np.zeros((24, 3)), "r_sun": np.zeros((24, 3)),
           "rho_earth": np.ones(24), "rho_sun": np.ones(24)}
    objectives = {name: np.full(size, 0.5) for name in ("POLAR_VOLATILES", "PLANETARY_PROCESSES", "IMPACT_HISTORY")}
    bundle = Artifacts(grid=grid, sky=sky, masks={1: np.zeros((size, 720))},
                       roughness_reference=np.array([0.0, 1.0]), objectives=objectives, reference={})
    metrics = np.zeros((size, 1, 5))
    metrics[:, :, 0:2] = 1
    app = create_app(Settings(data_dir=tmp_path, artifacts_dir=tmp_path, database_url=None))
    with TestClient(app) as client, patch("app.engine.service.visibility_windows", return_value=(metrics, np.zeros(size, dtype=bool))):
        app.state.artifacts = bundle
        for mission, power, comm, objective in product(
            ("CREWED", "UNCREWED"), ("LOW", "NORMAL", "HIGH"),
            ("INDEPENDENT", "NORMAL", "CRITICAL"), (o[0] for o in OBJECTIVES),
        ):
            params = {"missionType": mission, "powerRequirement": power,
                      "communicationDependency": comm, "objective": objective}
            preview = client.get("/weights", params=params).json()
            result = client.post("/analyses", json={**params, "landingDate": "2027-03-05", "stayDays": 1,
                                                       "advanced": {"landingDateSearchRangeDays": 0}})
            assert result.status_code == 201, result.text
            assert result.json()["appliedImportance"] == preview["importance"]
            assert result.json()["normalizedWeights"] == preview["normalizedWeights"]
