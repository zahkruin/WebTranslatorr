"""
Tests for MundoEpubLibre1 provider (mundoepublibre1.py).

Nearly identical to LectuEpubLibre5 — tests cover the same patterns
with provider-specific IDs.
"""
import pytest
from unittest.mock import AsyncMock

from app.providers.books.mundoepublibre1 import MundoEpubLibre1Provider
from app.core.models import SearchResult
from app.scraping.http_client import ScraperResponse

# ── HTML Fixtures ─────────────────────────────────────────────────────

SEARCH_HTML = """<html><body>
<h2 class="entry-title"><a href="/book/el-quijote/">El Quijote</a></h2>
<h3 class="entry-title"><a href="/libro/cien-anos/">Cien Años de Soledad</a></h3>
<a href="/book/harry-potter/">Harry Potter</a>
</body></html>"""

SEARCH_HTML_FILTERED = """<html><body>
<a href="/book/biblioteca/">biblioteca</a>
<a href="/book/inicio/">inicio</a>
<a href="/book/home/">home</a>
<a href="/book/real-book/">Real Book</a>
</body></html>"""

DETAIL_HTML_TEXT = """<html><body>
<a href="/download/123">EN EPUB</a>
<a href="/genre/novela">Novela Nav</a>
</body></html>"""

DETAIL_HTML_EXTENSION = """<html><body>
<a href="/files/book.epub">Download</a>
</body></html>"""

DETAIL_HTML_NAV_FILTERED = """<html><body>
<a href="/genre/novela">EN EPUB</a>
<a href="/autor/cervantes">DESCARGAR</a>
<a href="/download/real">DESCARGAR</a>
</body></html>"""

# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_client():
    return AsyncMock(get=AsyncMock())

@pytest.fixture
def provider(mock_client):
    return MundoEpubLibre1Provider(http_client=mock_client)


# ── search() Tests ────────────────────────────────────────────────────

class TestMundoEpubLibre1Search:

    @pytest.mark.asyncio
    async def test_search_returns_results(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        assert len(results) >= 2
        assert all(isinstance(r, SearchResult) for r in results)
        assert results[0].guid.startswith("mundoepublibre1-")

    @pytest.mark.asyncio
    async def test_search_filters_titles(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_FILTERED, b"", {}, "url"
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
    async def test_search_applies_offset(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020], offset=1)
        assert isinstance(results, list)

# ── get_download_url() Tests ──────────────────────────────────────────

class TestMundoEpubLibre1Download:

    @pytest.mark.asyncio
    async def test_download_text_link_filtered(self, provider, mock_client):
        """Navigation links (/genre/, /autor/) are filtered out."""
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_NAV_FILTERED, b"", {}, "url"
        )
        url = await provider.get_download_url("test", fmt="epub")
        assert url is not None
        assert "download/real" in url

    @pytest.mark.asyncio
    async def test_download_extension_link(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_EXTENSION, b"", {}, "url"
        )
        url = await provider.get_download_url("test", fmt="epub")
        assert url is not None

    @pytest.mark.asyncio
    async def test_download_triple_path(self, provider, mock_client):
        mock_client.get.side_effect = [
            Exception("f1"), Exception("f2"),
            ScraperResponse(200, DETAIL_HTML_TEXT, b"", {}, "url3"),
        ]
        url = await provider.get_download_url("test", fmt="epub")
        assert url is not None

    @pytest.mark.asyncio
    async def test_download_all_fail(self, provider, mock_client):
        mock_client.get.side_effect = [Exception("f")] * 3
        url = await provider.get_download_url("test", fmt="epub")
        assert url is None

# ── Capabilities Test ─────────────────────────────────────────────────

def test_get_capabilities(provider):
    caps = provider.get_capabilities()
    assert caps.provider_id == "mundoepublibre1"
    assert caps.supports_book_search is True
