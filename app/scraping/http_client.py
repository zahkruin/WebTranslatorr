"""
Cliente HTTP con:
- Rotación de User-Agents
- Rate limiting por dominio
- Reintentos automáticos con backoff exponencial
- Gestión de cookies/sesión
- Soporte de proxy HTTP
- Cloudscraper wrapper estandarizado a interfaz httpx
"""
import asyncio
import httpx
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Optional

import cloudscraper
import requests.exceptions

from config import settings
from app.core.exceptions import DownloadTooLargeError
from app.utils.url_safety import is_safe_redirect, is_safe_url


@dataclass
class ScraperResponse:
    status_code: int
    text: str
    content: bytes
    headers: dict
    url: str

    @classmethod
    def from_requests_response(cls, resp):
        return cls(
            status_code=resp.status_code,
            text=resp.text,
            content=resp.content,
            headers=dict(resp.headers),
            url=str(resp.url),
        )


class HttpClient:
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]

    CHUNK_SIZE = 262144

    def __init__(
        self,
        rate_limit_per_second: float = 2.0,
        max_retries: int = 3,
        timeout: int = 30,
        proxy: Optional[str] = None,
    ):
        client_kwargs = dict(
            timeout=timeout,
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=20),
        )
        if proxy:
            client_kwargs["proxies"] = proxy

        self._client = httpx.AsyncClient(**client_kwargs)
        self._rate_limit = rate_limit_per_second
        self._max_retries = max_retries
        self._last_request: dict[str, float] = {}
        self._rate_lock = asyncio.Lock()
        self._ua_index = 0

        scraper_kwargs = {
            'browser': {'browser': 'chrome', 'platform': 'windows', 'mobile': False},
        }
        if proxy:
            scraper_kwargs['proxies'] = {"http": proxy, "https": proxy}
        self._scraper = cloudscraper.create_scraper(**scraper_kwargs)

    def _validate_response_urls(self, url: str, final_url: str) -> None:
        if not is_safe_url(final_url):
            raise ValueError(f"Unsafe destination URL: {final_url}")

    async def get(self, url: str, **kwargs) -> ScraperResponse:
        if not is_safe_url(url):
            raise ValueError(f"Unsafe URL: {url}")

        await self._apply_rate_limit(url)
        headers = kwargs.pop("headers", {})
        headers.setdefault("User-Agent", self._rotate_ua())
        headers.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8")
        headers.setdefault("Accept-Language", "es-ES,es;q=0.9,en;q=0.8")
        headers.setdefault("Accept-Encoding", "gzip, deflate")
        headers.setdefault("DNT", "1")
        headers.setdefault("Connection", "keep-alive")

        follow_redirects = kwargs.pop("follow_redirects", True)
        use_scraper = kwargs.pop("use_scraper", False)
        params = kwargs.pop("params", None)

        for attempt in range(self._max_retries):
            try:
                if use_scraper:
                    loop = asyncio.get_event_loop()
                    resp = await loop.run_in_executor(
                        None,
                        lambda: self._scraper.get(
                            url,
                            params=params,
                            headers=headers,
                            allow_redirects=follow_redirects,
                            timeout=self._client.timeout if hasattr(self._client.timeout, 'read') else self._client.timeout,
                        ),
                    )
                    resp.raise_for_status()
                    final_url = str(resp.url)
                    self._validate_response_urls(url, final_url)
                    return ScraperResponse.from_requests_response(resp)

                resp = await self._client.get(
                    url,
                    params=params,
                    headers=headers,
                    follow_redirects=follow_redirects,
                )
                resp.raise_for_status()
                final_url = str(resp.url)
                self._validate_response_urls(url, final_url)
                if getattr(resp, "history", None):
                    previous = url
                    for hop in resp.history:
                        location = str(hop.headers.get("location", hop.url))
                        if not is_safe_redirect(previous, location):
                            raise ValueError(f"Unsafe redirect to: {location}")
                        previous = location
                return ScraperResponse(
                    status_code=resp.status_code,
                    text=resp.text,
                    content=resp.content,
                    headers=dict(resp.headers),
                    url=final_url,
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (429, 500, 502, 503, 504):
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
            except httpx.ConnectError:
                await asyncio.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                status = getattr(e.response, "status_code", None)
                if status in (429, 500, 502, 503, 504) or isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

        raise Exception(f"Failed after {self._max_retries} retries: {url}")

    async def post(self, url: str, **kwargs) -> ScraperResponse:
        if not is_safe_url(url):
            raise ValueError(f"Unsafe URL: {url}")

        await self._apply_rate_limit(url)
        headers = kwargs.pop("headers", {})
        headers.setdefault("User-Agent", self._rotate_ua())
        params = kwargs.pop("params", None)

        for attempt in range(self._max_retries):
            try:
                resp = await self._client.post(url, params=params, headers=headers, **kwargs)
                resp.raise_for_status()
                final_url = str(resp.url)
                self._validate_response_urls(url, final_url)
                return ScraperResponse(
                    status_code=resp.status_code,
                    text=resp.text,
                    content=resp.content,
                    headers=dict(resp.headers),
                    url=final_url,
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

        raise Exception(f"Failed after {self._max_retries} retries: {url}")

    async def download_file(self, url: str, *, max_bytes: int | None = None, **kwargs) -> bytes:
        if not is_safe_url(url):
            raise ValueError(f"Unsafe URL: {url}")

        max_bytes = max_bytes or settings.MAX_DOWNLOAD_BYTES
        use_scraper = kwargs.pop("use_scraper", False)
        await self._apply_rate_limit(url)

        if use_scraper:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: self._scraper.get(url, allow_redirects=True, **kwargs),
            )
            resp.raise_for_status()
            final_url = str(resp.url)
            self._validate_response_urls(url, final_url)
            content = resp.content
            if len(content) > max_bytes:
                raise DownloadTooLargeError(
                    f"Download exceeds limit of {max_bytes} bytes"
                )
            return content

        headers = kwargs.pop("headers", {})
        headers.setdefault("User-Agent", self._rotate_ua())
        follow_redirects = kwargs.pop("follow_redirects", True)

        async with self._client.stream(
            "GET",
            url,
            headers=headers,
            follow_redirects=follow_redirects,
            **kwargs,
        ) as response:
            response.raise_for_status()
            final_url = str(response.url)
            self._validate_response_urls(url, final_url)
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes(self.CHUNK_SIZE):
                total += len(chunk)
                if total > max_bytes:
                    raise DownloadTooLargeError(
                        f"Download exceeds limit of {max_bytes} bytes"
                    )
                chunks.append(chunk)
            return b"".join(chunks)

    async def head(self, url: str, **kwargs) -> ScraperResponse:
        if not is_safe_url(url):
            raise ValueError(f"Unsafe URL: {url}")

        await self._apply_rate_limit(url)
        headers = kwargs.pop("headers", {})
        headers.setdefault("User-Agent", self._rotate_ua())
        follow_redirects = kwargs.pop("follow_redirects", True)
        timeout = kwargs.pop("timeout", None)

        resp = await self._client.head(url, headers=headers, follow_redirects=follow_redirects, timeout=timeout)
        final_url = str(resp.url)
        self._validate_response_urls(url, final_url)
        return ScraperResponse(
            status_code=resp.status_code,
            text=resp.text,
            content=resp.content,
            headers=dict(resp.headers),
            url=final_url,
        )

    def _rotate_ua(self) -> str:
        ua = self.USER_AGENTS[self._ua_index % len(self.USER_AGENTS)]
        self._ua_index += 1
        return ua

    async def _apply_rate_limit(self, url: str) -> None:
        domain = urlparse(url).netloc
        async with self._rate_lock:
            now = asyncio.get_event_loop().time()
            last = self._last_request.get(domain)
            if last is not None:
                elapsed = now - last
                if elapsed < (1.0 / self._rate_limit):
                    await asyncio.sleep((1.0 / self._rate_limit) - elapsed)
            self._last_request[domain] = asyncio.get_event_loop().time()

    async def close(self):
        await self._client.aclose()
        if hasattr(self._scraper, "close"):
            self._scraper.close()
