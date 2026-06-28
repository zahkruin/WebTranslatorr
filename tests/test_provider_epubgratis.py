"""
Tests for Epubgratis provider (epubgratis.py) — Hybrid WP API + scraping.

Covers: search (API path + scraping fallback), get_download_url
(public links only, toggle reveal pattern), edge cases.
"""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.providers.books.epubgratis import EpubgratisProvider
from app.core.models import SearchResult
from app.scraping.http_client import ScraperResponse


# ── HTML Fixtures ─────────────────────────────────────────────────────

SEARCH_HTML = """<html><body>
<h2 class="entry-title"><a href="/epub-directory/el-quijote/">El Quijote</a></h2>
<div class="book-item">
    <a href="/libro/cien-anos-de-soledad/">Cien Años de Soledad</a>
</div>
<a href="/descargar/harry-potter/">Harry Potter</a>
<a href="/category/novela/">Novela</a>
</body></html>"""

SEARCH_HTML_CPT = """<html><body>
<a href="/epub_directory/poesia-completa/">Poesía Completa</a>
<div class="card"><a href="/book/rayuela/">Rayuela</a></div>
</body></html>"""

SEARCH_HTML_NO_MATCH = """<html><body><p>No books here</p></body></html>"""

DETAIL_HTML_PUBLIC_DOWNLOAD = """<html><body>
<a href="/download/12345/epub">Descargar EPUB</a>
<a href="/wp-login/private-download">Descarga Privada</a>
</body></html>"""

DETAIL_HTML_TOGGLE = """<html><body>
<div class="toggle-download mostrar">
    <a href="/files/book.epub">Enlace público</a>
    <a href="/login/private-download">Enlace privado</a>
</div>
</body></html>"""

DETAIL_HTML_NO_LINK = """<html><body><p>Sin descarga</p></body></html>"""

DETAIL_HTML_PRIVATE_ONLY = """<html><body>
<a href="/login/private-download">Descarga (requiere registro)</a>
<a href="/register/">Registrarse</a>
</body></html>"""

# Mock API response
API_POSTS = [
    {
        "id": 123, "date": "2026-06-01T10:00:00",
        "slug": "el-quijote", "link": "https://www.epubgratis.org/el-quijote/",
        "title": {"rendered": "El Quijote | Miguel de Cervantes"},
        "content": {"rendered": "<p>Great book content</p>"},
        "excerpt": {"rendered": "<p>La obra maestra de Cervantes</p>"},
        "type": "post", "yoast_head_json": {}
    }
]


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client


@pytest.fixture
def provider(mock_client):
    with patch("app.providers.books.epubgratis.WordPressApiClient") as mock_api_cls:
        mock_api_cls.return_value.search = AsyncMock(return_value=[])
        with patch("app.providers.books.epubgratis.settings") as mock_settings:
            mock_settings.EPUBGRATIS_DOMAIN = "https://www.epubgratis.org"
            mock_settings.EXTERNAL_URL = "http://localhost:9811"
            prov = EpubgratisProvider(http_client=mock_client)
            prov._USE_API = False  # Disable API for predictable scraping tests
            prov._api = None
            return prov


@pytest.fixture
def provider_api(mock_client):
    """Provider with API enabled."""
    with patch("app.providers.books.epubgratis.WordPressApiClient") as mock_api_cls:
        mock_api_cls.return_value.search = AsyncMock(return_value=[])
        with patch("app.providers.books.epubgratis.settings") as mock_settings:
            mock_settings.EPUBGRATIS_DOMAIN = "https://www.epubgratis.org"
            mock_settings.EXTERNAL_URL = "http://localhost:9811"
            prov = EpubgratisProvider(http_client=mock_client)
            return prov


# ── search() Tests ────────────────────────────────────────────────────

class TestEpubgratisSearch:

    @pytest.mark.asyncio
    async def test_search_scrape_returns_results(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        assert len(results) >= 1
        assert all(isinstance(r, SearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_search_scrape_epub_directory_cpt(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_CPT, b"", {}, "url"
        )
        results = await provider.search("poesia", categories=[7020])
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_scrape_deduplicates(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        links = [r.link for r in results]
        assert len(links) == len(set(links))

    @pytest.mark.asyncio
    async def test_search_empty_query(self, provider):
        results = await provider.search("", categories=[7020])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_scrape_http_error(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Connection error")
        results = await provider.search("quijote", categories=[7020])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_api_returns_results(self, provider_api, mock_client):
        """When API returns data, scraping should be skipped."""
        provider_api._api.search = AsyncMock(return_value=[
            SearchResult(
                title="API Book", guid="epubgratis-999",
                link="https://www.epubgratis.org/book/999/",
                download_url="http://localhost:9811/api/download?provider=epubgratis&id=999&fmt=epub",
                size_bytes=1000000, categories=[7020], description="From API"
            )
        ])
        results = await provider_api.search("quijote", categories=[7020])
        assert len(results) == 1
        assert results[0].title == "API Book"
        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_api_fallback_to_scrape(self, provider_api, mock_client):
        """When API returns empty, fall back to scraping."""
        provider_api._api.search = AsyncMock(return_value=[])
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider_api.search("quijote", categories=[7020])
        assert len(results) >= 1


# ── get_download_url() Tests ──────────────────────────────────────────

class TestEpubgratisDownload:

    @pytest.mark.asyncio
    async def test_download_public_link(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_PUBLIC_DOWNLOAD, b"", {}, "url"
        )
        url = await provider.get_download_url("el-quijote", fmt="epub")
        assert url is not None
        assert "download/12345/epub" in url

    @pytest.mark.asyncio
    async def test_download_toggle_reveal(self, provider, mock_client):
        """Should find links inside toggle/reveal elements."""
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_TOGGLE, b"", {}, "url"
        )
        url = await provider.get_download_url("el-quijote", fmt="epub")
        assert url is not None
        assert "files/book.epub" in url

    @pytest.mark.asyncio
    async def test_download_skips_private_links(self, provider, mock_client):
        """Should skip login-required links."""
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_PRIVATE_ONLY, b"", {}, "url"
        )
        url = await provider.get_download_url("el-quijote", fmt="epub")
        assert url is None

    @pytest.mark.asyncio
    async def test_download_no_link_found(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_NO_LINK, b"", {}, "url"
        )
        url = await provider.get_download_url("el-quijote", fmt="epub")
        assert url is None

    @pytest.mark.asyncio
    async def test_download_http_error(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Timeout")
        url = await provider.get_download_url("el-quijote", fmt="epub")
        assert url is None

    @pytest.mark.asyncio
    async def test_download_tries_alternate_paths(self, provider, mock_client):
        """Tries /libro/, /epub-directory/, etc."""
        mock_client.get.side_effect = [
            Exception("First path fail"),
            ScraperResponse(200, DETAIL_HTML_PUBLIC_DOWNLOAD, b"", {}, "url2"),
        ]
        url = await provider.get_download_url("el-quijote", fmt="epub")
        assert url is not None


# ── Capabilities Test ─────────────────────────────────────────────────

def test_get_capabilities(provider):
    caps = provider.get_capabilities()
    assert caps.provider_id == "epubgratis"
    assert caps.supports_book_search is True
    assert 7020 in caps.supported_categories
