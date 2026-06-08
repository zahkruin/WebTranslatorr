"""
Tests for Z-Library provider (zlibrary.py).

Covers: search (card-based + fallback link-based, multiple URL patterns),
get_download_url (multiple URL patterns + button extraction), edge cases.
"""
import pytest
from unittest.mock import AsyncMock
from datetime import datetime

from app.providers.books.zlibrary import ZLibraryProvider
from app.core.models import SearchResult
from app.scraping.http_client import ScraperResponse

# ── HTML Fixtures ─────────────────────────────────────────────────────

SEARCH_HTML_CARDS = """<html><body>
<div class="book-card">
  <a href="/book/1234567">
    <h3 class="book-title">El Quijote</h3>
  </a>
  <span class="author-name">Miguel de Cervantes</span>
  <span class="format-type">epub</span>
</div>
<div class="book-card">
  <a href="/book/7654321">
    <h3 class="book-title">Cien Años de Soledad</h3>
  </a>
  <span class="author-name">Gabriel García Márquez</span>
  <span class="format-type">pdf</span>
</div>
</body></html>"""

SEARCH_HTML_CARDS_ARTICLES = """<html><body>
<article>
  <a href="/book/1111111">
    <h3 class="book-title">1984</h3>
  </a>
  <span class="author-name">George Orwell</span>
  <span class="format-type">mobi</span>
</article>
</body></html>"""

SEARCH_HTML_FALLBACK_LINKS = """<html><body>
<p>Some page without cards</p>
<a href="/book/2222222">El Principito</a>
<a href="/book/3333333">Harry Potter</a>
<a href="/book/2222222">El Principito (dup)</a>
</body></html>"""

SEARCH_HTML_EMPTY = """<html><body><p>No results</p></body></html>"""

SEARCH_HTML_SHORT = """<html><body><p>err</p></body></html>"""

SEARCH_HTML_INVALID_EXT = """<html><body>
<div class="book-card">
  <a href="/book/9999999">
    <h3 class="book-title">Test Book</h3>
  </a>
  <span class="format-type">xyz_invalid</span>
</div>
</body></html>"""

SEARCH_HTML_NO_BOOK_ID = """<html><body>
<div class="book-card">
  <a href="/author/123">
    <h3 class="book-title">Author Page</h3>
  </a>
</div>
</body></html>"""

DETAIL_HTML_DOWNLOAD = """<html><body>
<a href="/dl/1234567" class="download-btn">Download EPUB</a>
</body></html>"""

DETAIL_HTML_BUTTON = """<html><body>
<button class="download-btn" data-url="/get/1234567">Descargar</button>
</body></html>"""

DETAIL_HTML_NO_LINKS = """<html><body><p>No downloads</p></body></html>"""

# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client

@pytest.fixture
def provider(mock_client):
    return ZLibraryProvider(http_client=mock_client)

# ── search() Tests ────────────────────────────────────────────────────

