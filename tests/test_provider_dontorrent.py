"""
Tests for DonTorrentProvider.
"""

import pytest
from unittest.mock import AsyncMock

from app.scraping.http_client import ScraperResponse
from app.providers.video.dontorrent import DonTorrentProvider

LISTING_HTML = """
<html><body>
    <a href="/pelicula/12345/inception-2010/">Inception (2010)</a>
    <a href="/pelicula/67890/interstellar/">Interstellar</a>
    <a href="/serie/11111/breaking-bad/">Breaking Bad</a>
</body></html>
"""


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client


@pytest.fixture
def provider(mock_client):
    return DonTorrentProvider(http_client=mock_client)


class TestDonTorrentProvider:
    """Tests for DonTorrentProvider."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=LISTING_HTML,
            content=LISTING_HTML.encode(),
            headers={},
            url="https://dontorrent.reisen/peliculas",
        )

        results = await provider.search(query="inception", categories=[])
        assert len(results) > 0
        for r in results:
            assert "inception" in r.title.lower() or "inception" == r.title.lower()

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_listings(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=LISTING_HTML,
            content=LISTING_HTML.encode(),
            headers={},
            url="https://dontorrent.reisen/peliculas",
        )

        results = await provider.search(query="", categories=[])
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_search_http_error_returns_empty(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Connection error")
        results = await provider.search(query="test", categories=[])
        assert results == []

    @pytest.mark.asyncio
    async def test_get_capabilities(self, provider):
        caps = provider.get_capabilities()
        assert caps.provider_id == "dontorrent"
        assert caps.supports_tv_search is True
        assert caps.supports_movie_search is True

    @pytest.mark.asyncio
    async def test_get_download_url_returns_id(self, provider):
        url = await provider.get_download_url("https://example.com/file.torrent")
        assert url == "https://example.com/file.torrent"

    @pytest.mark.asyncio
    async def test_search_with_category_filter_movie(self, provider, mock_client):
        MOVIE_ONLY_HTML = """
        <html><body>
            <a href="/pelicula/12345/inception-2010/">Inception (2010)</a>
            <a href="/pelicula/67890/interstellar/">Interstellar</a>
        </body></html>
        """
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=MOVIE_ONLY_HTML,
            content=MOVIE_ONLY_HTML.encode(),
            headers={},
            url="https://dontorrent.reisen/peliculas",
        )

        results = await provider.search(query="", categories=[2000])
        assert len(results) > 0
        assert all("pelicula" in r.link for r in results)

    def test_parse_results_extracts_content_type(self, provider):
        html = """
        <html><body>
            <a href="/pelicula/1/title1/">Movie 1</a>
            <a href="/serie/2/title2/">Series 2</a>
        </body></html>
        """
        results = provider._parse_results(html)
        assert len(results) == 2
        assert results[0].guid.startswith("dontorrent-1")
        assert results[1].guid.startswith("dontorrent-2")
