"""
Tests for LectulandiaProvider.
"""

import pytest
from unittest.mock import AsyncMock

from app.scraping.http_client import ScraperResponse
from app.providers.books.lectulandia import LectulandiaProvider

SEARCH_HTML = """
<html><body>
    <a href="/book/abc123/harry-potter/">Harry Potter</a>
    <a href="/book/def456/el-senor/">El Señor de los Anillos</a>
</body></html>
"""

DETAIL_HTML = """
<html><body>
    <a href="/download.php?id=abc123">Descargar</a>
</body></html>
"""

INTERMEDIATE_HTML = """
<html><body>
<script>var linkCode = "secret123";</script>
</body></html>
"""


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client


@pytest.fixture
def provider(mock_client):
    return LectulandiaProvider(http_client=mock_client)


class TestLectulandiaProvider:
    """Tests for LectulandiaProvider."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=SEARCH_HTML,
            content=SEARCH_HTML.encode(),
            headers={},
            url="https://ww3.lectulandia.co/search/harry+potter",
        )

        results = await provider.search(query="harry potter")
        assert len(results) > 0
        assert results[0].title == "Harry Potter"
        assert results[0].guid.startswith("lectulandia-")
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
        assert caps.provider_id == "lectulandia"
        assert caps.supports_book_search is True
        assert 7000 in caps.supported_categories

    @pytest.mark.asyncio
    async def test_get_download_url_full_flow(self, provider, mock_client):
        # First call: detail page → finds download.php
        # Second call: intermediate page → finds linkCode
        mock_client.get.side_effect = [
            ScraperResponse(
                status_code=200, text=DETAIL_HTML, content=DETAIL_HTML.encode(),
                headers={}, url="https://ww3.lectulandia.co/book/abc123/",
            ),
            ScraperResponse(
                status_code=200, text=INTERMEDIATE_HTML, content=INTERMEDIATE_HTML.encode(),
                headers={}, url="https://ww3.lectulandia.co/download.php?id=abc123",
            ),
        ]

        url = await provider.get_download_url("abc123")
        assert url is not None
        assert "secret123" in url
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_get_download_url_no_download_php(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text="<html><body>No download link here</body></html>",
            content=b"",
            headers={},
            url="https://ww3.lectulandia.co/book/unknown/",
        )

        url = await provider.get_download_url("unknown")
        assert url is None

    @pytest.mark.asyncio
    async def test_get_download_url_error(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Network error")
        url = await provider.get_download_url("abc123")
        assert url is None

    @pytest.mark.asyncio
    async def test_search_deduplicates_urls(self, provider, mock_client):
        html = """
        <html><body>
            <a href="/book/abc123/book/">Book</a>
            <a href="/book/abc123/book/">Book</a>
        </body></html>
        """
        mock_client.get.return_value = ScraperResponse(
            status_code=200, text=html, content=html.encode(), headers={}, url="https://ww3.lectulandia.co/search/test"
        )
        results = await provider.search(query="test")
        assert len(results) == 1
