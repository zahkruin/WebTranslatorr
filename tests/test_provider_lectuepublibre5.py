"""
Tests for LectuEpubLibre5 provider (lectuepublibre5.py) — Hybrid API + scraping.

Covers: search (API path + scraping fallback with multiple selectors),
get_download_url (triple path + text and extension strategies), edge cases.
"""
import json
import pytest
from unittest.mock import AsyncMock, patch

from app.providers.books.lectuepublibre5 import LectuEpubLibre5Provider
from app.core.models import SearchResult
from app.scraping.http_client import ScraperResponse

# ── HTML Fixtures ─────────────────────────────────────────────────────

SEARCH_HTML = """<html><body>
<h2 class="entry-title"><a href="/book/el-quijote/">El Quijote</a></h2>
<h3 class="entry-title"><a href="/libro/cien-anos/">Cien Años de Soledad</a></h3>
</body></html>"""

SEARCH_HTML_FILTERED_TITLES = """<html><body>
<a href="/book/biblioteca/">biblioteca</a>
<a href="/book/inicio/">inicio</a>
<a href="/book/home/">home</a>
<a href="/book/real-book/">Real Book Title</a>
</body></html>"""

DETAIL_HTML_TEXT = """<html><body>
<a href="/download/123">EN EPUB</a>
<a href="/genre/novela">Novela Nav</a>
</body></html>"""

DETAIL_HTML_EXTENSION = """<html><body>
<a href="/files/book.epub">link</a>
</body></html>"""

DETAIL_HTML_NAV_FILTERED = """<html><body>
<a href="/genre/novela">EN EPUB</a>
<a href="/autor/cervantes">DESCARGAR</a>
<a href="/download/real">DESCARGAR</a>
</body></html>"""

DETAIL_HTML_NO_LINK = """<html><body><p>No download</p></body></html>"""

# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client

@pytest.fixture
def provider(mock_client):
    with patch("app.providers.books.lectuepublibre5.WordPressApiClient"):
        prov = LectuEpubLibre5Provider(http_client=mock_client)
        prov._USE_API = False
        prov._api = None
        return prov

@pytest.fixture
def provider_api(mock_client):
    with patch("app.providers.books.lectuepublibre5.WordPressApiClient") as mock_cls:
        mock_cls.return_value.search = AsyncMock(return_value=[])
        prov = LectuEpubLibre5Provider(http_client=mock_client)
        return prov

# ── search() Tests ────────────────────────────────────────────────────

class TestLectuEpubLibre5Search:

    @pytest.mark.asyncio
    async def test_search_scrape_returns_results(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        assert len(results) == 2
        assert all(isinstance(r, SearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_search_filters_nav_titles(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_FILTERED_TITLES, b"", {}, "url"
        )
        results = await provider.search("test", categories=[7020])
        assert len(results) == 1
        assert results[0].title == "Real Book Title"

    @pytest.mark.asyncio
    async def test_search_empty_query(self, provider):
        results = await provider.search("", categories=[7020])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_http_error(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Error")
        results = await provider.search("quijote", categories=[7020])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_api_fallback_to_scrape(self, provider_api, mock_client):
        provider_api._api.search = AsyncMock(return_value=[])
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider_api.search("quijote", categories=[7020])
        assert len(results) >= 1

# ── get_download_url() Tests ──────────────────────────────────────────

class TestLectuEpubLibre5Download:

    @pytest.mark.asyncio
    async def test_download_text_link(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_TEXT, b"", {}, "url"
        )
        url = await provider.get_download_url("el-quijote", fmt="epub")
        assert url is not None
        assert "download/123" in url

    @pytest.mark.asyncio
    async def test_download_extension_link(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_EXTENSION, b"", {}, "url"
        )
        url = await provider.get_download_url("el-quijote", fmt="epub")
        assert url is not None
        assert "files/book.epub" in url

    @pytest.mark.asyncio
    async def test_download_filters_navigation_links(self, provider, mock_client):
        """Filter out /genre/ and /autor/ links."""
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_NAV_FILTERED, b"", {}, "url"
        )
        url = await provider.get_download_url("test", fmt="epub")
        assert url is not None
        assert "download/real" in url  # Not genre/ or autor/

    @pytest.mark.asyncio
    async def test_download_tries_triple_path(self, provider, mock_client):
        """Tests all three paths: /book/, /libro/, /descargar/."""
        mock_client.get.side_effect = [
            Exception("fail"),
            Exception("fail"),
            ScraperResponse(200, DETAIL_HTML_TEXT, b"", {}, "url3"),
        ]
        url = await provider.get_download_url("test", fmt="epub")
        assert url is not None

    @pytest.mark.asyncio
    async def test_download_all_paths_fail(self, provider, mock_client):
        mock_client.get.side_effect = [
            Exception("f1"), Exception("f2"), Exception("f3")
        ]
        url = await provider.get_download_url("test", fmt="epub")
        assert url is None

# ── Capabilities Test ─────────────────────────────────────────────────

def test_get_capabilities(provider):
    caps = provider.get_capabilities()
    assert caps.provider_id == "lectuepublibre5"
    assert caps.supports_book_search is True
