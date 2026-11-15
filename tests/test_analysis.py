from datetime import date

import numpy as np
import pytest
import rasterio
from fastapi.testclient import TestClient
from pyproj import CRS, Transformer
from rasterio.transform import from_origin

from app.config import Settings
from app.engine.analysis import evaluate_site
from app.engine.artifacts import Artifacts
from app.engine.refined import refined_sites
from app.engine.service import build_analysis
from app.main import create_app
from app.schemas import Advanced, AnalysisRequest, CrewedConstraint
from app.settings import LUNAR_RADIUS_M


def synthetic_sky() -> dict[str, np.ndarray]:
    times = np.arange(np.datetime64("2027-03-05T00", "h"), np.datetime64("2027-03-06T00", "h"))
    bodies = np.tile([LUNAR_RADIUS_M + 100_000.0, 0, 0], (len(times), 1))
    return {"time": times, "r_earth": bodies, "r_sun": bodies,
            "rho_sun": np.full(len(times), 0.25), "rho_earth": np.full(len(times), 1.0)}


def test_site_analysis_pass_and_slope_exclusion() -> None:
    request = AnalysisRequest(landingDate=date(2027, 3, 5), stayDays=1, missionType="CREWED",
                              objective="GENERAL", powerRequirement="NORMAL",
                              communicationDependency="NORMAL",
                              advanced=Advanced(landingDateSearchRangeDays=0,
                                                crewedSunlightConstraint=CrewedConstraint(enabled=True)))
    sky = synthetic_sky()
    args = (request, 0.0, 0.0, 0.5, 0.1, np.zeros(4), sky, np.array([0.1, 0.2]))
    result = evaluate_site(*args)
    assert result["passed"] is True
    assert result["visibility"]["sunlightRatio"] == 1.0
    assert result["visibility"]["earthVisibleRatio"] == 1.0
    assert len(result["hourly"]["sunVisible"]) == 24
    excluded = evaluate_site(request, 0.0, 0.0, 6.0, 0.1, np.zeros(4), sky, np.array([0.1, 0.2]))
    assert excluded["exclusionCodes"] == ["SLOPE_EXCEEDED"]
    assert excluded["suitability"] is None


def test_base_analysis_api_with_synthetic_artifacts() -> None:
    sky = synthetic_sky()
    n = 4
    grid = {"ids": np.array([f"LSP-{i:04}" for i in range(1, n + 1)]),
            "x": np.array([-1000, 1000, -1000, 1000]), "y": np.array([1000, 1000, -1000, -1000]),
            "lat": np.zeros(n), "lon": np.zeros(n), "slope": np.full(n, 0.5),
            "roughness": np.full(n, 0.1), "crs": np.array("synthetic test CRS")}
    bundle = Artifacts(grid=grid, sky=sky, masks={1: np.zeros((n, 720))},
                       roughness_reference=np.array([0.1, 0.2]), objectives={}, reference={})
    body = {"landingDate": "2027-03-05", "stayDays": 1, "missionType": "CREWED",
            "objective": "GENERAL", "powerRequirement": "NORMAL", "communicationDependency": "NORMAL",
            "advanced": {"landingDateSearchRangeDays": 0}}
    with TestClient(create_app(Settings(database_url=None))) as client:
        client.app.state.artifacts = bundle
        response = client.post("/analyses", json=body)
        assert response.status_code == 201, response.text
        analysis = response.json()
        assert any("margin is provisional" in warning for warning in analysis["warnings"])
        assert analysis["counts"]["passed"] == n
        assert client.post("/analyses", json=body).json()["analysisId"] == analysis["analysisId"]
        path = f"/analyses/{analysis['analysisId']}"
        assert client.get(f"{path}/sites/LSP-0001").json()["passed"] is True
        visibility = client.get(f"{path}/sites/LSP-0001/visibility").json()
        assert len(visibility["hourly"]) == 24
        assert visibility["visibility"]["sunlightRatio"] == 1.0
        assert visibility["passed"] is True
        hourly = visibility["hourly"][0]
        assert visibility["site_id"] == "LSP-0001"
        assert hourly["timestamp"] == hourly["time"] == "2027-03-05T00:00:00Z"
        assert hourly["sun_azimuth"] == hourly["sunAzimuthDeg"]
        assert hourly["sun_elevation"] == hourly["sunElevationDeg"]
        assert hourly["earth_azimuth"] == hourly["earthAzimuthDeg"]
        assert hourly["earth_elevation"] == hourly["earthElevationDeg"]
        assert hourly["sun_visible"] == hourly["sunVisible"]
        assert hourly["earth_visible"] == hourly["earthVisible"]
        assert client.get(f"{path}/sites/no-such-site").json()["error"]["code"] == "SITE_NOT_FOUND"
        grid_result = client.get(f"{path}/grid", params={"bbox": "-40000,-40000,40000,40000"})
        assert len(grid_result.json()["sites"]["ids"]) == n
        assert client.get(f"{path}/grid", params={"bbox": "-1000,-1000,1000,1000"}).status_code == 503


