
import os

from fastapi.testclient import TestClient

from app.handoff.api import app


def test_unauthorized_status(monkeypatch):
    monkeypatch.setenv("OPERATOR_TOKEN", "test-token")

    with TestClient(app) as client:
        response = client.get("/api/status")

    assert response.status_code == 401


def test_authorized_idle_status(monkeypatch):
    monkeypatch.setenv("OPERATOR_TOKEN", "test-token")

    with TestClient(app) as client:
        response = client.get(
            "/api/status",
            headers={
                "X-Operator-Token": "test-token",
            },
        )

    assert response.status_code == 200
    assert "state" in response.json()


def test_dashboard_available():
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Computer-Use Automation" in response.text
