from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_is_not_ready_without_artifacts(tmp_path: Path) -> None:
    with TestClient(create_app(Settings(data_dir=tmp_path, artifacts_dir=tmp_path / "artifacts"))) as client:
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json() == {"success": False, "error": {
            "code": "DATA_NOT_READY", "message": "Data is still loading."}}
        assert client.get("/docs").status_code == 200
        missing = client.get("/unknown-endpoint")
        assert missing.status_code == 404
        assert missing.json()["success"] is False


def test_provisional_cors_allows_origins(tmp_path: Path) -> None:
    with TestClient(create_app(Settings(data_dir=tmp_path, artifacts_dir=tmp_path / "artifacts"))) as client:
        response = client.get("/config", headers={"Origin": "https://example.com"})
        assert response.headers["access-control-allow-origin"] == "*"
