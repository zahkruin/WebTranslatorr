"""
Tests for Ebiblioteca provider (ebiblioteca.py) — HTML scraping + ZIP extraction.

Covers: search (catalog-style results), get_download_url (ad chain navigation),
edge cases, is_zipped flag.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.providers.books.ebiblioteca import EbibliotecaProvider
from app.core.models import SearchResult
from app.scraping.http_client import ScraperResponse


# ── HTML Fixtures ─────────────────────────────────────────────────────

SEARCH_HTML_CATALOG = """<html><body>
<div class="card">
    <h2><a href="/libro/12345/">El Quijote</a></h2>
    <span class="author">Miguel de Cervantes</span>
    <span class="genre">Novela</span>
    <span class="size">1.5 MB</span>
</div>
<div class="card">
    <h3><a href="/book/67890/">Cien Años de Soledad</a></h3>
    <span class="author">Gabriel García Márquez</span>
    <span class="genre">Realismo mágico</span>
    <span class="size">800 KB</span>
</div>
<a href="/category/literatura/">Literatura</a>
</body></html>"""

SEARCH_HTML_TABLE = """<html><body>
<table>
<tr><td><a href="/id/111/">Libro Tabla 1</a></td><td>Autor Uno</td></tr>
<tr><td><a href="/id/222/">Libro Tabla 2</a></td><td>Autor Dos</td></tr>
</table>
</body></html>"""

SEARCH_HTML_NO_RESULTS = """<html><body><p>Sin resultados</p></body></html>"""

DETAIL_HTML_DIRECT_ZIP = """<html><body>
<a href="/download/12345/libro.zip">Descargar</a>
</body></html>"""

DETAIL_HTML_AD_CHAIN_1 = """<html><body>
<a href="/go/12345/">Completar e ir a la página de descarga</a>
</body></html>"""

DETAIL_HTML_AD_CHAIN_2 = """<html><body>
<a href="/final/12345/libro.zip">Descargar archivo</a>
</body></html>"""

DETAIL_HTML_NO_LINK = """<html><body><p>Sin botón de descarga</p></body></html>"""


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client


@pytest.fixture
def provider(mock_client):
    with patch("app.providers.books.ebiblioteca.settings") as mock_settings:
        mock_settings.EBIBLIOTECA_DOMAIN = "https://ebiblioteca.org"
        mock_settings.EXTERNAL_URL = "http://localhost:9811"
        return EbibliotecaProvider(http_client=mock_client)


# ── search() Tests ────────────────────────────────────────────────────

class TestEbibliotecaSearch:

    @pytest.mark.asyncio
    async def test_search_returns_results(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_CATALOG, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        assert len(results) >= 1
        assert all(isinstance(r, SearchResult) for r in results)

    @pytest.mark.asyncio
    async def test_search_extracts_metadata(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_CATALOG, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        guids = [r.guid for r in results]
        assert any("12345" in g for g in guids)
        # Check author extraction
        authors = [r.author for r in results if r.author]
        assert len(authors) >= 1

    @pytest.mark.asyncio
    async def test_search_deduplicates(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_CATALOG, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        guids = [r.guid for r in results]
        assert len(guids) == len(set(guids))

    @pytest.mark.asyncio
    async def test_search_table_layout(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_TABLE, b"", {}, "url"
        )
        results = await provider.search("libro", categories=[7020])
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_empty_query(self, provider):
        results = await provider.search("", categories=[7020])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_http_error(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Connection error")
        results = await provider.search("quijote", categories=[7020])
        assert results == []


# ── get_download_url() Tests ──────────────────────────────────────────

class TestEbibliotecaDownload:

    @pytest.mark.asyncio
    async def test_download_direct_zip(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_DIRECT_ZIP, b"", {}, "url"
        )
        url = await provider.get_download_url("12345", fmt="epub")
        assert url is not None
        assert "libro.zip" in url

    @pytest.mark.asyncio
    async def test_download_through_ad_chain(self, provider, mock_client):
        """Navigate through 'Completar e ir a la página de descarga' chain."""
        mock_client.get.side_effect = [
            ScraperResponse(200, DETAIL_HTML_AD_CHAIN_1, b"", {}, "url1"),
            ScraperResponse(200, DETAIL_HTML_AD_CHAIN_2, b"", {}, "url2"),
        ]
        url = await provider.get_download_url("12345", fmt="epub")
        assert url is not None
        assert "libro.zip" in url

    @pytest.mark.asyncio
    async def test_download_no_link_found(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_NO_LINK, b"", {}, "url"
        )
        url = await provider.get_download_url("12345", fmt="epub")
        assert url is None

    @pytest.mark.asyncio
    async def test_download_http_error(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Timeout")
        url = await provider.get_download_url("12345", fmt="epub")
        assert url is None


# ── ZIP Flag Test ─────────────────────────────────────────────────────

def test_is_zipped_flag():
    """Ebiblioteca must have is_zipped = True for ZipExtractor activation."""
    assert EbibliotecaProvider.is_zipped is True


# ── Capabilities Test ─────────────────────────────────────────────────

def test_get_capabilities(provider):
    caps = provider.get_capabilities()
    assert caps.provider_id == "ebiblioteca"
    assert caps.supports_book_search is True
    assert 7020 in caps.supported_categories
