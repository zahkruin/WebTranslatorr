"""
Tests for Bajaebooks provider (bajaebooks.py) — HTML scraping with redirect chain.

Covers: search (multi-domain fallback), get_download_url (redirect following),
edge cases.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.providers.books.bajaebooks import BajaebooksProvider
from app.core.models import SearchResult
from app.scraping.http_client import ScraperResponse


# ── HTML Fixtures ─────────────────────────────────────────────────────

SEARCH_HTML = """<html><body>
<div class="book-card">
    <h2><a href="/libro/el-quijote/" title="El Quijote">El Quijote</a></h2>
    <span class="author">Cervantes</span>
</div>
<article>
    <h3><a href="/book/cien-anos-de-soledad/">Cien Años de Soledad</a></h3>
</article>
<a href="/descargar/harry-potter/">Harry Potter</a>
<a href="/category/novela/">Novela</a>
</body></html>"""

SEARCH_HTML_FALLBACK = """<html><body>
<a href="/book/solo-un-libro/">Solo un libro</a>
</body></html>"""

SEARCH_HTML_NO_RESULTS = """<html><body><p>No books here</p></body></html>"""

DETAIL_HTML_BUTTON = """<html><body>
<a href="/download/12345/epub" class="btn">Descargar EPUB</a>
<p>Sinopsis del libro</p>
</body></html>"""

DETAIL_HTML_REDIRECT = """<html><body>
<a href="/go/12345/">Ir a la página de descarga</a>
</body></html>"""

REDIRECT_TARGET = """<html><body>
<a href="/files/book.epub">Click here</a>
</body></html>"""

DETAIL_HTML_NO_LINK = """<html><body><p>Sin descarga</p></body></html>"""


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client


@pytest.fixture
def provider(mock_client):
    with patch("app.providers.books.bajaebooks.settings") as mock_settings:
        mock_settings.BAJAEEBOOKS_DOMAIN = "https://bajaebooks.info"
        mock_settings.EXTERNAL_URL = "http://localhost:9811"
        return BajaebooksProvider(http_client=mock_client)


# ── search() Tests ────────────────────────────────────────────────────

class TestBajaebooksSearch:

    @pytest.mark.asyncio
    async def test_search_returns_results(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        assert len(results) >= 1
        assert all(isinstance(r, SearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_search_extracts_title(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        titles = [r.title for r in results]
        assert any("Quijote" in t for t in titles)
        assert any("Cien Años" in t for t in titles)

    @pytest.mark.asyncio
    async def test_search_deduplicates(self, provider, mock_client):
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
    async def test_search_http_error(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Connection error")
        results = await provider.search("quijote", categories=[7020])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_fallback_domain(self, provider, mock_client):
        """Primary domain fails, should try fallback domain."""
        mock_client.get.side_effect = [
            Exception("Primary domain down"),
            ScraperResponse(200, SEARCH_HTML_FALLBACK, b"", {}, "url2"),
        ]
        results = await provider.search("libro", categories=[7020])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_extracts_author(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        authors = [r.author for r in results if r.author]
        assert any("Cervantes" in a for a in authors)


# ── get_download_url() Tests ──────────────────────────────────────────

class TestBajaebooksDownload:

    @pytest.mark.asyncio
    async def test_download_direct_button(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_BUTTON, b"", {}, "url"
        )
        url = await provider.get_download_url("el-quijote", fmt="epub")
        assert url is not None
        assert "download/12345/epub" in url

    @pytest.mark.asyncio
    async def test_download_follows_redirect(self, provider, mock_client):
        mock_client.get.side_effect = [
            ScraperResponse(200, DETAIL_HTML_REDIRECT, b"", {}, "url1"),
            ScraperResponse(200, REDIRECT_TARGET, b"", {}, "url2"),
        ]
        url = await provider.get_download_url("el-quijote", fmt="epub")
        assert url is not None
        assert "files/book.epub" in url

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
    assert caps.provider_id == "bajaebooks"
    assert caps.supports_book_search is True
    assert 7020 in caps.supported_categories
