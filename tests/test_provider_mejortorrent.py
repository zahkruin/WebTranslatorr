"""
Tests for MejorTorrentProvider.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.scraping.http_client import ScraperResponse
from app.providers.video.mejortorrent import MejorTorrentProvider

SEARCH_HTML = """
<html><body>
    <a href="/pelicula/12345/inception-2010-(BluRay-1080p)">Inception (BluRay-1080p)</a>
    <a href="/serie/67890/breaking-bad-(HDTV-720p)">Breaking Bad (HDTV-720p)</a>
</body></html>
"""

DETAIL_MOVIE_HTML = """
<html><body>
    <a href="/year/2010">2010</a>
    <a href="/genre/ciencia-ficcion">Ciencia Ficción</a>
    <a href="/genre/accion">Acción</a>
    <a href="inception-2010-bluray.torrent">Inception Torrent</a>
    <a href="https://www.imdb.com/title/tt1375666/">IMDB</a>
    Descripción: Una película sobre sueños
</body></html>
"""

DETAIL_SERIES_HTML = """
<html><body>
    <a href="/year/2008">2008</a>
    <a href="/genre/drama">Drama</a>
    <a href="breaking-bad-s01e01.torrent">S01E01 Torrent</a>
    <a href="breaking-bad-s01e02.torrent">S01E02 Torrent</a>
    Descripción: Una serie sobre química
