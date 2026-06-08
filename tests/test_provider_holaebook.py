"""
Tests for HolaEbookProvider.
"""

import pytest
from unittest.mock import AsyncMock

from app.scraping.http_client import ScraperResponse
from app.providers.books.holaebook import HolaEbookProvider

SEARCH_HTML = """
<html><body>
    <a href="/libro/abc123/harry-potter.html">Harry Potter</a>
    <a href="/book/def456/el-senor/">El Señor de los Anillos</a>
</body></html>
"""

DETAIL_HTML = """
<html><body>
    <a href="/descargar/abc123">DESCARGAR EPUB</a>
    <a href="/descargar/abc123">DOWNLOAD PDF</a>
</body></html>
"""


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client


@pytest.fixture
def provider(mock_client):
    return HolaEbookProvider(http_client=mock_client)


class TestHolaEbookProvider:
    """Tests for HolaEbookProvider."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=SEARCH_HTML,
            content=SEARCH_HTML.encode(),
            headers={},
            url="https://holaebook.com/search?q=harry+potter",
        )

        results = await provider.search(query="harry potter")
        assert len(results) > 0
        assert results[0].title == "Harry Potter"
        assert results[0].guid.startswith("holaebook-")
        assert "download" in results[0].download_url

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_empty(self, provider, mock_client):
        results = await provider.search(query="")
        assert results == []
        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_http_error_returns_empty(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Connection error")
        results = await provider.search(query="test")
        assert results == []

    @pytest.mark.asyncio
    async def test_get_capabilities(self, provider):
        caps = provider.get_capabilities()
        assert caps.provider_id == "holaebook"
        assert caps.supports_book_search is True

    @pytest.mark.asyncio
    async def test_get_download_url_valid(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=DETAIL_HTML,
            content=DETAIL_HTML.encode(),
            headers={},
            url="https://holaebook.com/libro/abc123.html",
        )

        url = await provider.get_download_url("abc123")
        assert url is not None

    @pytest.mark.asyncio
    async def test_get_download_url_fallback_route(self, provider, mock_client):
        """When /libro/ returns non-200, fallback to /book/."""
        mock_client.get.side_effect = [
            ScraperResponse(
                status_code=404, text="Not found", content=b"",
                headers={}, url="https://holaebook.com/libro/abc123.html",
            ),
            ScraperResponse(
                status_code=200, text=DETAIL_HTML, content=DETAIL_HTML.encode(),
                headers={}, url="https://holaebook.com/book/abc123/",
            ),
        ]

        url = await provider.get_download_url("abc123")
        assert url is not None
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_get_download_url_no_match(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text="<html><body>No links here</body></html>",
            content=b"",
            headers={},
            url="https://holaebook.com/libro/unknown.html",
        )

        url = await provider.get_download_url("unknown")
        assert url is None

    @pytest.mark.asyncio
    async def test_get_download_url_error(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Network error")
        url = await provider.get_download_url("abc123")
        assert url is None

    @pytest.mark.asyncio
    async def test_search_fallback_url_on_404(self, provider, mock_client):
        """When /search?q= returns 404, fallback to /?s="""
        mock_client.get.side_effect = [
            ScraperResponse(
                status_code=404, text="Not found", content=b"",
                headers={}, url="https://holaebook.com/search?q=test",
            ),
            ScraperResponse(
                status_code=200, text=SEARCH_HTML, content=SEARCH_HTML.encode(),
                headers={}, url="https://holaebook.com/?s=test",
            ),
        ]

        results = await provider.search(query="test")
        assert len(results) > 0
        assert mock_client.get.call_count == 2
