"""
Tests for OceanOfPDF provider (oceanofpdf.py) — Híbrido WP API + HTML scraping.

Covers: search (API path, scraping fallback, empty results, errors),
get_download_url (EPUB link discovery, no-link, HTTP error), capabilities.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.providers.books.oceanofpdf import OceanOfPDFProvider
from app.core.models import SearchResult
from app.scraping.http_client import ScraperResponse


# ── HTML Fixtures ─────────────────────────────────────────────────────

OCEANOFPDF_SEARCH_HTML = """<html><body>
<div class="site-content">
<article class="post">
  <h2 class="entry-title">
    <a href="/python-for-data-science/" rel="bookmark">Python for Data Science | Jake VanderPlas</a>
  </h2>
  <div class="entry-meta">by Jake VanderPlas on June 15, 2025</div>
</article>
<article class="type-post">
  <h2 class="entry-title">
    <a href="/deep-learning-with-python/" rel="bookmark">Deep Learning with Python</a>
  </h2>
  <div class="entry-meta">by François Chollet</div>
</article>
<article class="post">
  <h2 class="entry-title">
    <a href="/clean-architecture/">Clean Architecture</a>
  </h2>
  <div class="entry-meta">by Robert C. Martin</div>
</article>
</div>
</body></html>"""

OCEANOFPDF_SEARCH_HTML_ALT_SELECTORS = """<html><body>
<article class="post">
  <h2 class="entry-title">
    <a href="/machine-learning-yearning/" rel="bookmark">Machine Learning Yearning</a>
  </h2>
</article>
<article class="post">
  <div class="entry-title">
    <a href="/hands-on-ml/">Hands-On Machine Learning</a>
  </div>
</article>
</body></html>"""

OCEANOFPDF_SEARCH_HTML_NO_RESULTS = """<html><body>
<div class="no-results">
<p>Sorry, no posts matched your criteria.</p>
</div>
</body></html>"""

OCEANOFPDF_SEARCH_HTML_SKIP_LINKS = """<html><body>
<article class="post">
  <h2 class="entry-title">
    <a href="/category/fiction/" rel="bookmark">Fiction</a>
  </h2>
</article>
<article class="post">
  <h2 class="entry-title">
    <a href="/tag/bestseller/" rel="bookmark">Bestseller</a>
  </h2>
</article>
<article class="post">
  <h2 class="entry-title">
    <a href="javascript:void(0)" rel="bookmark">JavaScript Link</a>
  </h2>
</article>
</body></html>"""

OCEANOFPDF_DETAIL_HTML_EPUB = """<html><body>
<article class="post">
  <h1 class="entry-title">Python for Data Science</h1>
  <div class="entry-content">
    <p>Download your copy:</p>
    <a href="/download/1234/python-data-science.epub" class="download-btn">Download EPUB</a>
  </div>
</article>
</body></html>"""

OCEANOFPDF_DETAIL_HTML_NO_LINK = """<html><body>
<article class="post">
  <h1 class="entry-title">Book Without Downloads</h1>
  <div class="entry-content">
    <p>This content is restricted.</p>
    <a href="/login/">Login to access</a>
  </div>
</article>
</body></html>"""

OCEANOFPDF_DETAIL_HTML_DOWNLOAD_TEXT = """<html><body>
<article class="post">
  <div class="entry-content">
    <a href="/dl/5678/book-title/">Free Download</a>
    <a href="/wp-login/">Login</a>
  </div>
</article>
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
    """OceanOfPDF provider with API disabled for predictable scraping tests."""
    with patch("app.providers.books.oceanofpdf.WordPressApiClient") as mock_api_cls:
        mock_api_cls.return_value.search = AsyncMock(return_value=[])
        with patch("app.providers.books.oceanofpdf.settings") as mock_settings:
            mock_settings.OCEANOFPDF_DOMAIN = "https://oceanofpdf.com"
            mock_settings.EXTERNAL_URL = "http://localhost:9811"
            prov = OceanOfPDFProvider(http_client=mock_client)
            prov._USE_API = False  # Disable API for predictable scraping tests
            prov._api = None
            return prov


