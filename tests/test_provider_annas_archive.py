"""
Tests for AnnasArchiveProvider.
"""

import pytest
from unittest.mock import AsyncMock

from app.scraping.http_client import ScraperResponse
from app.providers.books.annas_archive import AnnasArchiveProvider

SEARCH_HTML = """
<html><body>
    <a href="/md5/abc123def456">
        <h3>Harry Potter</h3>
    </a>
    <a href="/md5/def789ghi012">
        <div class="font-bold">El Señor de los Anillos</div>
    </a>
</body></html>
"""

DETAIL_HTML_SLOW_SERVER = """
<html><body>
    <a class="js-download-link" href="/download/slow/abc123">Slow Partner Server</a>
    <a class="js-download-link" href="/download/libgen/abc123">libgen</a>
</body></html>
"""

DETAIL_HTML_FALLBACK = """
<html><body>
    <a href="/download/abc123">Download Link</a>
    <a href="https://libgen.li/abc123">Libgen Link</a>
</body></html>
"""


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client


@pytest.fixture
def provider(mock_client):
    return AnnasArchiveProvider(http_client=mock_client)


class TestAnnasArchiveProvider:
    """Tests for AnnasArchiveProvider."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=SEARCH_HTML,
            content=SEARCH_HTML.encode(),
            headers={},
            url="https://annas-archive.org/search?q=harry+potter&lang=es&ext=epub",
        )

        results = await provider.search(query="harry potter")
        assert len(results) > 0
        assert results[0].guid.startswith("annasarchive-")
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
        assert caps.provider_id == "annasarchive"
        assert caps.supports_book_search is True

    @pytest.mark.asyncio
    async def test_get_download_url_slow_partner(self, provider, mock_client):
        """Should prefer Slow Partner Server links."""
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=DETAIL_HTML_SLOW_SERVER,
            content=DETAIL_HTML_SLOW_SERVER.encode(),
            headers={},
            url="https://annas-archive.org/md5/abc123def456",
        )

        url = await provider.get_download_url("abc123def456")
        assert url is not None
        assert "slow" in url

    @pytest.mark.asyncio
    async def test_get_download_url_fallback(self, provider, mock_client):
        """Should fall back to /download/ links when no slow partner."""
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=DETAIL_HTML_FALLBACK,
            content=DETAIL_HTML_FALLBACK.encode(),
            headers={},
            url="https://annas-archive.org/md5/abc123def456",
        )

        url = await provider.get_download_url("abc123def456")
        assert url is not None

    @pytest.mark.asyncio
    async def test_get_download_url_no_match(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text="<html><body>No links</body></html>",
            content=b"",
            headers={},
            url="https://annas-archive.org/md5/unknown",
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
            <a href="/md5/abc"><h3>Book</h3></a>
            <a href="/md5/abc"><h3>Book</h3></a>
        </body></html>
        """
        mock_client.get.return_value = ScraperResponse(
            status_code=200, text=html, content=html.encode(), headers={}, url="https://annas-archive.org/search?q=test"
        )
        results = await provider.search(query="test")
        assert len(results) == 1