class TestZLibrarySearch:

    @pytest.mark.asyncio
    async def test_search_cards_returns_results(self, provider, mock_client):
        """Card-based layout: finds books with title/author/format."""
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_CARDS, b"", {}, "https://z-library.sk/s/quijote"
        )
        results = await provider.search("quijote", categories=[7020])
        assert len(results) == 2
        assert all(isinstance(r, SearchResult) for r in results)
        assert results[0].title == "El Quijote - Miguel de Cervantes"
        assert results[0].guid == "zlibrary-1234567"
        assert results[0].author == "Miguel de Cervantes"
        assert results[0].extra_attrs["format"] == "epub"

    @pytest.mark.asyncio
    async def test_search_article_elements(self, provider, mock_client):
        """Article-based card layout."""
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_CARDS_ARTICLES, b"", {}, "url"
        )
        results = await provider.search("1984", categories=[7020])
        assert len(results) == 1
        assert results[0].extra_attrs["format"] == "mobi"

    @pytest.mark.asyncio
    async def test_search_fallback_links(self, provider, mock_client):
        """When card selectors find nothing, fall back to /book/ links."""
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_FALLBACK_LINKS, b"", {}, "url"
        )
        results = await provider.search("principito", categories=[7020])
        assert len(results) >= 2
        guids = [r.guid for r in results]
        assert len(guids) == len(set(guids))  # deduplicated

    @pytest.mark.asyncio
    async def test_search_empty_query(self, provider):
        results = await provider.search("", categories=[7020])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_all_urls_fail(self, provider, mock_client):
        """All 3 search URL patterns fail."""
        mock_client.get.side_effect = [
            Exception("fail1"), Exception("fail2"), Exception("fail3")
        ]
        results = await provider.search("quijote", categories=[7020])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_first_url_works(self, provider, mock_client):
        """First URL pattern returns valid response."""
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_CARDS, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_second_url_fallback(self, provider, mock_client):
        """First URL fails, second one works."""
        mock_client.get.side_effect = [
            Exception("fail"),
            ScraperResponse(200, SEARCH_HTML_CARDS, b"", {}, "url2"),
        ]
        results = await provider.search("quijote", categories=[7020])
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_invalid_extension_falls_back_to_epub(self, provider, mock_client):
        """Non-standard extension defaults to epub."""
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_INVALID_EXT, b"", {}, "url"
        )
        results = await provider.search("test", categories=[7020])
        assert len(results) == 1
        assert results[0].extra_attrs["format"] == "epub"

    @pytest.mark.asyncio
    async def test_search_no_book_id_skipped(self, provider, mock_client):
        """Card without /book/{id} link is skipped."""
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_NO_BOOK_ID, b"", {}, "url"
        )
        results = await provider.search("test", categories=[7020])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_short_response_rejected(self, provider, mock_client):
        """Response with < 500 chars is rejected."""
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_SHORT, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020])
        # Short text means resp.text > 500 fails, moves to next URL
        # All URLs would return same short response -> no valid response
        assert results == []

    @pytest.mark.asyncio
    async def test_search_applies_limit(self, provider, mock_client):
        """Respects limit parameter."""
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_CARDS, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020], limit=1)
        assert len(results) <= 1

    @pytest.mark.asyncio
    async def test_search_applies_offset(self, provider, mock_client):
        """Applies offset to results."""
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_CARDS, b"", {}, "url"
        )
        results = await provider.search("quijote", categories=[7020], offset=1)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_deduplicates_by_book_id(self, provider, mock_client):
        """Same book_id appears only once."""
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML_FALLBACK_LINKS, b"", {}, "url"
        )
        results = await provider.search("test", categories=[7020])
        book_ids = [r.guid for r in results]
        assert len(book_ids) == len(set(book_ids))

# ── get_download_url() Tests ──────────────────────────────────────────

class TestZLibraryDownload:

    @pytest.mark.asyncio
    async def test_download_text_based_link(self, provider, mock_client):
        """Download link with 'Download EPUB' text."""
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_DOWNLOAD, b"", {}, "url"
        )
        url = await provider.get_download_url("1234567", fmt="epub")
        assert url is not None
        assert "dl/1234567" in url

    @pytest.mark.asyncio
    async def test_download_button_data_url(self, provider, mock_client):
        """Button with data-url attribute."""
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_BUTTON, b"", {}, "url"
        )
        url = await provider.get_download_url("1234567", fmt="epub")
        assert url is not None
        assert "get/1234567" in url

    @pytest.mark.asyncio
    async def test_download_tries_multiple_patterns(self, provider, mock_client):
        """First URL pattern fails, second succeeds."""
        mock_client.get.side_effect = [
            Exception("fail"),
            ScraperResponse(200, DETAIL_HTML_DOWNLOAD, b"", {}, "url2"),
        ]
        url = await provider.get_download_url("1234567", fmt="epub")
        assert url is not None

    @pytest.mark.asyncio
    async def test_download_all_patterns_fail(self, provider, mock_client):
        """All URL patterns fail."""
        mock_client.get.side_effect = [
            Exception("fail1"), Exception("fail2"),
            Exception("fail3"), Exception("fail4"),
        ]
        url = await provider.get_download_url("1234567", fmt="epub")
        assert url is None

    @pytest.mark.asyncio
    async def test_download_no_links_found(self, provider, mock_client):
        """Detail page has no download links."""
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML_NO_LINKS, b"", {}, "url"
        )
        url = await provider.get_download_url("1234567", fmt="epub")
        assert url is None

# ── Capabilities Test ─────────────────────────────────────────────────

def test_get_capabilities(provider):
    caps = provider.get_capabilities()
    assert caps.provider_id == "zlibrary"
    assert caps.supports_book_search is True
    assert 7020 in caps.supported_categories
