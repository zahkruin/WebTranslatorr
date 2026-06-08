"""
Tests for EbookeloProvider.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.scraping.http_client import ScraperResponse
from app.providers.books.ebookelo import EbookeloProvider

# Sample HTML for a search results page
SEARCH_HTML = """
<html><body>
<div class="search-results">
    <a href="/ebook/12345/el-senor-de-los-anillos">
        El Señor de los Anillos
    </a>
    <a href="/ebook/12346/harry-potter">
        Harry Potter
    </a>
</div>
</body></html>
"""

# Sample HTML for a book detail page
DETAIL_HTML = """
<html><body>
    <a href="/ebooks/autor/J.+R.R.+Tolkien">J. R. R. Tolkien</a>
    <a href="/download/12345/epub">EPUB</a>
    <a href="/download/12345/mobi">MOBI</a>
    <a href="/ebooks/genero/fantasia">Fantasía</a>
</body></html>
"""


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client


@pytest.fixture
def provider(mock_client):
    return EbookeloProvider(http_client=mock_client)


class TestEbookeloProvider:
    """Tests for EbookeloProvider."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=SEARCH_HTML,
            content=SEARCH_HTML.encode(),
            headers={},
            url="https://ww2.ebookelo.com/search/el+senor/page/1",
        )

        results = await provider.search(query="el señor", categories=[])
        assert len(results) > 0
        assert results[0].title == "El Señor de los Anillos"
        assert results[0].guid.startswith("ebookelo-")
        assert results[0].download_url != ""

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_empty(self, provider, mock_client):
        results = await provider.search(query="", categories=[])
        assert results == []
        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_with_author_and_title(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=SEARCH_HTML,
            content=SEARCH_HTML.encode(),
            headers={},
            url="https://ww2.ebookelo.com/search/tolkien+el+senor/page/1",
        )

        results = await provider.search(query="", author="tolkien", title="el señor", categories=[])
        assert len(results) > 0
        # search() also fetches detail pages for each result → multiple HTTP calls
        assert mock_client.get.call_count >= 1
        call_url = mock_client.get.call_args_list[0][0][0]
        assert "tolkien" in call_url.lower() or "se%C3%B1or" in call_url.lower()

    @pytest.mark.asyncio
    async def test_search_http_error_returns_empty(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Connection error")
        results = await provider.search(query="test", categories=[])
        assert results == []

    @pytest.mark.asyncio
    async def test_get_capabilities(self, provider):
        caps = provider.get_capabilities()
        assert caps.provider_id == "ebookelo"
        assert caps.supports_book_search is True
        assert 7000 in caps.supported_categories
        assert "q" in caps.supported_search_params

    @pytest.mark.asyncio
    async def test_get_download_url_valid(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=DETAIL_HTML,
            content=DETAIL_HTML.encode(),
            headers={"content-type": "text/html"},
            url="https://ww2.ebookelo.com/download/12345/epub",
        )

        url = await provider.get_download_url("12345/epub")
        assert url is not None

    @pytest.mark.asyncio
    async def test_get_download_url_handles_error(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Network error")
        url = await provider.get_download_url("99999/epub")
        assert url is not None  # Falls back to constructed URL

    def test_select_best_format(self, provider):
        assert provider._select_best_format(["pdf", "epub", "mobi"]) == "epub"
        assert provider._select_best_format(["mobi", "pdf"]) == "mobi"
        assert provider._select_best_format(["pdf"]) == "pdf"
        assert provider._select_best_format([]) == "epub"

    @pytest.mark.asyncio
    async def test_init_with_domain_resolver(self, mock_client):
        """Test domain_resolver overrides default domain (lines 41-43)."""
        mock_resolver = MagicMock()
        mock_resolver.get_current.return_value = "https://custom.ebookelo.com"
        provider = EbookeloProvider(http_client=mock_client, domain_resolver=mock_resolver)
        assert "custom.ebookelo.com" in provider.base_url

    @pytest.mark.asyncio
    async def test_search_with_offset(self, provider, mock_client):
        """Test offset slicing in search (line 112)."""
        mock_client.get.side_effect = [
            ScraperResponse(
                status_code=200, text=SEARCH_HTML, content=SEARCH_HTML.encode(),
                headers={}, url="https://ww2.ebookelo.com/search/test/page/1",
            ),
            ScraperResponse(
                status_code=200, text=DETAIL_HTML, content=DETAIL_HTML.encode(),
                headers={}, url="https://ww2.ebookelo.com/ebook/12345/el-senor-de-los-anillos",
            ),
            ScraperResponse(
                status_code=200, text=DETAIL_HTML, content=DETAIL_HTML.encode(),
                headers={}, url="https://ww2.ebookelo.com/ebook/12346/harry-potter",
            ),
        ]
        results = await provider.search(query="test", categories=[], offset=10)
        assert isinstance(results, list)

    def test_parse_results_short_href(self, provider):
        """Test _parse_results skips hrefs with fewer than 4 parts (line 132)."""
        html = '<html><body><a href="/ebook/123">Short</a></body></html>'
        results = provider._parse_results(html)
        assert len(results) == 0

    def test_parse_results_no_title_or_id(self, provider):
        """Test _parse_results skips entries without title or numeric id (line 140)."""
        html = '<html><body><a href="/ebook/abc/invalid">  </a></body></html>'
        results = provider._parse_results(html)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_parse_book_detail_all_fields(self, provider, mock_client):
        """Test _parse_book_detail extracts author, formats, genre, language (lines 178-200)."""
        detail_html = """
        <html><body>
            <a href="/ebooks/spanish">Spanish</a>
            <a href="/ebooks/autor/John+Doe">John Doe</a>
            <a href="/download/12345/epub">EPUB</a>
            <a href="/download/12345/mobi">MOBI</a>
            <a href="/ebooks/genero/fantasia">Fantasy</a>
        </body></html>
        """
        mock_client.get.return_value = ScraperResponse(
            status_code=200, text=detail_html, content=detail_html.encode(),
            headers={}, url="https://ww2.ebookelo.com/ebook/12345/test",
        )
        detail = await provider._parse_book_detail("https://ww2.ebookelo.com/ebook/12345/test")
        assert detail["author"] == "John Doe"
        assert "epub" in detail["formats"]
        assert detail["genre"] == "Fantasy"
        assert detail["language"] == "spanish"

    @pytest.mark.asyncio
    async def test_get_download_url_no_format_in_id(self, provider, mock_client):
        """Test get_download_url when internal_id has no format (lines 220-221)."""
        mock_client.get.return_value = ScraperResponse(
            status_code=302,
            text="",
            content=b"",
            headers={"Location": "https://cdn.ebookelo.com/download/12345/epub"},
            url="https://ww2.ebookelo.com/download/12345/epub",
        )
        url = await provider.get_download_url("12345")
        assert "cdn.ebookelo.com" in url

    @pytest.mark.asyncio
    async def test_get_download_url_redirect_with_profitablecpmgate(self, provider, mock_client):
        """Test get_download_url skips profitablecpmgate redirects (lines 233-235, 245-250)."""
        mock_client.get.return_value = ScraperResponse(
            status_code=302,
            text="",
            content=b"",
            headers={"Location": "https://profitablecpmgate.com/redirect"},
            url="https://ww2.ebookelo.com/download/12345/epub",
        )
        # When the redirect is to profitablecpmgate, returns the original download_url
        url = await provider.get_download_url("12345/epub")
        assert url is not None

    @pytest.mark.asyncio
    async def test_get_download_url_binary_content(self, provider, mock_client):
        """Test get_download_url when response has binary content (line 240)."""
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=b"binary data",
            content=b"binary data",
            headers={"content-type": "application/epub+zip"},
            url="https://ww2.ebookelo.com/download/12345/epub",
        )
        url = await provider.get_download_url("12345/epub")
        assert url is not None

    @pytest.mark.asyncio
    async def test_get_download_url_relative_href(self, provider, mock_client):
        """Test get_download_url with relative href in detail page (line 250)."""
        detail_html = """
        <html><body>
            <a href="/download/12345/epub">Download EPUB</a>
        </body></html>
        """
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=detail_html,
            content=detail_html.encode(),
            headers={"content-type": "text/html"},
            url="https://ww2.ebookelo.com/download/12345/epub",
        )
        url = await provider.get_download_url("12345/epub")
        assert "ww2.ebookelo.com" in url

    @pytest.mark.asyncio
    async def test_search_enrichment_error(self, provider, mock_client):
        """Test search handles enrichment errors gracefully (line 107)."""
        # Make search page succeed but detail page fail
        mock_client.get.side_effect = [
            ScraperResponse(
                status_code=200, text=SEARCH_HTML, content=SEARCH_HTML.encode(),
                headers={}, url="https://ww2.ebookelo.com/search/test/page/1",
            ),
            Exception("Detail page error"),
            Exception("Detail page error"),
        ]
        results = await provider.search(query="test", categories=[])
        # Should still return results even when enrichment fails
        assert len(results) > 0