</body></html>
"""


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client


@pytest.fixture
def provider(mock_client):
    return MejorTorrentProvider(http_client=mock_client)


class TestMejorTorrentProvider:
    """Tests for MejorTorrentProvider."""

    @pytest.mark.asyncio
    async def test_search_returns_movie_results(self, provider, mock_client):
        mock_client.get.side_effect = [
            ScraperResponse(
                status_code=200, text=SEARCH_HTML, content=SEARCH_HTML.encode(),
                headers={}, url="https://www42.mejortorrent.eu/busqueda?q=inception",
            ),
            ScraperResponse(
                status_code=200, text=DETAIL_MOVIE_HTML, content=DETAIL_MOVIE_HTML.encode(),
                headers={}, url="https://www42.mejortorrent.eu/pelicula/12345/inception-2010",
            ),
        ]

        results = await provider.search(query="inception", categories=[])
        assert len(results) > 0
        assert results[0].guid.startswith("mejortorrent-")
        assert results[0].download_url != ""

    @pytest.mark.asyncio
    async def test_search_with_imdb_id(self, provider, mock_client):
        mock_client.get.side_effect = [
            ScraperResponse(
                status_code=200,
                text='{"movie_results": [{"title": "Inception"}], "tv_results": []}',
                content=b'{"movie_results": [{"title": "Inception"}], "tv_results": []}',
                headers={},
                url="https://api.themoviedb.org/3/find/tt1375666",
            ),
            ScraperResponse(
                status_code=200, text=SEARCH_HTML, content=SEARCH_HTML.encode(),
                headers={}, url="https://www42.mejortorrent.eu/busqueda?q=Inception",
            ),
            ScraperResponse(
                status_code=200, text=DETAIL_MOVIE_HTML, content=DETAIL_MOVIE_HTML.encode(),
                headers={}, url="https://www42.mejortorrent.eu/pelicula/12345/inception-2010",
            ),
        ]

        results = await provider.search(query="", imdb_id="tt1375666", categories=[])
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_series_results(self, provider, mock_client):
        mock_client.get.side_effect = [
            ScraperResponse(
                status_code=200, text=SEARCH_HTML, content=SEARCH_HTML.encode(),
                headers={}, url="https://www42.mejortorrent.eu/busqueda?q=breaking+bad",
            ),
            ScraperResponse(
                status_code=200, text=DETAIL_MOVIE_HTML, content=DETAIL_MOVIE_HTML.encode(),
                headers={}, url="https://www42.mejortorrent.eu/pelicula/12345/inception-2010",
            ),
            ScraperResponse(
                status_code=200, text=DETAIL_SERIES_HTML, content=DETAIL_SERIES_HTML.encode(),
                headers={},
                url="https://www42.mejortorrent.eu/serie/67890/breaking-bad",
            ),
        ]

        results = await provider.search(query="breaking bad", categories=[])
        assert len(results) > 0
        assert any(r.episode is not None for r in results)
        assert any(r.season is not None for r in results)

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_empty(self, provider, mock_client):
        results = await provider.search(query="", categories=[])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_http_error_returns_empty(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Connection error")
        results = await provider.search(query="test", categories=[])
        assert results == []

    @pytest.mark.asyncio
    async def test_get_capabilities(self, provider):
        caps = provider.get_capabilities()
        assert caps.provider_id == "mejortorrent"
        assert caps.supports_tv_search is True
        assert caps.supports_movie_search is True
        assert 2000 in caps.supported_categories

    @pytest.mark.asyncio
    async def test_get_download_url_returns_id(self, provider):
        url = await provider.get_download_url("https://example.com/file.torrent", fmt="torrent")
        assert url == "https://example.com/file.torrent"

    @pytest.mark.asyncio
    async def test_tmdb_lookup_uses_json_loads(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text='{"movie_results": [{"title": "Inception"}], "tv_results": []}',
            content=b'{}',
            headers={},
            url="https://api.themoviedb.org/3/find/tt1375666",
        )
        with patch("app.providers.video.mejortorrent.settings") as mock_settings:
            mock_settings.TMDB_API_KEY = "test-key"
            title = await provider._resolve_imdb_to_spanish_title("tt1375666")
        assert title == "Inception"

    def test_quality_to_categories_movie(self, provider):
        cats = provider._quality_to_categories("BluRay-1080p", "movie")
        assert 2000 in cats
        assert 2040 in cats

    def test_quality_to_categories_tv(self, provider):
        cats = provider._quality_to_categories("HDTV-720p", "tv")
        assert 5000 in cats
        assert 5040 in cats

    def test_extract_season_episode(self, provider):
        # "show 1x02" matches (\d+)x(\d+)
        assert provider._extract_season_episode("show 1x02", 1) == (1, 2)
        # "show 2x3" matches (\d+)x(\d+)
        assert provider._extract_season_episode("show 2x3", 1) == (2, 3)
        # "Capitulo 5" pattern
        assert provider._extract_season_episode("Capitulo 5", 1) == (1, 5)
        # "show-s01e02" does not match any pattern, falls back to (1, fallback_ep)
        assert provider._extract_season_episode("show-s01e02", 1) == (1, 1)

    def test_extract_imdb_id(self, provider):
        from bs4 import BeautifulSoup
        html = '<a href="https://www.imdb.com/title/tt1375666/">IMDB</a>'
        soup = BeautifulSoup(html, "lxml")
        imdb = provider._extract_imdb_id(soup)
        assert imdb == "tt1375666"

    def test_extract_imdb_id_returns_none(self, provider):
        """Test _extract_imdb_id returns None when no IMDb link present (line 295)."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup("<html><body>No imdb here</body></html>", "lxml")
        assert provider._extract_imdb_id(soup) is None

    @pytest.mark.asyncio
    async def test_init_with_domain_resolver(self, mock_client):
        """Test domain_resolver overrides default domain (lines 51-53)."""
        mock_resolver = MagicMock()
        mock_resolver.get_current.return_value = "https://custom.mejortorrent.com"
        provider = MejorTorrentProvider(http_client=mock_client, domain_resolver=mock_resolver)
        assert "custom.mejortorrent.com" in provider.base_url

    @pytest.mark.asyncio
    async def test_search_with_season_filter(self, provider, mock_client):
        """Test season filtering in search (line 119)."""
        mock_client.get.side_effect = [
            ScraperResponse(
                status_code=200, text=SEARCH_HTML, content=SEARCH_HTML.encode(),
                headers={}, url="https://www42.mejortorrent.eu/busqueda?q=breaking+bad",
            ),
            ScraperResponse(
                status_code=200, text=DETAIL_SERIES_HTML, content=DETAIL_SERIES_HTML.encode(),
                headers={}, url="https://www42.mejortorrent.eu/serie/67890/breaking-bad",
            ),
        ]
        results = await provider.search(query="breaking bad", categories=[], season=1)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_with_offset(self, provider, mock_client):
        """Test offset slicing in search results (line 125)."""
        mock_client.get.side_effect = [
            ScraperResponse(
                status_code=200, text=SEARCH_HTML, content=SEARCH_HTML.encode(),
                headers={}, url="https://www42.mejortorrent.eu/busqueda?q=test",
            ),
            ScraperResponse(
                status_code=200, text=DETAIL_MOVIE_HTML, content=DETAIL_MOVIE_HTML.encode(),
                headers={}, url="https://www42.mejortorrent.eu/pelicula/12345/inception-2010",
            ),
            ScraperResponse(
                status_code=200, text=DETAIL_SERIES_HTML, content=DETAIL_SERIES_HTML.encode(),
                headers={}, url="https://www42.mejortorrent.eu/serie/67890/breaking-bad",
            ),
        ]
        results = await provider.search(query="test", categories=[], offset=10)
        assert isinstance(results, list)

    def test_build_search_url_with_page(self, provider):
        """Test _build_search_url with page > 1 (line 132)."""
        url = provider._build_search_url("test", page=2)
        assert "/busqueda/page/2" in url

    def test_parse_results_empty_text(self, provider):
        """Test _parse_results skips empty link text (line 147)."""
        html = '<html><body><a href="/pelicula/1/test/">   </a></body></html>'
        results = provider._parse_results(html)
        assert len(results) == 0

    def test_parse_results_documental(self, provider):
        """Test _parse_results parses /documental/ links (lines 156-160)."""
        html = '<html><body><a href="/documental/99/nature/">Nature (HDTV)</a></body></html>'
        results = provider._parse_results(html)
        assert len(results) == 1
        assert results[0].guid == "mejortorrent-99"

    def test_parse_results_no_match(self, provider):
        """Test _parse_results skips links without numeric ID (line 163)."""
        html = '<html><body><a href="/pelicula/abc/invalid/">Invalid</a></body></html>'
        results = provider._parse_results(html)
        assert len(results) == 0

    def test_parse_results_duplicate_id(self, provider):
        """Test _parse_results skips duplicate IDs (line 167)."""
        html = """
        <html><body>
            <a href="/pelicula/1/movie1/">Movie1 (BluRay-1080p)</a>
            <a href="/pelicula/1/movie1-dup/">Movie1 Dup (BluRay-1080p)</a>
        </body></html>
        """
        results = provider._parse_results(html)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_fetch_detail_no_torrent_links(self, provider, mock_client):
        """Test _fetch_detail_page when no torrent links exist (lines 220-221)."""
        from app.core.models import SearchResult
        result = SearchResult(
            title="Test Movie",
            guid="mejortorrent-999",
            link="https://example.com/pelicula/999/",
            download_url="",
        )
        html_no_torrent = """
        <html><body>
            <a href="/year/2020">2020</a>
            <a href="/genre/action">Action</a>
            Descripción: A test movie
        </body></html>
        """
        mock_client.get.return_value = ScraperResponse(
            status_code=200, text=html_no_torrent, content=html_no_torrent.encode(),
            headers={}, url="https://example.com/pelicula/999/",
        )
        results = await provider._fetch_detail_page(result)
        assert len(results) == 1
        # Description includes concatenated body text
        assert "A test movie" in results[0].description

    @pytest.mark.asyncio
    async def test_resolve_imdb_no_api_key(self, provider):
        """Test _resolve_imdb_to_spanish_title returns imdb_id when no API key (line 308)."""
        import config
        original_key = config.settings.TMDB_API_KEY
        config.settings.TMDB_API_KEY = ""
        try:
            result = await provider._resolve_imdb_to_spanish_title("tt1234567")
            assert result == "tt1234567"
        finally:
            config.settings.TMDB_API_KEY = original_key

    @pytest.mark.asyncio
    async def test_resolve_imdb_tv_results(self, provider, mock_client):
        """Test _resolve_imdb_to_spanish_title handles tv_results (lines 322-323)."""
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text='{"movie_results": [], "tv_results": [{"name": "Test Show"}]}',
            content=b'{}',
            headers={},
            url="https://api.themoviedb.org/3/find/tt1234567",
        )
        with patch("app.providers.video.mejortorrent.settings") as mock_settings:
            mock_settings.TMDB_API_KEY = "test-key"
            result = await provider._resolve_imdb_to_spanish_title("tt1234567")
        assert result == "Test Show"
