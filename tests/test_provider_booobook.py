"""
Tests for B00k.Bond provider (booobook.py).

Covers: search (multiple URL patterns + 5 selectors + aggressive filtering),
get_download_url (triple path + text/extension strategies), edge cases.
"""
import pytest
from unittest.mock import AsyncMock

from app.providers.books.booobook import BooobookProvider
from app.core.models import SearchResult
from app.scraping.http_client import ScraperResponse

# ── HTML Fixtures ─────────────────────────────────────────────────────

SEARCH_HTML = """<html><body>
<h2 class="entry-title"><a href="/book/el-quijote/">El Quijote</a></h2>
<article><a href="/libro/cien-anos/">Cien Años de Soledad</a></article>
</body></html>"""

SEARCH_HTML_NAV_LINKS = """<html><body>
<a href="/genre/novela/">Novela</a>
<a href="/autor/cervantes/">Cervantes</a>
<a href="/category/libros/">Libros</a>
<a href="/tag/clasicos/">Clásicos</a>
<a href="/page/about/">About</a>
<a href="#">Skip</a>
<a href="/book/real-book/">Real Book</a>
</body></html>"""

SEARCH_HTML_FILTERED_TITLES = """<html><body>
<a href="/book/inicio/">inicio</a>
<a href="/book/home/">home</a>
<a href="/book/biblioteca/">biblioteca</a>
<a href="/book/contacto/">contacto</a>
<a href="/book/real/">Real Book</a>
</body></html>"""

SEARCH_HTML_FALLBACK_URL = """<html><body>
<a href="/search/el-quijote">Search result</a>
</body></html>"""

DETAIL_HTML_TEXT = """<html><body>
<a href="/download/123">EN EPUB</a>
</body></html>"""

DETAIL_HTML_EXT = """<html><body>
<a href="/files/book.epub">Download</a>
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
    return BooobookProvider(http_client=mock_client)

# ── search() Tests ────────────────────────────────────────────────────

class TestBooobookSearch:

    @pytest.mark.asyncio
    async def test_search_returns_results(self, provider, mock_client):
        """First URL pattern works, returns book results."""
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        assert len(results) == 2
        assert all(isinstance(r, SearchResult) for r in results)
        assert results[0].guid.startswith("booobook-")

    @pytest.mark.asyncio
    async def test_search_filters_nav_links(self, provider, mock_client):
        """Filters out /genre/, /autor/, /category/, /tag/, /page/, # links."""
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_NAV_LINKS, b"", {}, "url"
        )
        results = await provider.search("test", categories=[7020])
        assert len(results) == 1
        assert results[0].title == "Real Book"

    @pytest.mark.asyncio
    async def test_search_filters_site_titles(self, provider, mock_client):
        """Filters out 'inicio', 'home', 'biblioteca', 'contacto'."""
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_FILTERED_TITLES, b"", {}, "url"
        )
        results = await provider.search("test", categories=[7020])
        assert len(results) == 1
        assert results[0].title == "Real Book"

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
    async def test_search_fallback_url_pattern(self, provider, mock_client):
        """First URL fails, second (/search/{query}) succeeds."""
        mock_client.get.side_effect = [
            Exception("first fail"),
            ScraperResponse(200, SEARCH_HTML, b"", {}, "url2"),
        ]
        results = await provider.search("quijote", categories=[7020])
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_all_urls_fail(self, provider, mock_client):
        mock_client.get.side_effect = [
            Exception("f1"), Exception("f2")
        ]
        results = await provider.search("quijote", categories=[7020])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_applies_limit(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020], limit=1)
        assert len(results) <= 1

# ── get_download_url() Tests ──────────────────────────────────────────

class TestBooobookDownload:

    @pytest.mark.asyncio
    async def test_download_text_link(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_TEXT, b"", {}, "url"
        )
        url = await provider.get_download_url("el-quijote", fmt="epub")
        assert url is not None

    @pytest.mark.asyncio
    async def test_download_extension_link(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_EXT, b"", {}, "url"
        )
        url = await provider.get_download_url("el-quijote", fmt="epub")
        assert url is not None

    @pytest.mark.asyncio
    async def test_download_triple_path(self, provider, mock_client):
        """Tests all three paths: /book/, /libro/, /descargar/."""
        mock_client.get.side_effect = [
            Exception("f1"), Exception("f2"),
            ScraperResponse(200, DETAIL_HTML_TEXT, b"", {}, "url3"),
        ]
        url = await provider.get_download_url("test", fmt="epub")
        assert url is not None

    @pytest.mark.asyncio
    async def test_download_all_fail(self, provider, mock_client):
        mock_client.get.side_effect = [Exception("f1")] * 3
        url = await provider.get_download_url("test", fmt="epub")
        assert url is None

# ── Capabilities Test ─────────────────────────────────────────────────

def test_get_capabilities(provider):
    caps = provider.get_capabilities()
    assert caps.provider_id == "booobook"
    assert caps.supports_book_search is True
