from pathlib import Path

import numpy as np
import rasterio
from fastapi.testclient import TestClient
from rasterio.transform import from_origin

from app.config import Settings
from app.main import create_app


def test_health_with_missing_data(tmp_path: Path) -> None:
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "data_missing"
        assert all(not item["exists"] for item in response.json()["data"].values())
        assert client.get("/docs").status_code == 200


def test_metadata_and_cors(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, cors_origins="http://localhost:3000, https://example.com")
    for path in settings.raster_paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(path, "w", driver="GTiff", width=2, height=3, count=1,
                           dtype="uint8", transform=from_origin(0, 3, 80, 80)) as dataset:
            dataset.write(np.zeros((1, 3, 2), dtype="uint8"))
    with TestClient(create_app(settings)) as client:
        response = client.get("/health", headers={"Origin": "https://example.com"})
        assert response.json()["status"] == "ok"
        assert response.json()["data"]["dem"]["shape"] == [3, 2]
        assert response.json()["data"]["dem"]["res"] == [80.0, 80.0]
        assert response.headers["access-control-allow-origin"] == "https://example.com"
        assert "access-control-allow-origin" not in client.get(
            "/health", headers={"Origin": "https://untrusted.example"}
        ).headers


def test_unreadable_raster(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    for path in settings.raster_paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("invalid")
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").json()["status"] == "data_error"
