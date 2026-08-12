"""
Tests for HttpClient — the async HTTP client with retry, rate-limiting and cloudscraper fallback.
"""

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from app.scraping.http_client import HttpClient, ScraperResponse


@pytest.fixture
def mock_httpx_class():
    """Fixture that patches httpx.AsyncClient and returns the class mock."""
    with patch("app.scraping.http_client.httpx.AsyncClient") as mock:
        instance = AsyncMock()
        mock.return_value = instance
        yield mock, instance


@pytest.fixture
def mock_cloudscraper():
    """Fixture that patches cloudscraper.create_scraper."""
    with patch("app.scraping.http_client.cloudscraper.create_scraper") as mock:
        instance = MagicMock()
        mock.return_value = instance
        yield mock, instance


class TestHttpClientInit:
    """Tests for HttpClient.__init__."""

    def test_default_init(self, mock_httpx_class):
        """Should create httpx client without proxy."""
        mock_cls, _ = mock_httpx_class
        client = HttpClient()
        mock_cls.assert_called_once()

    def test_init_with_proxy(self, mock_httpx_class, mock_cloudscraper):
        """Should pass proxy to both httpx and cloudscraper."""
        mock_cls, _ = mock_httpx_class
        scraper_cls, _ = mock_cloudscraper
        client = HttpClient(proxy="http://proxy:8080")
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["proxies"] == "http://proxy:8080"
        # Cloudscraper should also receive proxies
        scraper_kwargs = scraper_cls.call_args[1]
        assert "proxies" in scraper_kwargs


class TestHttpClientRateLimiting:
    """Tests for _apply_rate_limit."""

    @pytest.mark.asyncio
    async def test_first_request_no_wait(self, mock_httpx_class, mock_cloudscraper):
        """First request to a domain should not sleep."""
        client = HttpClient(rate_limit_per_second=100.0)
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await client._apply_rate_limit("https://example.com/page")
            mock_sleep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_second_request_waits(self, mock_httpx_class, mock_cloudscraper):
        """Second request before rate limit window should sleep."""
        client = HttpClient(rate_limit_per_second=1.0)
        await client._apply_rate_limit("https://example.com/page")
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await client._apply_rate_limit("https://example.com/page")
            mock_sleep.assert_awaited()