@pytest.fixture
def provider_api(mock_client):
    """OceanOfPDF provider with API enabled for API-path tests."""
    with patch("app.providers.books.oceanofpdf.WordPressApiClient") as mock_api_cls:
        mock_api_cls.return_value.search = AsyncMock(return_value=[])
        with patch("app.providers.books.oceanofpdf.settings") as mock_settings:
            mock_settings.OCEANOFPDF_DOMAIN = "https://oceanofpdf.com"
            mock_settings.EXTERNAL_URL = "http://localhost:9811"
            return OceanOfPDFProvider(http_client=mock_client)


# ── search() Tests: Scraping Path ─────────────────────────────────────


class TestOceanOfPDFSearchScrape:

    @pytest.mark.asyncio
    async def test_search_parses_wp_results(self, provider, mock_client):
        """Should parse WordPress HTML search results into SearchResults."""
        mock_client.get.return_value = ScraperResponse(
            200, OCEANOFPDF_SEARCH_HTML, b"", {},
            "https://oceanofpdf.com/?s=python"
        )

        results = await provider.search("python", categories=[7020])

        assert len(results) >= 3
        assert all(isinstance(r, SearchResult) for r in results)
        assert all(r.guid.startswith("oceanofpdf-") for r in results)
        assert all("api/download" in r.download_url for r in results)
        assert all("provider=oceanofpdf" in r.download_url for r in results)
        assert all("fmt=epub" in r.download_url for r in results)

    @pytest.mark.asyncio
    async def test_search_handles_empty_results(self, provider, mock_client):
        """Should return empty list when HTML has no matching posts."""
        mock_client.get.return_value = ScraperResponse(
            200, OCEANOFPDF_SEARCH_HTML_NO_RESULTS, b"", {}, "url"
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
    async def test_search_deduplicates(self, provider, mock_client):
        """Should not return duplicate results for same URL."""
        mock_client.get.return_value = ScraperResponse(
            200, OCEANOFPDF_SEARCH_HTML, b"", {}, "url"
        )

        results = await provider.search("python", categories=[7020])

        links = [r.link for r in results]
        assert len(links) == len(set(links))

    @pytest.mark.asyncio
    async def test_search_skips_utility_links(self, provider, mock_client):
        """Should skip category, tag, and javascript links."""
        mock_client.get.return_value = ScraperResponse(
            200, OCEANOFPDF_SEARCH_HTML_SKIP_LINKS, b"", {}, "url"
        )

        results = await provider.search("fiction", categories=[7020])

        # All links should be skipped: category, tag, javascript
        assert results == []

    @pytest.mark.asyncio
    async def test_search_extracts_author_from_meta(self, provider, mock_client):
        """Should extract author from entry-meta 'by X' pattern."""
        mock_client.get.return_value = ScraperResponse(
            200, OCEANOFPDF_SEARCH_HTML, b"", {}, "url"
        )

        results = await provider.search("python", categories=[7020])

        assert results[0].author == "Jake VanderPlas"
        assert results[1].author == "François Chollet"

    @pytest.mark.asyncio
    async def test_search_extracts_author_from_title_split(self, provider, mock_client):
        """When title contains '| Author', should extract and clean title."""
        mock_client.get.return_value = ScraperResponse(
            200, OCEANOFPDF_SEARCH_HTML, b"", {}, "url"
        )

        results = await provider.search("python", categories=[7020])

        # First result title: "Python for Data Science | Jake VanderPlas"
        # Author should be extracted from the "|" split
        assert results[0].author == "Jake VanderPlas"
        # Title should be cleaned (author part stripped)
        assert "|" not in results[0].title


# ── search() Tests: API Path ──────────────────────────────────────────


class TestOceanOfPDFSearchAPI:

    @pytest.mark.asyncio
    async def test_search_api_returns_results(self, provider_api, mock_client):
        """When API returns data, scraping should be skipped."""
        provider_api._api.search = AsyncMock(return_value=[
            SearchResult(
                title="API Book", guid="oceanofpdf-999",
                link="https://oceanofpdf.com/api-book/",
                download_url="http://localhost:9811/api/download?provider=oceanofpdf&id=999&fmt=epub",
                size_bytes=1000000, categories=[7020],
                description="From WordPress API"
            )
        ])

        results = await provider_api.search("api-book", categories=[7020])

        assert len(results) == 1
        assert results[0].title == "API Book"
        assert results[0].guid == "oceanofpdf-999"
        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_api_fallback_to_scrape(self, provider_api, mock_client):
        """When API returns empty, fall back to HTML scraping."""
        provider_api._api.search = AsyncMock(return_value=[])
        mock_client.get.return_value = ScraperResponse(
            200, OCEANOFPDF_SEARCH_HTML, b"", {}, "url"
        )

        results = await provider_api.search("python", categories=[7020])

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_api_error_fallback_to_scrape(self, provider_api, mock_client):
        """When API raises exception, fall back to HTML scraping."""
        provider_api._api.search = AsyncMock(side_effect=Exception("API down"))
        mock_client.get.return_value = ScraperResponse(
            200, OCEANOFPDF_SEARCH_HTML, b"", {}, "url"
        )

        results = await provider_api.search("python", categories=[7020])

        assert len(results) >= 1


# ── get_download_url() Tests ──────────────────────────────────────────


class TestOceanOfPDFDownload:

    @pytest.mark.asyncio
    async def test_get_download_url_finds_epub_link(self, provider, mock_client):
        """Should find direct .epub link on detail page and return absolute URL."""
        mock_client.get.return_value = ScraperResponse(
            200, OCEANOFPDF_DETAIL_HTML_EPUB, b"", {},
            "https://oceanofpdf.com/python-for-data-science/"
        )

        url = await provider.get_download_url("python-for-data-science")

        assert url is not None
        assert "download/1234/python-data-science.epub" in url
        assert url.startswith("https://oceanofpdf.com")

    @pytest.mark.asyncio
    async def test_get_download_url_handles_no_link(self, provider, mock_client):
        """Should return None when detail page has no downloadable links."""
        mock_client.get.return_value = ScraperResponse(
            200, OCEANOFPDF_DETAIL_HTML_NO_LINK, b"", {}, "url"
        )

        url = await provider.get_download_url("no-download-book")

        assert url is None

    @pytest.mark.asyncio
    async def test_get_download_url_handles_http_error(self, provider, mock_client):
        """Should return None when HttpClient raises an exception."""
        mock_client.get.side_effect = Exception("Timeout")

        url = await provider.get_download_url("python-for-data-science")

        assert url is None

    @pytest.mark.asyncio
    async def test_get_download_url_finds_by_text(self, provider, mock_client):
        """Should find links via 'Download' text detection (Strategy 2)."""
        mock_client.get.return_value = ScraperResponse(
            200, OCEANOFPDF_DETAIL_HTML_DOWNLOAD_TEXT, b"", {},
            "https://oceanofpdf.com/some-book/"
        )

        url = await provider.get_download_url("some-book")

        assert url is not None
        assert "/dl/5678/book-title/" in url

    @pytest.mark.asyncio
    async def test_get_download_url_skips_login_links(self, provider, mock_client):
        """Should not return wp-login links from download text detection."""
        mock_client.get.return_value = ScraperResponse(
            200, OCEANOFPDF_DETAIL_HTML_NO_LINK, b"", {},
            "https://oceanofpdf.com/restricted-book/"
        )

        url = await provider.get_download_url("restricted-book")

        assert url is None


# ── Capabilities Test ─────────────────────────────────────────────────


def test_get_capabilities(provider):
    """Should declare book search support and English query language."""
    caps = provider.get_capabilities()
    assert caps.provider_id == "oceanofpdf"
    assert caps.display_name == "OceanOfPDF"
    assert caps.supports_book_search is True
    assert caps.query_language == "en"
    assert 7020 in caps.supported_categories