def test_refined_grid_reuses_ids_and_scores(tmp_path) -> None:
    crs = CRS.from_proj4("+proj=stere +lat_0=-90 +lon_0=0 +R=1737400 +units=m")
    inverse = Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True)
    x = np.array([-1000.0, 0.0, 1000.0, 0.0])
    y = np.array([0.0, 0.0, 0.0, 1000.0])
    lon, lat = inverse.transform(x, y)
    for relative, value in (("dem/LDEM_80S_80MPP_ADJ.TIF", 0),
                            ("terrain/LDSM_80S_80MPP_ADJ.TIF", 0),
                            ("terrain/LDRM_80S_50MPP_ADJ_ROUGH_100M.TIF", 0.1)):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(path, "w", driver="GTiff", width=100, height=100, count=1,
                           dtype="float32", crs=crs.to_wkt(), transform=from_origin(-4000, 4000, 80, 80)) as dst:
            dst.write(np.full((1, 100, 100), value, dtype=np.float32))
    sky = synthetic_sky()
    sky["r_sun"] = np.tile([0, 0, -LUNAR_RADIUS_M - 100_000.0], (24, 1))
    sky["r_earth"] = sky["r_sun"].copy()
    grid = {"ids": np.array([f"LSP-{i:04}" for i in range(1, 5)]), "x": x, "y": y,
            "lat": np.asarray(lat), "lon": np.asarray(lon), "slope": np.zeros(4),
            "roughness": np.full(4, float(np.float32(0.1))), "crs": np.array(crs.to_wkt())}
    bundle = Artifacts(grid=grid, sky=sky, masks={1: np.zeros((4, 720))},
                       roughness_reference=np.array([float(np.float32(0.1)), 0.2]), objectives={}, reference={})
    body = {"landingDate": "2027-03-05", "stayDays": 1, "missionType": "CREWED",
            "objective": "GENERAL", "powerRequirement": "NORMAL", "communicationDependency": "NORMAL",
            "advanced": {"landingDateSearchRangeDays": 0}}
    app = create_app(Settings(data_dir=tmp_path, database_url=None))
    with TestClient(app) as client:
        app.state.artifacts = bundle
        post = client.post("/analyses", json=body).json()
        path = f"/analyses/{post['analysisId']}"
        params = {"bbox": "-400,-400,400,400"}
        refined = client.get(path + "/grid", params=params)
        assert refined.status_code == 200, refined.text
        points = refined.json()["sites"]
        center = next(i for i, (px, py) in enumerate(zip(points["x"], points["y"], strict=True)) if px == py == 0)
        assert points["suitability"][center] == post["sites"]["suitability"][1]
        again = client.get(path + "/grid", params=params).json()["sites"]
        assert again["ids"] == points["ids"]
        recommendations = client.get(path + "/recommendations", params=params)
        assert recommendations.status_code == 200
        assert recommendations.json()["returnedCount"] == 10
        wider = client.get(path + "/recommendations", params={"bbox": "-600,-600,600,600"})
        assert wider.status_code == 200
        assert wider.json()["returnedCount"] == 10
        assert client.get(path + "/grid", params=params).json()["sites"]["ids"] == points["ids"]
        assert client.get(path + f"/sites/{points['ids'][center]}/terrain").status_code == 200
        stored = app.state.store.get(post["analysisId"])
        bounds = (1999, -1, 2001, 1)
        first = refined_sites(stored, bounds, 200, bundle, app.state.settings)[0]
        second = refined_sites(stored, bounds, 250, bundle, app.state.settings)[0]
        assert first["siteId"] == second["siteId"]
        assert first["suitability"] == second["suitability"]


def test_terrain_frontend_contract_and_missing_values(tmp_path) -> None:
    dem = tmp_path / "dem" / "LDEM_80S_80MPP_ADJ.TIF"
    dem.parent.mkdir()
    crs = CRS.from_proj4("+proj=stere +lat_0=-90 +lon_0=0 +R=1737400 +units=m")
    values = np.arange(16, dtype=np.float32).reshape(4, 4)
    values[0, 0] = -9999
    with rasterio.open(dem, "w", driver="GTiff", width=4, height=4, count=1, dtype="float32",
                       nodata=-9999, crs=crs.to_wkt(), transform=from_origin(-160, 160, 80, 80)) as dst:
        dst.write(values, 1)
    app = create_app(Settings(data_dir=tmp_path, database_url=None))
    body = AnalysisRequest(landingDate="2027-03-05", stayDays=1, missionType="CREWED",
                           objective="GENERAL", powerRequirement="NORMAL", communicationDependency="NORMAL")
    site = {"siteId": "LSP-0001", "lat": -90.0, "lon": 0.0, "x": 0.0, "y": 0.0}
    analysis = app.state.store.put(body, {"byId": {site["siteId"]: site}, "response": {"crs": crs.to_wkt()}})
    with TestClient(app) as client:
        response = client.get(f"/analyses/{analysis['analysisId']}/sites/LSP-0001/terrain", params={"radiusM": 200})
        assert response.status_code == 200
        data = response.json()
        assert (data["site_id"], data["latitude"], data["longitude"]) == ("LSP-0001", -90.0, 0.0)
        assert data["heights"] == data["elevationsM"]
        assert data["heights"][0][0] is None
        assert data["heights"][3][3] == 15
        assert data["resolution_m"] == data["gridSpacingM"] == 80
        coordinates = data["coordinate_system"]
        assert coordinates["origin"] == {"x": -120, "y": 120}
        assert coordinates["site_position"] == {"x": 0, "y": 0}
        assert coordinates["column_step"] == {"x": 80, "y": 0}
        assert coordinates["row_step"] == {"x": 0, "y": -80}
        with rasterio.open(dem) as raster:
            assert CRS.from_wkt(coordinates["crs_wkt"]) == CRS.from_wkt(raster.crs.to_wkt())
        assert data["elevation_reference"]["radius_m"] == 1_737_400


