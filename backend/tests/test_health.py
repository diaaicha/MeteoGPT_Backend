from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["service"] == "MeteoGPT Backend"
    assert data["environment"] == "development"


def test_openapi_available():
    response = client.get("/openapi.json")

    assert response.status_code == 200

    data = response.json()

    assert data["info"]["title"] == "MeteoGPT Backend"


def test_swagger_available():
    response = client.get("/docs")

    assert response.status_code == 200