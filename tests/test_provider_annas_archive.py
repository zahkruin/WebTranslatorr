"""
Tests for AnnasArchiveProvider.
"""

import pytest
from unittest.mock import AsyncMock, call

from app.scraping.http_client import ScraperResponse
from app.providers.books.annas_archive import AnnasArchiveProvider

SEARCH_HTML = """
<html><body>
    <a href="/md5/abc123def456">
        <h3>Harry Potter</h3>
    </a>
    <a href="/md5/def789ghi012">
        <div class="font-bold">El Señor de los Anillos</div>
    </a>
</body></html>
"""

SEARCH_HTML_SPAN_TITLE = """
<html><body>
    <a href="/md5/xyz999">
        <span class="text-lg">Cien Años de Soledad</span>
    </a>
</body></html>
"""

SEARCH_HTML_DATA_DOWNLOAD = """
<html><body>
    <a data-download="true" href="/download/data/abc123">Download with data attr</a>
</body></html>
"""

SEARCH_HTML_DATA_PARTNER = """
<html><body>
    <a data-partner="true" href="/download/partner/xyz">Partner link</a>
</body></html>
"""

DETAIL_HTML_SLOW_SERVER = """
<html><body>
    <a class="js-download-link" href="/download/slow/abc123">Slow Partner Server</a>
    <a class="js-download-link" href="/download/libgen/abc123">libgen</a>
</body></html>
"""

DETAIL_HTML_FALLBACK = """
<html><body>
    <a href="/download/abc123">Download Link</a>
    <a href="https://libgen.li/abc123">Libgen Link</a>
</body></html>
"""

CF_CHALLENGE_HTML = """
<html><head><title>Just a moment...</title></head>
<body><div id="cf-challenge-running">Verifying...</div></body></html>
"""

CF_CHALLENGE_HTML_VARIANT = """
<html><head><title>Just a moment...</title></head>
<body><div id="challenge-error-text">Please enable JavaScript</div></body></html>
"""

BROWSE_HTML = """
<html><body>
    <a href="/md5/browse1">
        <h3>Recent Book</h3>
    </a>
    <a href="/md5/browse2">
        <div class="truncate">Another Recent Book</div>
    </a>
</body></html>
"""


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get = AsyncMock()
    return client


@pytest.fixture
def provider(mock_client):
    return AnnasArchiveProvider(http_client=mock_client)


