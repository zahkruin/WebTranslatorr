"""
Tests for BaseProvider abstract base class.
"""

import pytest
from unittest.mock import AsyncMock

from app.providers.base import BaseProvider
from app.scraping.http_client import ScraperResponse


class ConcreteProvider(BaseProvider):
    """A concrete implementation of BaseProvider for testing."""

    async def search(self, query, categories=None, **kwargs):
        return []

    async def get_download_url(self, internal_id):
        return ""


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client


@pytest.fixture
def provider(mock_client):
    return ConcreteProvider(
        http_client=mock_client,
        provider_id="test_provider",
        display_name="Test Provider",
        base_url="https://example.com",
    )


class TestBaseProvider:
    """Tests for BaseProvider."""

    @pytest.mark.asyncio
    async def test_is_healthy_returns_true(self, provider, mock_client):
        """is_healthy should return True when the base URL responds 200."""
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text="ok",
            content=b"ok",
            headers={},
            url="https://example.com",
        )
        assert await provider.is_healthy() is True
        mock_client.get.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    async def test_is_healthy_returns_false_on_error(self, provider, mock_client):
        """is_healthy should return False when the request fails."""
        mock_client.get.side_effect = Exception("Connection error")
        assert await provider.is_healthy() is False

    @pytest.mark.asyncio
    async def test_is_healthy_returns_false_on_non_200(self, provider, mock_client):
        """is_healthy should return False when status is not 200."""
        mock_client.get.return_value = ScraperResponse(
            status_code=500,
            text="error",
            content=b"error",
            headers={},
            url="https://example.com",
        )
        assert await provider.is_healthy() is False

    def test_combine_query_with_all_parts(self, provider):
        """_combine_query should merge query, author, and title."""
        result = provider._combine_query("extra keyword", "tolkien", "lord of the rings")
        assert "tolkien" in result
        assert "lord" in result
        assert "extra" in result

    def test_combine_query_only_query(self, provider):
        """_combine_query should return just the query when author/title are missing."""
        result = provider._combine_query("harry potter", None, None)
        assert result == "harry potter"

    def test_combine_query_author_title_only(self, provider):
        """_combine_query should combine author and title when no query."""
        result = provider._combine_query("", "gabriel garcia marquez", "cien años")
        assert "gabriel" in result
        assert "cien" in result

    def test_normalize_query(self, provider):
        """normalize_query should clean and lowercase the query."""
        result = provider.normalize_query("  Harry Potter   y la Piedra  ")
        assert result == "harry potter y la piedra"

    def test_get_capabilities_defaults(self, provider):
        """get_capabilities should return sensible defaults."""
        caps = provider.get_capabilities()
        assert caps.provider_id == "test_provider"
        assert caps.display_name == "Test Provider"
        assert caps.supports_book_search is True
        assert caps.supports_movie_search is False
        assert caps.supports_tv_search is False
        assert "q" in caps.supported_search_params

    def test_build_search_url_does_nothing(self, provider):
        """_build_search_url is a no-op helper."""
        assert provider._build_search_url("test") is None

    def test_parse_results_does_nothing(self, provider):
        """_parse_results is a no-op helper."""
        assert provider._parse_results("<html></html>") is None
