"""
Tests for BookSee provider (booksee.py) — HTML scraping puro.

Covers: search (table parsing, author extraction, empty results, errors),
get_download_url (PDF link discovery, no-link, HTTP error), capabilities.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.providers.books.booksee import BookseeProvider
from app.core.models import SearchResult
from app.scraping.http_client import ScraperResponse


# ── HTML Fixtures ─────────────────────────────────────────────────────

BOOKSEE_SEARCH_HTML = """<html><body>
<div class="content">
<table class="results">
<tr>
  <td class="book-info">
    <h3><a href="/book/python-crash-course/">Python Crash Course</a></h3>
    <span class="author">Eric Matthes</span>
    <p class="description">A hands-on introduction to programming</p>
  </td>
</tr>
<tr>
  <td class="book-info">
    <h3><a href="/book/clean-code/">Clean Code</a></h3>
    <span class="author">Robert C. Martin</span>
  </td>
</tr>
<tr>
  <td class="book-info">
    <h3><a href="/book/design-patterns/">Design Patterns</a></h3>
    <span class="author">Gang of Four</span>
  </td>
</tr>
</table>
</div>
</body></html>"""

BOOKSEE_SEARCH_HTML_AUTHOR_ITEMPROP = """<html><body>
<table class="results">
<tr>
  <td>
    <h3><a href="/book/the-pragmatic-programmer/">The Pragmatic Programmer</a></h3>
    <span itemprop="author">David Thomas</span>
  </td>
</tr>
</table>
</body></html>"""

BOOKSEE_SEARCH_HTML_NO_RESULTS = """<html><body>
<div class="content">
<p>No books found matching your query.</p>
</div>
</body></html>"""

BOOKSEE_SEARCH_HTML_MALFORMED = """<html><body>
<div class="content">
<table class="results">
<tr><td>Header row — no book link here</td></tr>
<tr><td>Another row with <a href="/category/fiction/">Fiction</a> but no /book/ link</td></tr>
</table>
</div>
</body></html>"""

BOOKSEE_DETAIL_HTML_PDF = """<html><body>
<div class="book-detail">
  <h1>Python Crash Course</h1>
  <a href="/files/python-crash-course.pdf" download>Download PDF</a>
</div>
</body></html>"""

BOOKSEE_DETAIL_HTML_NO_LINK = """<html><body>
<div class="book-detail">
  <h1>Book Without Downloads</h1>
  <p>This book has no download available.</p>
  <a href="/book/other-book/">Related Book</a>
  <a href="/author/john-doe/">John Doe</a>
