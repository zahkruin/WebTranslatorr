"""
Cliente HTTP con:
- Rotación de User-Agents
- Rate limiting por dominio
- Reintentos automáticos con backoff exponencial
- Gestión de cookies/sesión
"""
import asyncio
import httpx
from collections import defaultdict
from urllib.parse import urlparse
import cloudscraper
import requests.exceptions


class HttpClient:
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]

    def __init__(self, rate_limit_per_second: float = 2.0, max_retries: int = 3, timeout: int = 30):
        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=20),
        )
        self._rate_limit = rate_limit_per_second
        self._max_retries = max_retries
        self._last_request: dict[str, float] = defaultdict(float)
        self._ua_index = 0
        self._scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )

    async def get(self, url: str, **kwargs) -> httpx.Response:
        await self._apply_rate_limit(url)
        headers = kwargs.pop("headers", {})
        headers.setdefault("User-Agent", self._rotate_ua())
        headers.setdefault("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8")
        headers.setdefault("Accept-Language", "es-ES,es;q=0.9,en;q=0.8")
        headers.setdefault("Accept-Encoding", "gzip, deflate")
        headers.setdefault("DNT", "1")
        headers.setdefault("Connection", "keep-alive")

        for attempt in range(self._max_retries):
            try:
                follow_redirects = kwargs.pop("follow_redirects", True)
                use_scraper = kwargs.pop("use_scraper", False)
                if use_scraper:
                    # Usa cloudscraper de forma síncrona dentro de un executor para no bloquear el EventLoop
                    loop = asyncio.get_event_loop()
                    resp = await loop.run_in_executor(None, lambda: self._scraper.get(url, headers=headers, allow_redirects=follow_redirects, timeout=self._client.timeout.read, **kwargs))
                    # Cloudscraper usa requests.Response. Lo mapeamos artificialmente hacia httpx.Response solo para homogeneizar el status_code, content, text y headers
                    # O alternativamente, usar el objeto tal cual sabiendo que tiene la misma interfaz para content, text, status_code.
                    # Asumimos interface duck-typing sencilla en base a status_code, text, headers, content
                    resp.raise_for_status()
                    return resp
                else:    
                    resp = await self._client.get(url, headers=headers, follow_redirects=follow_redirects, **kwargs)
                    resp.raise_for_status()
                    return resp
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                elif e.response.status_code in [500, 502, 503, 504]:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise
            except httpx.ConnectError:
                await asyncio.sleep(2 ** attempt)
            except requests.exceptions.RequestException as e:
                # Omitimos excepciones específicas y reintentamos si es error de red o timeout
                if getattr(e.response, "status_code", 200) in [429, 500, 502, 503, 504] or isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

        raise Exception(f"Failed after {self._max_retries} retries: {url}")

    async def post(self, url: str, **kwargs) -> httpx.Response:
        await self._apply_rate_limit(url)
        headers = kwargs.pop("headers", {})
        headers.setdefault("User-Agent", self._rotate_ua())

        for attempt in range(self._max_retries):
            try:
                resp = await self._client.post(url, headers=headers, **kwargs)
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

        raise Exception(f"Failed after {self._max_retries} retries: {url}")

    async def download_file(self, url: str, **kwargs) -> bytes:
        response = await self.get(url, **kwargs)
        return response.content

    async def head(self, url: str, **kwargs) -> httpx.Response:
        await self._apply_rate_limit(url)
        headers = kwargs.pop("headers", {})
        headers.setdefault("User-Agent", self._rotate_ua())
        return await self._client.head(url, headers=headers, **kwargs)

    def _rotate_ua(self) -> str:
        ua = self.USER_AGENTS[self._ua_index % len(self.USER_AGENTS)]
        self._ua_index += 1
        return ua

    async def _apply_rate_limit(self, url: str) -> None:
        domain = urlparse(url).netloc
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request[domain]
        if elapsed < (1.0 / self._rate_limit):
            await asyncio.sleep((1.0 / self._rate_limit) - elapsed)
        self._last_request[domain] = asyncio.get_event_loop().time()

    async def close(self):
        await self._client.aclose()
