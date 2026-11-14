from itertools import product

from fastapi.testclient import TestClient

from app.engine.scoring import calculate_weights
from app.main import create_app
from app.settings import OBJECTIVES


def test_preview_and_objectives() -> None:
    with TestClient(create_app()) as client:
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


def test_analysis_does_not_fabricate_results() -> None:
    request = {"landingDate": "2027-03-05", "stayDays": 6, "missionType": "CREWED",
               "objective": "GENERAL", "powerRequirement": "NORMAL",
               "communicationDependency": "NORMAL"}
    with TestClient(create_app()) as client:
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


def test_all_preview_presets_match_shared_weight_calculation() -> None:
    with TestClient(create_app()) as client:
        for mission, power, comm, objective in product(
            ("CREWED", "UNCREWED"), ("LOW", "NORMAL", "HIGH"),
            ("INDEPENDENT", "NORMAL", "CRITICAL"), (o[0] for o in OBJECTIVES),
        ):
            params = {"missionType": mission, "powerRequirement": power,
                      "communicationDependency": comm, "objective": objective}
            response = client.get("/weights", params=params)
            assert response.status_code == 200
            assert response.json() == calculate_weights(mission, power, comm, objective)
