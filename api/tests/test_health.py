# tests/test_health.py
from fastapi.testclient import TestClient
from opentaion_api.main import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_correct_body():
    response = client.get("/health")
    assert response.json() == {"status": "ok"}