@pytest.mark.parametrize("mission,sun_mode,earth_mode", [
    ("CREWED", "PARTIAL", "UPPER_EDGE"),
    ("CREWED", "HALF_DISK", "CENTER_DELTA"),
    ("UNCREWED", "FULL", "FULL"),
])
def test_batch_analysis_matches_single_site(mission: str, sun_mode: str, earth_mode: str) -> None:
    n = 4
    times = np.arange(np.datetime64("2027-03-05T00", "h"), np.datetime64("2027-03-08T00", "h"))
    angle = np.arange(len(times)) * 2 * np.pi / 24
    sun = np.column_stack((LUNAR_RADIUS_M + 1000 * np.sin(angle), np.full(len(times), 100_000), np.zeros(len(times))))
    earth = np.column_stack((LUNAR_RADIUS_M + 500 * np.cos(angle), np.full(len(times), 100_000), np.zeros(len(times))))
    sky = {"time": times, "r_earth": earth, "r_sun": sun, "rho_earth": np.ones(len(times)),
           "rho_sun": np.full(len(times), 0.25)}
    grid = {"ids": np.array([f"LSP-{i:04}" for i in range(1, n + 1)]),
            "x": np.array([-1000, 1000, -1000, 1000]), "y": np.array([1000, 1000, -1000, -1000]),
            "lat": np.zeros(n), "lon": np.zeros(n), "slope": np.array([0.0, 3.0, 6.0, 15.0]),
            "roughness": np.array([0.1, 0.2, 0.3, 0.4]), "crs": np.array("test CRS")}
    masks = np.zeros((n, 720))
    reference = np.array([0.1, 0.2, 0.3, 0.4])
    artifacts = Artifacts(grid, sky, {1: masks}, reference, {}, {})
    request = AnalysisRequest(landingDate=date(2027, 3, 6), stayDays=1, missionType=mission, objective="GENERAL",
                              powerRequirement="NORMAL", communicationDependency="NORMAL", advanced={
                                  "landingDateSearchRangeDays": 1, "sunVisibilityCriterion": sun_mode,
                                  "earthVisibilityCriterion": earth_mode,
                                  "uncrewedConstraints": {"enabled": mission == "UNCREWED",
                                                           "batteryEnduranceHours": 6,
                                                           "maxCommBlackoutHours": 8}})
    result = build_analysis(request, artifacts)
    for i, actual in enumerate(result["sites"]):
        expected = evaluate_site(request, 0, 0, grid["slope"][i], grid["roughness"][i], masks[i], sky, reference)
        for key in ("passed", "exclusionCodes", "suitability", "bestLandingDate", "visibility"):
            assert actual[key] == expected[key]


def test_best_date_can_pass_when_requested_date_does_not() -> None:
    request = AnalysisRequest(landingDate=date(2027, 3, 6), stayDays=1, missionType="CREWED",
                              objective="GENERAL", powerRequirement="NORMAL",
                              communicationDependency="NORMAL",
                              advanced=Advanced(landingDateSearchRangeDays=1))
    times = np.arange(np.datetime64("2027-03-05T00", "h"), np.datetime64("2027-03-08T00", "h"))
    bodies = np.tile([LUNAR_RADIUS_M + 100_000.0, 0, 0], (len(times), 1))
    sun = bodies.copy()
    sun[24:48, 0] = LUNAR_RADIUS_M - 100_000.0
    sky = {"time": times, "r_earth": bodies, "r_sun": sun,
           "rho_sun": np.full(len(times), 0.25), "rho_earth": np.full(len(times), 1.0)}
    result = evaluate_site(request, 0, 0, 0, 0.1, np.zeros(720), sky, np.array([0.1]))
    assert not result["passed"]
    assert result["bestLandingDate"] == "2027-03-05"
    grid = {"ids": np.array(["LSP-0001", "LSP-0002"]), "x": np.array([0, 1000]),
            "y": np.array([0, 1000]), "lat": np.zeros(2), "lon": np.zeros(2),
            "slope": np.zeros(2), "roughness": np.full(2, 0.1), "crs": np.array("test")}
    artifacts = Artifacts(grid, sky, {1: np.zeros((2, 720))}, np.array([0.1]), {}, {})
    batch = build_analysis(request, artifacts)["sites"][0]
    assert batch["bestLandingDate"] == result["bestLandingDate"]