</div>
</body></html>"""


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mock_client():
    """Mock HTTP client with async get method."""
    client = AsyncMock()
    client.get = AsyncMock()
    return client


@pytest.fixture
def provider(mock_client):
    """BookSee provider with mocked settings and HTTP client."""
    with patch("app.providers.books.booksee.settings") as mock_settings:
        mock_settings.BOOKSEE_DOMAIN = "https://en.booksee.org"
        mock_settings.EXTERNAL_URL = "http://localhost:9811"
        return BookseeProvider(http_client=mock_client)


# ── search() Tests ────────────────────────────────────────────────────


class TestBookseeSearch:

    @pytest.mark.asyncio
    async def test_search_parses_results(self, provider, mock_client):
        """Should parse HTML table rows into SearchResults with correct fields."""
        mock_client.get.return_value = ScraperResponse(
            200, BOOKSEE_SEARCH_HTML, b"", {}, "https://en.booksee.org/?q=python&page=1"
        )

        results = await provider.search("python", categories=[7020])

        assert len(results) >= 3
        assert all(isinstance(r, SearchResult) for r in results)
        assert all(r.guid.startswith("booksee-") for r in results)
        assert all("api/download" in r.download_url for r in results)
        assert all("provider=booksee" in r.download_url for r in results)
        assert all("fmt=pdf" in r.download_url for r in results)
        # Verify first result details
        assert results[0].title == "Python Crash Course"
        assert "booksee-python-crash-course" in results[0].guid
        assert "en.booksee.org/book/python-crash-course/" in results[0].link

    @pytest.mark.asyncio
    async def test_search_handles_empty_results(self, provider, mock_client):
        """Should return empty list when HTML has no matching book containers."""
        mock_client.get.return_value = ScraperResponse(
            200, BOOKSEE_SEARCH_HTML_NO_RESULTS, b"", {}, "url"
        )

        results = await provider.search("nonexistent", categories=[7020])

        assert results == []

    @pytest.mark.asyncio
    async def test_search_handles_http_error(self, provider, mock_client):
        """Should return empty list when HttpClient raises an exception."""
        mock_client.get.side_effect = Exception("Connection refused")

        results = await provider.search("python", categories=[7020])

        assert results == []

    @pytest.mark.asyncio
    async def test_search_handles_empty_query(self, provider):
        """Should return empty list for empty query string."""
        results = await provider.search("", categories=[7020])

        assert results == []

    @pytest.mark.asyncio
    async def test_search_extracts_author(self, provider, mock_client):
        """Should extract author from span.author or span[itemprop='author']."""
        mock_client.get.return_value = ScraperResponse(
            200, BOOKSEE_SEARCH_HTML, b"", {}, "url"
        )

        results = await provider.search("python", categories=[7020])

        assert results[0].author == "Eric Matthes"
        assert results[1].author == "Robert C. Martin"
        assert results[2].author == "Gang of Four"

    @pytest.mark.asyncio
    async def test_search_extracts_author_itemprop(self, provider, mock_client):
        """Should extract author from span[itemprop='author'] fallback."""
        mock_client.get.return_value = ScraperResponse(
            200, BOOKSEE_SEARCH_HTML_AUTHOR_ITEMPROP, b"", {}, "url"
        )

        results = await provider.search("pragmatic", categories=[7020])

        assert len(results) == 1
        assert results[0].author == "David Thomas"

    @pytest.mark.asyncio
    async def test_search_deduplicates(self, provider, mock_client):
        """Should not return duplicate results for the same internal ID."""
        mock_client.get.return_value = ScraperResponse(
            200, BOOKSEE_SEARCH_HTML, b"", {}, "url"
        )

        results = await provider.search("python", categories=[7020])

        guids = [r.guid for r in results]
        assert len(guids) == len(set(guids))

    @pytest.mark.asyncio
    async def test_search_skips_malformed_rows(self, provider, mock_client):
        """Should skip rows without valid /book/ links without crashing."""
        mock_client.get.return_value = ScraperResponse(
            200, BOOKSEE_SEARCH_HTML_MALFORMED, b"", {}, "url"
        )

        results = await provider.search("fiction", categories=[7020])

        # All rows lack valid /book/ links → no results
        assert results == []


# ── get_download_url() Tests ──────────────────────────────────────────


class TestBookseeDownload:

    @pytest.mark.asyncio
    async def test_get_download_url_finds_pdf_link(self, provider, mock_client):
        """Should find direct PDF link on detail page and return absolute URL."""
        mock_client.get.return_value = ScraperResponse(
            200, BOOKSEE_DETAIL_HTML_PDF, b"", {},
            "https://en.booksee.org/book/python-crash-course/"
        )

        url = await provider.get_download_url("python-crash-course")

        assert url is not None
        assert "files/python-crash-course.pdf" in url
        assert url.startswith("https://en.booksee.org")

    @pytest.mark.asyncio
    async def test_get_download_url_handles_no_link(self, provider, mock_client):
        """Should return None when detail page has no downloadable links."""
        mock_client.get.return_value = ScraperResponse(
            200, BOOKSEE_DETAIL_HTML_NO_LINK, b"", {}, "url"
        )

        url = await provider.get_download_url("no-download-book")

        assert url is None

    @pytest.mark.asyncio
    async def test_get_download_url_handles_http_error(self, provider, mock_client):
        """Should return None when HttpClient raises an exception."""
        mock_client.get.side_effect = Exception("Timeout")

        url = await provider.get_download_url("python-crash-course")

        assert url is None

    @pytest.mark.asyncio
    async def test_get_download_url_finds_download_attribute(self, provider, mock_client):
        """Should find links with download attribute (Strategy 1)."""
        mock_client.get.return_value = ScraperResponse(
            200, BOOKSEE_DETAIL_HTML_PDF, b"", {},
            "https://en.booksee.org/book/python-crash-course/"
        )

        url = await provider.get_download_url("python-crash-course")

        # The HTML has <a ... download> which triggers Strategy 1
        assert url is not None
        assert "files/python-crash-course.pdf" in url


# ── Capabilities Test ─────────────────────────────────────────────────


def test_get_capabilities(provider):
    """Should declare book search support and English query language."""
    caps = provider.get_capabilities()
    assert caps.provider_id == "booksee"
    assert caps.display_name == "BookSee"
    assert caps.supports_book_search is True
    assert caps.query_language == "en"
    assert 7020 in caps.supported_categories
