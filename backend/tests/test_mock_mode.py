from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def test_health_reports_mock_mode() -> None:
    settings = get_settings()
    original = settings.mock_lxd
    settings.mock_lxd = True
    try:
        with TestClient(app) as client:
            response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["lxd"] == "mock"
    finally:
        settings.mock_lxd = original
