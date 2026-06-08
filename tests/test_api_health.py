"""
Tests for the health check API endpoint.
"""

from fastapi.testclient import TestClient

from app.server import app

client = TestClient(app)


def test_health_check():
    """GET /health should return a healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "WebTranslatorr"
