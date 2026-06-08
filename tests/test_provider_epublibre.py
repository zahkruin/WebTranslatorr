"""
Tests for EpubLibreProvider.
"""

import pytest
from unittest.mock import AsyncMock

from app.scraping.http_client import ScraperResponse
from app.providers.books.epublibre import EpubLibreProvider

SEARCH_HTML = """
<html><body>
    <a href="/book/abc123/harry-potter/">Harry Potter</a>
    <a href="/book/def456/el-senor/">El Señor de los Anillos</a>
    <a href="/biblioteca/">Biblioteca</a>
</body></html>
"""

DETAIL_HTML = """
<html><body>
    <a href="/descargar/abc123/epub">DESCARGAR EN EPUB</a>
    <a href="/descargar/abc123/pdf">DESCARGAR EN PDF</a>
</body></html>
"""


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client


@pytest.fixture
def provider(mock_client):
    return EpubLibreProvider(http_client=mock_client)


class TestEpubLibreProvider:
    """Tests for EpubLibreProvider."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=SEARCH_HTML,
            content=SEARCH_HTML.encode(),
            headers={},
            url="https://epublibre.bid/?s=harry+potter",
        )

        results = await provider.search(query="harry potter")
        assert len(results) > 0
        assert results[0].title == "Harry Potter"
        assert results[0].guid.startswith("epublibre-")
        assert "download" in results[0].download_url

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_empty(self, provider, mock_client):
        results = await provider.search(query="")
        assert results == []
        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_deduplicates_urls(self, provider, mock_client):
        html = """
        <html><body>
            <a href="/book/abc123/harry-potter/">Harry Potter</a>
            <a href="/book/abc123/harry-potter/">Harry Potter</a>
        </body></html>
        """
        mock_client.get.return_value = ScraperResponse(
            status_code=200, text=html, content=html.encode(), headers={}, url="https://epublibre.bid/?s=test"
        )
        results = await provider.search(query="test")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_http_error_returns_empty(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Connection error")
        results = await provider.search(query="test")
        assert results == []

    @pytest.mark.asyncio
    async def test_get_capabilities(self, provider):
        caps = provider.get_capabilities()
        assert caps.provider_id == "epublibre"
        assert caps.supports_book_search is True
        assert 7000 in caps.supported_categories

    @pytest.mark.asyncio
    async def test_get_download_url_valid(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=DETAIL_HTML,
            content=DETAIL_HTML.encode(),
            headers={},
            url="https://epublibre.bid/book/abc123/",
        )

        url = await provider.get_download_url("abc123", fmt="epub")
        assert url is not None
        assert "descargar" in url.lower() or "/book/" in url
        assert "epub" in url.lower()

    @pytest.mark.asyncio
    async def test_get_download_url_no_match(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text="<html><body>No download links here</body></html>",
            content=b"",
            headers={},
            url="https://epublibre.bid/book/unknown/",
        )

        url = await provider.get_download_url("unknown")
        assert url is None

    @pytest.mark.asyncio
    async def test_get_download_url_error(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Network error")
        url = await provider.get_download_url("abc123")
        assert url is None

    @pytest.mark.asyncio
    async def test_search_with_offset(self, provider, mock_client):
        html = """
        <html><body>
            <a href="/book/001/book1/">Book 1</a>
            <a href="/book/002/book2/">Book 2</a>
            <a href="/book/003/book3/">Book 3</a>
        </body></html>
        """
        mock_client.get.return_value = ScraperResponse(
            status_code=200, text=html, content=html.encode(), headers={}, url="https://epublibre.bid/?s=test"
        )

        results = await provider.search(query="test", offset=1)
        assert len(results) == 2
        assert results[0].title == "Book 2"
