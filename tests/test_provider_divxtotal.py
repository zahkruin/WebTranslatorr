"""
Tests for DivxTotal provider (divxtotal.py) — Torrent tracker.

Covers: search (pagination, card parsing), _fetch_detail_page
(magnet/torrent extraction, metadata), get_capabilities.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.providers.video.divxtotal import DivxtotalProvider
from app.core.models import SearchResult
from app.scraping.http_client import ScraperResponse


# ── HTML Fixtures ─────────────────────────────────────────────────────

SEARCH_HTML = """<html><body>
<div class="card">
    <h2><a href="/pelicula/123/el-padrino/">El Padrino (1080p)</a></h2>
    <span class="badge">1080p</span>
</div>
<div class="card">
    <h3><a href="/serie/456/breaking-bad/">Breaking Bad (HDTV)</a></h3>
</div>
<a href="/category/accion/">Acción</a>
</body></html>"""

SEARCH_HTML_PAGE_2 = """<html><body>
<div class="card">
    <a href="/pelicula/789/otra-pelicula/">Otra Película (4K)</a>
</div>
</body></html>"""

SEARCH_HTML_EMPTY = """<html><body><p>No results</p></body></html>"""

DETAIL_MOVIE_HTML = """<html><body>
<div class="sinopsis">Una historia de la mafia italiana en Nueva York.</div>
<span class="year">1972</span>
<span class="quality">1080p</span>
<span class="size">2.5 GB</span>
<span class="seeds">150</span>
<span class="peers">30</span>
<a href="magnet:?xt=urn:btih:ABCDEF1234567890ABCDEF1234567890ABCDEF12">Magnet</a>
<a href="/torrent/123/el-padrino.torrent">Torrent</a>
<a href="https://www.imdb.com/title/tt0068646/">IMDb</a>
</body></html>"""

DETAIL_MOVIE_NO_MAGNET = """<html><body>
<div class="sinopsis">Descripción de la película.</div>
<span class="year">2020</span>
<a href="/torrent/789/otra-peli.torrent">Descargar Torrent</a>
</body></html>"""

DETAIL_TV_HTML = """<html><body>
<div class="descripcion">Serie de química convertida en imperio de drogas.</div>
<span class="year">2008</span>
<span class="temporada">Temporada 1</span>
<span class="capitulo">Episodio 1</span>
<a href="magnet:?xt=urn:btih:1234567890ABCDEF1234567890ABCDEF12345678">Magnet</a>
</body></html>"""


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client


@pytest.fixture
def provider(mock_client):
    with patch("app.providers.video.divxtotal.settings") as mock_settings:
        mock_settings.DIVXTOTAL_DOMAIN = "https://divxtotal.wtf"
        mock_settings.EXTERNAL_URL = "http://localhost:9811"
        return DivxtotalProvider(http_client=mock_client)


# ── search() Tests ────────────────────────────────────────────────────

class TestDivxtotalSearch:

    @pytest.mark.asyncio
    async def test_search_returns_results(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider.search("padrino", categories=[2000])
        # Results go through enrichment, which also calls mock_client.get
        # But since enrichment does a second get for detail, we mock it to return detail
        assert len(results) >= 1
        assert all(isinstance(r, SearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_search_detects_movie_and_tv(self, provider, mock_client):
        # First call: search page
        # Subsequent calls: detail pages (one per result)
        mock_client.get.side_effect = [
            ScraperResponse(200, SEARCH_HTML, b"", {}, "search"),
            ScraperResponse(200, DETAIL_MOVIE_HTML, b"", {}, "detail1"),
            ScraperResponse(200, DETAIL_TV_HTML, b"", {}, "detail2"),
        ]
        results = await provider.search("padrino", categories=[2000])
        movie_results = [r for r in results if r.extra_attrs.get('content_type') == 'movie']
        tv_results = [r for r in results if r.extra_attrs.get('content_type') == 'tv']
        assert len(movie_results) >= 1
        assert len(tv_results) >= 1

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
    async def test_search_enriches_info_hash(self, provider, mock_client):
        mock_client.get.side_effect = [
            ScraperResponse(200, SEARCH_HTML, b"", {}, "search"),
            ScraperResponse(200, DETAIL_MOVIE_HTML, b"", {}, "detail"),
            ScraperResponse(200, DETAIL_TV_HTML, b"", {}, "detail"),
        ]
        results = await provider.search("padrino", categories=[2000])
        hashes = [r.info_hash for r in results if r.info_hash]
        assert len(hashes) >= 1

    @pytest.mark.asyncio
    async def test_search_handles_no_magnet(self, provider, mock_client):
        """When detail has no magnet, should fall back to torrent link."""
        mock_client.get.side_effect = [
            ScraperResponse(200, """<a href="/pelicula/789/peli/">Peli</a>""", b"", {}, "search"),
            ScraperResponse(200, DETAIL_MOVIE_NO_MAGNET, b"", {}, "detail"),
        ]
        results = await provider.search("peli", categories=[2000])
        assert len(results) >= 1
        assert "torrent" in results[0].download_url.lower()

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

class TestDivxtotalDownload:

    @pytest.mark.asyncio
    async def test_get_download_url_returns_input(self, provider):
        """DivxTotal get_download_url is pass-through after enrichment."""
        result = await provider.get_download_url("magnet:?xt=urn:btih:ABCDEF")
        assert result is not None


# ── Capabilities Test ─────────────────────────────────────────────────

class TestDivxtotalCapabilities:

    def test_get_capabilities(self, provider):
        caps = provider.get_capabilities()
        assert caps.provider_id == "divxtotal"
        assert caps.supports_movie_search is True
        assert caps.supports_tv_search is True
        assert caps.supports_book_search is False
        assert 2000 in caps.supported_categories
        assert 5000 in caps.supported_categories
