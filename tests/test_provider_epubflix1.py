"""
Tests for Epubflix1 provider (epubflix1.py) — Hybrid API + scraping.

Covers: search (API path + scraping fallback), get_download_url
(double path /book/ + /libro/), edge cases.
"""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.providers.books.epubflix1 import Epubflix1Provider
from app.core.models import SearchResult
from app.scraping.http_client import ScraperResponse

# ── HTML Fixtures ─────────────────────────────────────────────────────

SEARCH_HTML = """<html><body>
<h2 class="entry-title"><a href="/book/el-quijote/">El Quijote</a></h2>
<h3 class="entry-title"><a href="/libro/cien-anos-de-soledad/">Cien Años de Soledad</a></h3>
<a href="/book/harry-potter/">Harry Potter</a>
<a href="/genre/fantasia/">Fantasía</a>
</body></html>"""

SEARCH_HTML_DUP = """<html><body>
<a href="/book/el-quijote/">El Quijote</a>
<a href="/book/el-quijote/">El Quijote (dup)</a>
</body></html>"""

SEARCH_HTML_NO_MATCH = """<html><body><p>No books here</p></body></html>"""

DETAIL_HTML_DOWNLOAD = """<html><body>
<a href="/download/12345/epub">EN EPUB</a>
<a href="/genre/novela">Novela</a>
</body></html>"""

DETAIL_HTML_EXTENSION = """<html><body>
<a href="/files/book.epub">Link</a>
</body></html>"""

DETAIL_HTML_NO_LINK = """<html><body><p>Sin descarga</p></body></html>"""

# Mock API response
API_POSTS = [
    {
        "id": 123, "date": "2026-04-19T08:42:37",
        "slug": "el-quijote", "link": "https://epubflix1.com/el-quijote/",
        "title": {"rendered": "El Quijote | Miguel de Cervantes"},
        "content": {"rendered": "<p>Content</p>"},
        "excerpt": {"rendered": "<p>Great book</p>"},
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
    # Patch WordPressApiClient where it's imported in epubflix1 module
    with patch("app.providers.books.epubflix1.WordPressApiClient") as mock_api_cls:
        mock_api_cls.return_value.search = AsyncMock(return_value=[])
        prov = Epubflix1Provider(http_client=mock_client)
        prov._USE_API = False  # Disable API for predictable scraping tests
        prov._api = None
        return prov

@pytest.fixture
def provider_api(mock_client):
    """Provider with API enabled for hybrid tests."""
    with patch("app.providers.books.epubflix1.WordPressApiClient") as mock_api_cls:
        mock_api_cls.return_value.search = AsyncMock(return_value=[])
        prov = Epubflix1Provider(http_client=mock_client)
        return prov


# ── search() Tests ────────────────────────────────────────────────────

class TestEpubflix1Search:

    @pytest.mark.asyncio
    async def test_search_scrape_returns_results(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        assert len(results) >= 1
        assert all(isinstance(r, SearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_search_scrape_extracts_id(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        assert results[0].guid == "epubflix1-el-quijote"
        assert "epubflix1.com/book/el-quijote" in results[0].link

    @pytest.mark.asyncio
    async def test_search_scrape_deduplicates(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_DUP, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        assert len(results) == 1

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
                title="API Book", guid="epubflix1-999",
                link="https://epubflix1.com/book/999/",
                download_url="http://localhost:9811/api/download?provider=epubflix1&id=999&fmt=epub",
                size_bytes=1000000, categories=[7020], description="From API"
            )
        ])
        results = await provider_api.search("quijote", categories=[7020])
        assert len(results) == 1
        assert results[0].title == "API Book"
        # HTTP client should NOT have been called for scraping
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

class TestEpubflix1Download:

    @pytest.mark.asyncio
    async def test_download_text_link(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_DOWNLOAD, b"", {}, "url"
        )
        url = await provider.get_download_url("el-quijote", fmt="epub")
        assert url is not None
        assert "download/12345" in url

    @pytest.mark.asyncio
    async def test_download_extension_link(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_EXTENSION, b"", {}, "url"
        )
        url = await provider.get_download_url("el-quijote", fmt="epub")
        assert url is not None
        assert "files/book.epub" in url

    @pytest.mark.asyncio
    async def test_download_tries_both_paths(self, provider, mock_client):
        """First path /book/ fails, second /libro/ succeeds."""
        mock_client.get.side_effect = [
            Exception("first fail"),
            ScraperResponse(200, DETAIL_HTML_DOWNLOAD, b"", {}, "url2"),
        ]
        url = await provider.get_download_url("el-quijote", fmt="epub")
        assert url is not None

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

# ── Capabilities Test ─────────────────────────────────────────────────

def test_get_capabilities(provider):
    caps = provider.get_capabilities()
    assert caps.provider_id == "epubflix1"
    assert caps.supports_book_search is True
    assert 7020 in caps.supported_categories