class TestAnnasArchiveProvider:
    """Tests for AnnasArchiveProvider."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=SEARCH_HTML,
            content=SEARCH_HTML.encode(),
            headers={},
            url="https://annas-archive.gl/search?q=harry+potter&lang=es&ext=epub",
        )

        results = await provider.search(query="harry potter")
        assert len(results) > 0
        assert results[0].guid.startswith("annasarchive-")
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
        assert caps.provider_id == "annasarchive"
        assert caps.supports_book_search is True

    @pytest.mark.asyncio
    async def test_get_download_url_slow_partner(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=DETAIL_HTML_SLOW_SERVER,
            content=DETAIL_HTML_SLOW_SERVER.encode(),
            headers={},
            url="https://annas-archive.gl/md5/abc123def456",
        )

        url = await provider.get_download_url("abc123def456")
        assert url is not None
        assert "slow" in url

    @pytest.mark.asyncio
    async def test_get_download_url_fallback(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=DETAIL_HTML_FALLBACK,
            content=DETAIL_HTML_FALLBACK.encode(),
            headers={},
            url="https://annas-archive.gl/md5/abc123def456",
        )

        url = await provider.get_download_url("abc123def456")
        assert url is not None

    @pytest.mark.asyncio
    async def test_get_download_url_no_match(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text="<html><body>No links</body></html>",
            content=b"",
            headers={},
            url="https://annas-archive.gl/md5/unknown",
        )

        url = await provider.get_download_url("unknown")
        assert url is None

    @pytest.mark.asyncio
    async def test_get_download_url_error(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Network error")
        url = await provider.get_download_url("abc123")
        assert url is None

    @pytest.mark.asyncio
    async def test_search_deduplicates_urls(self, provider, mock_client):
        html = """
        <html><body>
            <a href="/md5/abc"><h3>Book</h3></a>
            <a href="/md5/abc"><h3>Book</h3></a>
        </body></html>
        """
        mock_client.get.return_value = ScraperResponse(
            status_code=200, text=html, content=html.encode(), headers={}, url="https://annas-archive.gl/search?q=test"
        )
        results = await provider.search(query="test")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_cloudflare_challenge_detected_returns_empty(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=CF_CHALLENGE_HTML,
            content=CF_CHALLENGE_HTML.encode(),
            headers={},
            url="https://annas-archive.gl/search?q=test",
        )
        results = await provider.search(query="test")
        assert results == []

    @pytest.mark.asyncio
    async def test_cloudflare_challenge_variant_returns_empty(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=CF_CHALLENGE_HTML_VARIANT,
            content=CF_CHALLENGE_HTML_VARIANT.encode(),
            headers={},
            url="https://annas-archive.gl/search?q=test",
        )
        results = await provider.search(query="test")
        assert results == []

    @pytest.mark.asyncio
    async def test_url_encoding_spaces(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=SEARCH_HTML,
            content=SEARCH_HTML.encode(),
            headers={},
            url="https://annas-archive.gl/search?q=harry+potter&lang=es&ext=epub",
        )

        await provider.search(query="harry potter")
        call_url = mock_client.get.call_args[0][0]
        assert "harry+potter" in call_url
        assert " " not in call_url

    @pytest.mark.asyncio
    async def test_url_encoding_special_chars(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=SEARCH_HTML,
            content=SEARCH_HTML.encode(),
            headers={},
            url="https://annas-archive.gl/search?q=ca%C3%B1a&lang=es&ext=epub",
        )

        await provider.search(query="caña")
        call_url = mock_client.get.call_args[0][0]
        assert "ca%C3%B1a" in call_url

    @pytest.mark.asyncio
    async def test_is_healthy_uses_scraper(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text="<html><head><title>Anna's Archive</title></head><body>OK</body></html>",
            content=b"",
            headers={},
            url="https://annas-archive.gl/",
        )

        result = await provider.is_healthy()
        assert result is True
        mock_client.get.assert_called_once()
        call_kwargs = mock_client.get.call_args
        assert call_kwargs[1].get("use_scraper") is True

    @pytest.mark.asyncio
    async def test_is_healthy_detects_cf_challenge(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=CF_CHALLENGE_HTML,
            content=CF_CHALLENGE_HTML.encode(),
            headers={},
            url="https://annas-archive.gl/",
        )

        result = await provider.is_healthy()
        assert result is False

    @pytest.mark.asyncio
    async def test_is_healthy_http_error(self, provider, mock_client):
        mock_client.get.side_effect = Exception("Connection refused")
        result = await provider.is_healthy()
        assert result is False

    @pytest.mark.asyncio
    async def test_download_selectors_data_download(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=SEARCH_HTML_DATA_DOWNLOAD,
            content=SEARCH_HTML_DATA_DOWNLOAD.encode(),
            headers={},
            url="https://annas-archive.gl/md5/abc123",
        )

        url = await provider.get_download_url("abc123")
        assert url is not None

    @pytest.mark.asyncio
    async def test_download_selectors_data_partner(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=SEARCH_HTML_DATA_PARTNER,
            content=SEARCH_HTML_DATA_PARTNER.encode(),
            headers={},
            url="https://annas-archive.gl/md5/xyz",
        )

        url = await provider.get_download_url("xyz")
        assert url is not None

    @pytest.mark.asyncio
    async def test_title_extraction_span(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=SEARCH_HTML_SPAN_TITLE,
            content=SEARCH_HTML_SPAN_TITLE.encode(),
            headers={},
            url="https://annas-archive.gl/search?q=cien+a%C3%B1os",
        )

        results = await provider.search(query="cien años")
        assert len(results) == 1
        assert results[0].title == "Cien Años de Soledad"

    @pytest.mark.asyncio
    async def test_browse_returns_results(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=BROWSE_HTML,
            content=BROWSE_HTML.encode(),
            headers={},
            url="https://annas-archive.gl/",
        )

        results = await provider.browse()
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_browse_cf_challenge_returns_empty(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=CF_CHALLENGE_HTML,
            content=CF_CHALLENGE_HTML.encode(),
            headers={},
            url="https://annas-archive.gl/",
        )

        results = await provider.browse()
        assert results == []

    @pytest.mark.asyncio
    async def test_get_download_url_cf_challenge(self, provider, mock_client):
        mock_client.get.return_value = ScraperResponse(
            status_code=200,
            text=CF_CHALLENGE_HTML,
            content=CF_CHALLENGE_HTML.encode(),
            headers={},
            url="https://annas-archive.gl/md5/abc123",
        )

        url = await provider.get_download_url("abc123")
        assert url is None
