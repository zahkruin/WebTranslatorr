"""
Tests for EliteTorrent provider (elitetorrent.py) — Torrent tracker.

Covers: search (pagination, quality detection), _fetch_detail_page
(magnet/torrent extraction, metadata, language), get_capabilities.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.providers.video.elitetorrent import EliteTorrentProvider
from app.core.models import SearchResult
from app.scraping.http_client import ScraperResponse


# ── HTML Fixtures ─────────────────────────────────────────────────────

SEARCH_HTML = """<html><body>
<article>
    <h2><a href="/peliculas/el-padrino/">El Padrino (4K)</a></h2>
</article>
<div class="item">
    <a href="/series/breaking-bad/">Breaking Bad (MicroHD)</a>
</div>
<div class="paginacion">
    <span class="current">1</span>
    <a href="/page/2/?s=padrino">2</a>
</div>
</body></html>"""

SEARCH_HTML_LAST_PAGE = """<html><body>
<div class="paginacion">
    <span class="current">2</span>
</div>
</body></html>"""

SEARCH_HTML_EMPTY = """<html><body><p>No results</p></body></html>"""

DETAIL_MOVIE_HTML = """<html><body>
<div class="sinopsis">La historia de la familia Corleone.</div>
<span class="year">1972</span>
<span class="quality">4K</span>
<span class="idioma">Español Latino</span>
<span class="size">5.2 GB</span>
<span class="seeds">200</span>
<span class="peers">45</span>
<a href="magnet:?xt=urn:btih:AAAABBBBCCCCDDDDEEEEFFFFGGGGHHHHIIII">Magnet</a>
<a href="/torrent/el-padrino.torrent">Torrent</a>
<a href="https://www.imdb.com/title/tt0068646/">IMDb</a>
</body></html>"""

DETAIL_MOVIE_TORRENT_ONLY = """<html><body>
<div class="sinopsis">Descripción.</div>
<a href="/torrents/otra-peli.torrent">Descargar Torrent</a>
</body></html>"""

DETAIL_TV_HTML = """<html><body>
<div class="descripcion">Drama sobre drogas y química.</div>
<span class="year">2008</span>
<a href="magnet:?xt=urn:btih:IIIIHHHHGGGGFFFFEEEEDDDDCCCCBBBBAAAA">Magnet</a>
<a href="https://www.imdb.com/title/tt0903747/">IMDb</a>
</body></html>"""


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client


@pytest.fixture
def provider(mock_client):
    with patch("app.providers.video.elitetorrent.settings") as mock_settings:
        mock_settings.ELITETORRENT_DOMAIN = "https://www.elitetorrent.com"
        mock_settings.EXTERNAL_URL = "http://localhost:9811"
        return EliteTorrentProvider(http_client=mock_client)


# ── search() Tests ────────────────────────────────────────────────────

class TestEliteTorrentSearch:

    @pytest.mark.asyncio
    async def test_search_returns_results(self, provider, mock_client):
        mock_client.get.side_effect = [
            ScraperResponse(200, SEARCH_HTML, b"", {}, "search"),
            ScraperResponse(200, DETAIL_MOVIE_HTML, b"", {}, "detail1"),
            ScraperResponse(200, DETAIL_TV_HTML, b"", {}, "detail2"),
        ]
        results = await provider.search("padrino", categories=[2000])
        assert len(results) >= 1
        assert all(isinstance(r, SearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_search_detects_quality(self, provider, mock_client):
        mock_client.get.side_effect = [
            ScraperResponse(200, SEARCH_HTML, b"", {}, "search"),
            ScraperResponse(200, DETAIL_MOVIE_HTML, b"", {}, "detail1"),
            ScraperResponse(200, DETAIL_TV_HTML, b"", {}, "detail2"),
        ]
        results = await provider.search("padrino", categories=[2000])
        qualities = [r.extra_attrs.get('quality', '') for r in results]
        assert any('4K' in q for q in qualities) or any('MicroHD' in q for q in qualities)

    @pytest.mark.asyncio
    async def test_search_enriches_magnet(self, provider, mock_client):
        mock_client.get.side_effect = [
            ScraperResponse(200, SEARCH_HTML, b"", {}, "search"),
            ScraperResponse(200, DETAIL_MOVIE_HTML, b"", {}, "detail"),
            ScraperResponse(200, DETAIL_TV_HTML, b"", {}, "detail"),
        ]
        results = await provider.search("padrino", categories=[2000])
        magnets = [r.magnet_uri for r in results if r.magnet_uri]
        assert len(magnets) >= 1

    @pytest.mark.asyncio
    async def test_search_enriches_imdb(self, provider, mock_client):
        mock_client.get.side_effect = [
            ScraperResponse(200, SEARCH_HTML, b"", {}, "search"),
            ScraperResponse(200, DETAIL_MOVIE_HTML, b"", {}, "detail"),
            ScraperResponse(200, DETAIL_TV_HTML, b"", {}, "detail"),
        ]
        results = await provider.search("padrino", categories=[2000])
        imdbs = [r.imdb_id for r in results if r.imdb_id]
        assert len(imdbs) >= 1

    @pytest.mark.asyncio
    async def test_search_handles_torrent_only(self, provider, mock_client):
        """When no magnet is available, should fall back to torrent URL."""
        mock_client.get.side_effect = [
            ScraperResponse(200, """<a href="/peliculas/otra-peli/">Peli</a>""", b"", {}, "search"),
            ScraperResponse(200, DETAIL_MOVIE_TORRENT_ONLY, b"", {}, "detail"),
        ]
        results = await provider.search("peli", categories=[2000])
        assert len(results) >= 1
        assert "torrent" in results[0].download_url.lower()

    @pytest.mark.asyncio
    async def test_search_extracts_language(self, provider, mock_client):
        mock_client.get.side_effect = [
            ScraperResponse(200, """<a href="/peliculas/el-padrino/">El Padrino</a>""", b"", {}, "search"),
            ScraperResponse(200, DETAIL_MOVIE_HTML, b"", {}, "detail"),
        ]
        results = await provider.search("padrino", categories=[2000])
        assert any("Español" in r.description for r in results)

    @pytest.mark.asyncio
    async def test_search_enriches_size(self, provider, mock_client):
        mock_client.get.side_effect = [
            ScraperResponse(200, """<a href="/peliculas/el-padrino/">El Padrino</a>""", b"", {}, "search"),
            ScraperResponse(200, DETAIL_MOVIE_HTML, b"", {}, "detail"),
        ]
        results = await provider.search("padrino", categories=[2000])
        movie_results = [r for r in results if r.extra_attrs.get('content_type') == 'movie']
        assert len(movie_results) >= 1
        assert movie_results[0].size_bytes > 0

    @pytest.mark.asyncio
    async def test_search_empty_query(self, provider):
        results = await provider.search("", categories=[2000])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_http_error(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Connection error")
        results = await provider.search("padrino", categories=[2000])
        assert results == []


# ── get_download_url() Tests ──────────────────────────────────────────

class TestEliteTorrentDownload:

    @pytest.mark.asyncio
    async def test_get_download_url_returns_input(self, provider):
        result = await provider.get_download_url("magnet:?xt=urn:btih:AAAABBBB")
        assert result is not None


# ── Capabilities Test ─────────────────────────────────────────────────

class TestEliteTorrentCapabilities:

    def test_get_capabilities(self, provider):
        caps = provider.get_capabilities()
        assert caps.provider_id == "elitetorrent"
        assert caps.supports_movie_search is True
        assert caps.supports_tv_search is True
        assert caps.supports_book_search is False
        assert 2000 in caps.supported_categories
        assert 5000 in caps.supported_categories
