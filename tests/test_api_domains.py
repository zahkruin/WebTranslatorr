"""
Tests for the /api/domains endpoints.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api import domains


@pytest.fixture
def mock_resolver():
    """Returns a mock DomainResolver."""
    resolver = MagicMock()
    resolver.get_status = MagicMock(return_value={
        "mejortorrent": {"url": "https://example.com", "healthy": True},
    })
    resolver.resolve = AsyncMock(return_value="https://new.example.com")
    resolver.resolve_all = AsyncMock(return_value={"mejortorrent": "https://example.com"})
    resolver.health_check = AsyncMock(return_value=True)
    return resolver


@pytest.fixture
def app(mock_resolver):
    """Creates a minimal FastAPI app with the domains router and a mock resolver."""
    app = FastAPI()
    app.state.domain_resolver = mock_resolver
    app.include_router(domains.router)
    return app


@pytest.fixture
def client(app):
    """Returns a TestClient for the test app."""
    return TestClient(app)


class TestGetDomains:
    """Tests for GET /api/domains"""

    def test_returns_status(self, client, mock_resolver):
        response = client.get("/api/domains")
        assert response.status_code == 200
        data = response.json()
        assert "mejortorrent" in data
        assert data["mejortorrent"]["url"] == "https://example.com"
        mock_resolver.get_status.assert_called_once()


class TestRefreshDomains:
    """Tests for POST /api/domains/refresh"""

    @pytest.mark.asyncio
    async def test_refresh_all(self, client, mock_resolver):
        response = client.post("/api/domains/refresh")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Domain resolution complete"
        assert "domains" in data


class TestRefreshProviderDomain:
    """Tests for POST /api/domains/refresh/{provider_id}"""

    @pytest.mark.asyncio
    async def test_refresh_provider_success(self, client, mock_resolver):
        response = client.post("/api/domains/refresh/mejortorrent")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Domain resolved for mejortorrent"
        assert data["domain"] == "https://new.example.com"

    @pytest.mark.asyncio
    async def test_refresh_provider_not_found(self, client, mock_resolver):
        mock_resolver.resolve = AsyncMock(side_effect=ValueError("Unknown provider: unknown"))
        response = client.post("/api/domains/refresh/unknown")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data


class TestCheckProviderHealth:
    """Tests for GET /api/domains/health/{provider_id}"""

    @pytest.mark.asyncio
    async def test_health_success(self, client, mock_resolver):
        response = client.get("/api/domains/health/mejortorrent")
        assert response.status_code == 200
        data = response.json()
        assert data["provider_id"] == "mejortorrent"
        assert data["healthy"] is True

    @pytest.mark.asyncio
    async def test_health_not_found(self, client, mock_resolver):
        mock_resolver.health_check = AsyncMock(side_effect=ValueError("Unknown provider"))
        response = client.get("/api/domains/health/unknown")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