class TestHttpClientGet:
    """Tests for HttpClient.get."""

    @pytest.mark.asyncio
    async def test_get_success_httpx(self, mock_httpx_class, mock_cloudscraper):
        """GET with httpx should return ScraperResponse."""
        _, mock_instance = mock_httpx_class
        client = HttpClient(rate_limit_per_second=100.0, max_retries=1, timeout=10)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.text = "<html>ok</html>"
        mock_response.content = b"<html>ok</html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.url = "https://example.com/page"
        mock_response.history = []
        mock_instance.get = AsyncMock(return_value=mock_response)

        result = await client.get("https://example.com/page")

        assert isinstance(result, ScraperResponse)
        assert result.status_code == 200
        assert result.text == "<html>ok</html>"
        assert result.content == b"<html>ok</html>"

    @pytest.mark.asyncio
    async def test_get_with_params(self, mock_httpx_class, mock_cloudscraper):
        """GET should pass params to httpx."""
        _, mock_instance = mock_httpx_class
        client = HttpClient(rate_limit_per_second=100.0, max_retries=1, timeout=10)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.text = ""
        mock_response.content = b""
        mock_response.headers = {}
        mock_response.url = "https://example.com/search"
        mock_response.history = []
        mock_instance.get = AsyncMock(return_value=mock_response)

        await client.get("https://example.com/search", params={"q": "test"})

        mock_instance.get.assert_called_once()
        _, kwargs = mock_instance.get.call_args
        assert kwargs["params"] == {"q": "test"}

    @pytest.mark.asyncio
    async def test_get_retry_on_429(self, mock_httpx_class, mock_cloudscraper):
        """GET should retry on HTTP 429."""
        _, mock_instance = mock_httpx_class
        client = HttpClient(max_retries=3, rate_limit_per_second=100.0)

        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 429
        error_response.text = ""
        error_response.content = b""
        error_response.headers = {}
        error_response.url = "https://example.com/page"
        error_response.history = []

        # Raise HTTPStatusError on first two attempts, succeed on third
        exc = httpx.HTTPStatusError("Too Many", request=MagicMock(), response=error_response)
        error_response.raise_for_status.side_effect = [exc, exc, None]
        mock_instance.get = AsyncMock(return_value=error_response)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.get("https://example.com/page")

        assert result is not None
        assert mock_instance.get.await_count == 3

    @pytest.mark.asyncio
    async def test_get_use_scraper_success(self, mock_httpx_class, mock_cloudscraper):
        """GET with use_scraper=True should use cloudscraper path."""
        _, mock_instance = mock_httpx_class
        mock_scraper_cls, mock_scraper_instance = mock_cloudscraper
        client = HttpClient(max_retries=1, rate_limit_per_second=100.0)

        scraper_resp = MagicMock()
        scraper_resp.status_code = 200
        scraper_resp.text = "<html>scraped</html>"
        scraper_resp.content = b"<html>scraped</html>"
        scraper_resp.headers = {"content-type": "text/html"}
        scraper_resp.url = "https://example.com/page"
        scraper_resp.raise_for_status = MagicMock()

        mock_scraper_instance.get = MagicMock(return_value=scraper_resp)

        with patch("asyncio.sleep", new_callable=AsyncMock), \
             patch("asyncio.get_event_loop") as mock_loop:
            mock_loop_instance = MagicMock()
            mock_loop.return_value = mock_loop_instance
            # Run the lambda synchronously in the mock so scraper.get is called
            mock_loop_instance.run_in_executor = AsyncMock(
                side_effect=lambda executor, func: func()
            )

            result = await client.get("https://example.com/page", use_scraper=True)

        assert result.status_code == 200
        assert result.text == "<html>scraped</html>"
        # Verify scraper was actually called
        mock_scraper_instance.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_retry_on_429(self, mock_httpx_class, mock_cloudscraper):
        """POST should retry on HTTP 429."""
        _, mock_instance = mock_httpx_class
        client = HttpClient(max_retries=3, rate_limit_per_second=100.0)

        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 429
        error_response.text = ""
        error_response.content = b""
        error_response.headers = {}
        error_response.url = "https://example.com/page"
        error_response.history = []

        exc = httpx.HTTPStatusError("Too Many", request=MagicMock(), response=error_response)
        error_response.raise_for_status.side_effect = [exc, exc, None]
        mock_instance.post = AsyncMock(return_value=error_response)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client.post("https://example.com/page")

        assert result is not None
        assert mock_instance.post.await_count == 3

    @pytest.mark.asyncio
    async def test_head_with_exception(self, mock_httpx_class, mock_cloudscraper):
        """HEAD should propagate exceptions."""
        _, mock_instance = mock_httpx_class
        client = HttpClient(max_retries=1, rate_limit_per_second=100.0)
        mock_instance.head = AsyncMock(side_effect=httpx.ConnectError("connection failed"))

        with pytest.raises(httpx.ConnectError):
            await client.head("https://example.com")

    @pytest.mark.asyncio
    async def test_get_retry_on_connect_error(self, mock_httpx_class, mock_cloudscraper):
        """GET should retry on ConnectError."""
        _, mock_instance = mock_httpx_class
        client = HttpClient(max_retries=2, rate_limit_per_second=100.0)
        mock_instance.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(Exception, match="Failed after 2 retries"):
                await client.get("https://example.com/page")

    @pytest.mark.asyncio
    async def test_get_non_retryable_status(self, mock_httpx_class, mock_cloudscraper):
        """GET should raise immediately on 4xx that aren't 429."""
        _, mock_instance = mock_httpx_class
        client = HttpClient(max_retries=2, rate_limit_per_second=100.0)
        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 404
        exc = httpx.HTTPStatusError("Not Found", request=MagicMock(), response=error_response)
        error_response.raise_for_status.side_effect = exc
        mock_instance.get = AsyncMock(return_value=error_response)

        with pytest.raises(httpx.HTTPStatusError):
            await client.get("https://example.com/notfound")


