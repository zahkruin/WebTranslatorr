"""
Tests for EspaebookProvider.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.scraping.http_client import ScraperResponse
from app.providers.books.espaebook import EspaebookProvider

SEARCH_HTML = """
<html><body>
    <a href="/libro/abc123/harry-potter/">Harry Potter</a>
    <a href="/book/def456/el-senor/">El Señor de los Anillos</a>
    <h2 class="entry-title"><a href="/libro/ghi789/otro-libro/">Otro Libro</a></h2>
</body></html>
"""

DETAIL_HTML = """
<html><body>
    <a href="/descargar/abc123">DESCARGAR EPUB</a>
    <a href="/genre/fantasy">Fantasía</a>
    <a href="/autor/tolkien">Tolkien</a>
</body></html>
"""


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client


@pytest.fixture
def provider(mock_client):
    return EspaebookProvider(http_client=mock_client)


class TestEspaebookProvider:
    """Tests for EspaebookProvider."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=SEARCH_HTML,
            content=SEARCH_HTML.encode(),
            headers={},
            url="https://espaebook.cc/?s=harry+potter",
        )

        results = await provider.search(query="harry potter")
        assert len(results) > 0
        assert results[0].title == "Harry Potter"
        assert results[0].guid.startswith("espaebook-")
        assert "download" in results[0].download_url

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_empty(self, provider, mock_client):
        results = await provider.search(query="")
        assert results == []
        mock_client.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_http_error_returns_empty(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Connection error")
        results = await provider.search(query="test")
        assert results == []

    @pytest.mark.asyncio
    async def test_get_capabilities(self, provider):
        caps = provider.get_capabilities()
        assert caps.provider_id == "espaebook"
        assert caps.supports_book_search is True

    @pytest.mark.asyncio
    async def test_get_download_url_valid(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=DETAIL_HTML,
            content=DETAIL_HTML.encode(),
            headers={},
            url="https://espaebook.cc/libro/abc123/",
        )

        url = await provider.get_download_url("abc123", fmt="epub")
        assert url is not None
        assert "descargar" in url.lower()

    @pytest.mark.asyncio
    async def test_get_download_url_fallback_route(self, provider, mock_client):
        """When /libro/ returns 404, should fallback to /book/."""
        mock_client.get.side_effect = [
            ScraperResponse(
                status_code=404, text="Not found", content=b"",
                headers={}, url="https://espaebook.cc/libro/abc123/",
            ),
            ScraperResponse(
                status_code=200, text=DETAIL_HTML, content=DETAIL_HTML.encode(),
                headers={}, url="https://espaebook.cc/book/abc123/",
            ),
        ]

        url = await provider.get_download_url("abc123")
        assert url is not None
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_get_download_url_no_match(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text="<html><body>No links here</body></html>",
            content=b"",
            headers={},
            url="https://espaebook.cc/libro/unknown/",
        )

        url = await provider.get_download_url("unknown")
        assert url is None

    @pytest.mark.asyncio
    async def test_get_download_url_error(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Network error")
        url = await provider.get_download_url("abc123")
        assert url is None

    @pytest.mark.asyncio
    async def test_init_with_domain_resolver(self, mock_client):
        """Test that domain_resolver overrides the default domain."""
        mock_resolver = MagicMock()
        mock_resolver.get_current.return_value = "https://custom-espaebook.com"

        provider = EspaebookProvider(http_client=mock_client, domain_resolver=mock_resolver)
        assert "custom-espaebook.com" in provider.base_url
        mock_resolver.get_current.assert_called_once_with("espaebook")

    @pytest.mark.asyncio
    async def test_init_with_domain_resolver_returns_none(self, mock_client):
        """Test that when domain_resolver returns None, default domain is used."""
        mock_resolver = MagicMock()
        mock_resolver.get_current.return_value = None

        provider = EspaebookProvider(http_client=mock_client, domain_resolver=mock_resolver)
        assert "espaebook" in provider.base_url

    @pytest.mark.asyncio
    async def test_search_skips_duplicate_urls(self, provider, mock_client):
        """Test that duplicate URLs are skipped (line 66)."""
        dup_html = """
        <html><body>
            <a href="/libro/abc123/harry-potter/">Harry Potter</a>
            <a href="/libro/abc123/harry-potter/">Harry Potter</a>
            <a href="">Empty href</a>
        </body></html>
        """
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=dup_html,
            content=dup_html.encode(),
            headers={},
            url="https://espaebook.cc/?s=test",
        )

        results = await provider.search(query="test")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_search_fallback_internal_id(self, provider, mock_client):
        """Test fallback internal_id extraction when regex doesn't match (line 73)."""
        fallback_html = """
        <html><body>
            <a href="/libro//">Custom Link</a>
        </body></html>
        """
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=fallback_html,
            content=fallback_html.encode(),
            headers={},
            url="https://espaebook.cc/?s=test",
        )

        results = await provider.search(query="test")
        assert len(results) == 1
        assert "espaebook-" in results[0].guid

    @pytest.mark.asyncio
    async def test_search_respects_limit(self, provider, mock_client):
        """Test that search respects the limit parameter (line 88)."""
        many_links = "<html><body>" + "".join(
            f'<a href="/libro/id{i:03d}/book-{i}/">Book {i}</a>'
            for i in range(10)
        ) + "</body></html>"

        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=many_links,
            content=many_links.encode(),
            headers={},
            url="https://espaebook.cc/?s=test",
        )

        results = await provider.search(query="test", limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_get_download_url_absolute_href(self, provider, mock_client):
        """Test get_download_url when href is absolute (line 114)."""
        detail_html = """
        <html><body>
            <a href="https://cdn.espaebook.cc/descargar/abc123.epub">DESCARGAR EPUB</a>
        </body></html>
        """
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=detail_html,
            content=detail_html.encode(),
            headers={},
            url="https://espaebook.cc/libro/abc123/",
        )

        url = await provider.get_download_url("abc123")
        assert url == "https://cdn.espaebook.cc/descargar/abc123.epub"
