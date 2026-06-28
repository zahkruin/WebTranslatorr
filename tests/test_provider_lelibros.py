"""
Tests for LeLibros provider (lelibros.py) — HTML scraping with direct download.

Covers: search (multiple URL patterns), get_download_url (format-specific
buttons), edge cases.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.providers.books.lelibros import LeLibrosProvider
from app.core.models import SearchResult
from app.scraping.http_client import ScraperResponse


# ── HTML Fixtures ─────────────────────────────────────────────────────

SEARCH_HTML = """<html><body>
<article><h2><a href="/libro/el-quijote/">El Quijote</a></h2></article>
<div class="entry-content">
    <a href="/book/cien-anos-de-soledad/">Cien Años de Soledad</a>
    <a href="/category/novela/">Novela</a>
</div>
<div class="book">
    <a href="/libro/harry-potter/">Harry Potter</a>
</div>
</body></html>"""

SEARCH_HTML_ALT_PATTERN = """<html><body>
<div class="search-results">
    <a href="/book/cien-anos-de-soledad/">Cien Años de Soledad</a>
</div>
</body></html>"""

SEARCH_HTML_NO_RESULTS = """<html><body><p>No results found</p></body></html>"""

DETAIL_HTML_EPUB = """<html><body>
<a href="/download/12345/libro.epub">Descargar en EPUB</a>
<a href="/download/12345/libro.pdf">Descargar en PDF</a>
<a href="/download/12345/libro.mobi">Descargar en MOBI</a>
</body></html>"""

DETAIL_HTML_DIRECT_LINK = """<html><body>
<a href="/files/book.epub">Link</a>
</body></html>"""

DETAIL_HTML_GENERIC_DOWNLOAD = """<html><body>
<a href="/download/12345">DESCARGAR</a>
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
    with patch("app.providers.books.lelibros.settings") as mock_settings:
        mock_settings.LELIBROS_DOMAIN = "https://lelibros.online"
        mock_settings.EXTERNAL_URL = "http://localhost:9811"
        return LeLibrosProvider(http_client=mock_client)


# ── search() Tests ────────────────────────────────────────────────────

class TestLeLibrosSearch:

    @pytest.mark.asyncio
    async def test_search_returns_results(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        assert len(results) >= 1
        assert all(isinstance(r, SearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_search_extracts_ids(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        guids = [r.guid for r in results]
        assert any("el-quijote" in g for g in guids)

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
    async def test_search_tries_alternate_url(self, provider, mock_client):
        """When first URL returns 404, should try alternate pattern."""
        mock_client.get.side_effect = [
            ScraperResponse(404, "", b"", {}, "url"),
            ScraperResponse(200, SEARCH_HTML_ALT_PATTERN, b"", {}, "url2"),
        ]
        results = await provider.search("cien anos", categories=[7020])
        assert len(results) == 1


# ── get_download_url() Tests ──────────────────────────────────────────

class TestLeLibrosDownload:

    @pytest.mark.asyncio
    async def test_download_format_specific_epub(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_EPUB, b"", {}, "url"
        )
        url = await provider.get_download_url("el-quijote", fmt="epub")
        assert url is not None
        assert "libro.epub" in url

    @pytest.mark.asyncio
    async def test_download_format_specific_pdf(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_EPUB, b"", {}, "url"
        )
        url = await provider.get_download_url("el-quijote", fmt="pdf")
        assert url is not None
        assert "libro.pdf" in url

    @pytest.mark.asyncio
    async def test_download_format_specific_mobi(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_EPUB, b"", {}, "url"
        )
        url = await provider.get_download_url("el-quijote", fmt="mobi")
        assert url is not None
        assert "libro.mobi" in url

    @pytest.mark.asyncio
    async def test_download_extension_link(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_DIRECT_LINK, b"", {}, "url"
        )
        url = await provider.get_download_url("el-quijote", fmt="epub")
        assert url is not None
        assert "book.epub" in url

    @pytest.mark.asyncio
    async def test_download_generic_button(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_GENERIC_DOWNLOAD, b"", {}, "url"
        )
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
    assert caps.provider_id == "lelibros"
    assert caps.supports_book_search is True
    assert 7020 in caps.supported_categories