class TestHttpClientPost:
    """Tests for HttpClient.post."""

    @pytest.mark.asyncio
    async def test_post_success(self, mock_httpx_class, mock_cloudscraper):
        """POST should send data and return ScraperResponse."""
        _, mock_instance = mock_httpx_class
        client = HttpClient(rate_limit_per_second=100.0, max_retries=1, timeout=10)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 201
        mock_response.text = "created"
        mock_response.content = b"created"
        mock_response.headers = {"location": "/new"}
        mock_response.url = "https://example.com/resource"
        mock_instance.post = AsyncMock(return_value=mock_response)

        result = await client.post("https://example.com/resource", json={"key": "val"})

        assert isinstance(result, ScraperResponse)
        assert result.status_code == 201
        mock_instance.post.assert_called_once()
        _, kwargs = mock_instance.post.call_args
        assert kwargs["json"] == {"key": "val"}


class TestHttpClientHead:
    """Tests for HttpClient.head."""

    @pytest.mark.asyncio
    async def test_head_success(self, mock_httpx_class, mock_cloudscraper):
        """HEAD should return ScraperResponse."""
        _, mock_instance = mock_httpx_class
        client = HttpClient(rate_limit_per_second=100.0, max_retries=1, timeout=10)
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.text = ""
        mock_response.content = b""
        mock_response.headers = {"content-type": "text/html"}
        mock_response.url = "https://example.com"
        mock_instance.head = AsyncMock(return_value=mock_response)

        result = await client.head("https://example.com")

        assert result.status_code == 200
        assert result.headers["content-type"] == "text/html"


class TestHttpClientDownload:
    """Tests for HttpClient.download_file."""

    @pytest.mark.asyncio
    async def test_download_file(self, mock_httpx_class, mock_cloudscraper):
        """download_file should return content bytes."""
        _, mock_instance = mock_httpx_class
        client = HttpClient(rate_limit_per_second=100.0, max_retries=1, timeout=10)

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com/file.bin"
        mock_response.raise_for_status = MagicMock()

        async def aiter_bytes(chunk_size):
            yield b"binary data"

        mock_response.aiter_bytes = aiter_bytes
        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream.__aexit__ = AsyncMock(return_value=None)
        mock_instance.stream = MagicMock(return_value=mock_stream)

        result = await client.download_file("https://example.com/file.bin")

        assert result == b"binary data"

    @pytest.mark.asyncio
    async def test_download_file_too_large(self, mock_httpx_class, mock_cloudscraper):
        from app.core.exceptions import DownloadTooLargeError

        _, mock_instance = mock_httpx_class
        client = HttpClient(rate_limit_per_second=100.0, max_retries=1, timeout=10)

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.url = "https://example.com/file.bin"
        mock_response.raise_for_status = MagicMock()

        async def aiter_bytes(chunk_size):
            yield b"x" * 2048

        mock_response.aiter_bytes = aiter_bytes
        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream.__aexit__ = AsyncMock(return_value=None)
        mock_instance.stream = MagicMock(return_value=mock_stream)

        with pytest.raises(DownloadTooLargeError):
            await client.download_file("https://example.com/file.bin", max_bytes=1024)


class TestHttpClientRotateUA:
    """Tests for _rotate_ua."""

    def test_rotate_ua_cycles(self, mock_httpx_class, mock_cloudscraper):
        """_rotate_ua should cycle through user agents."""
        client = HttpClient()
        first = client._rotate_ua()
        second = client._rotate_ua()
        assert first != second

    def test_rotate_ua_wraps_around(self, mock_httpx_class, mock_cloudscraper):
        """_rotate_ua should wrap around when exceeding list length."""
        client = HttpClient()
        uas = []
        for _ in range(len(client.USER_AGENTS) + 1):
            uas.append(client._rotate_ua())
        assert uas[0] == uas[-1]


class TestHttpClientClose:
    """Tests for HttpClient.close."""

    @pytest.mark.asyncio
    async def test_close(self, mock_httpx_class, mock_cloudscraper):
        """close should call aclose on the httpx client."""
        _, mock_instance = mock_httpx_class
        client = HttpClient()
        await client.close()
        mock_instance.aclose.assert_awaited_once()
