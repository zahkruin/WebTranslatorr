import re
import logging
from typing import Optional
from datetime import datetime
from urllib.parse import urlencode, quote_plus

from bs4 import BeautifulSoup

from app.providers.base import BaseProvider
from app.core.models import SearchResult
from app.core.exceptions import ProviderBlockedError
from app.services.download_tokens import build_download_url
from config import settings


logger = logging.getLogger("provider.annasarchive")


class AnnasArchiveProvider(BaseProvider):
    def __init__(self, http_client, domain_resolver=None):
        domain = settings.ANNASARCHIVE_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("annasarchive")
            if active_domain:
                domain = active_domain

        super().__init__(
            provider_id="annasarchive",
            display_name="Anna's Archive",
            base_url=domain,
            http_client=http_client,
            categories=[7000, 7020, 8000, 8010],
            query_language="es",
        )

    async def _fetch(self, url: str, use_flaresolverr_fallback: bool = True):
        try:
            return await self.http_client.get(url, use_scraper=True, rate_limit=0.5)
        except Exception:
            if use_flaresolverr_fallback and settings.FLARESOLVERR_URL:
                self.logger.warning("cloudscraper failed, falling back to FlareSolverr")
                try:
                    return await self.http_client.get(url, use_flaresolverr=True, rate_limit=0.5)
                except Exception as e2:
                    self.logger.error(f"FlareSolverr fallback also failed: {e2}")
            raise

    def _is_cloudflare_challenge(self, soup: BeautifulSoup) -> bool:
        title_text = (soup.title.get_text().lower() if soup.title else '')
        if 'just a moment' in title_text:
            return True
        if soup.select_one('#challenge-error-text, .cf-browser-verification, #cf-challenge-running'):
            return True
        return False

    def _extract_title(self, a_tag) -> str | None:
        for h in ('h3', 'h2', 'h1', 'h4'):
            el = a_tag.find(h)
            if el:
                return el.get_text(strip=True)

        for sel in ('div.text-xl', 'div.font-bold', 'div.truncate', 'span.text-lg'):
            el = a_tag.select_one(sel)
            if el:
                return el.get_text(strip=True)

        for el in a_tag.find_all(['div', 'span']):
            text = el.get_text(strip=True)
            if len(text) >= 3:
                return text

        text = a_tag.get_text(strip=True)
        return text if len(text) >= 3 else None

    def _find_download_url(self, soup) -> str | None:
        for a in soup.select('a.js-download-link'):
            text = a.get_text(strip=True).lower()
            href = a.get('href', '')
            if any(kw in text for kw in ('slow', 'partner', 'libgen', 'download')):
                return self._normalize_link(href)

        for a in soup.select('a.js-download-link'):
            href = a.get('href', '')
            if href:
                return self._normalize_link(href)

        for a in soup.select('a[data-download], a[data-partner]'):
            return self._normalize_link(a['href'])

        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True).lower()
            if any(kw in text for kw in ('download', 'libgen', 'ipfs', 'slow', 'partner')):
                return self._normalize_link(a['href'])

        for a in soup.find_all('a', href=True):
            if '/download/' in a['href'] or re.search(r'libgen\.\w+', a['href']):
                return self._normalize_link(a['href'])

        return None

    def _normalize_link(self, href: str) -> str:
        if href.startswith('/'):
            return f"{self.base_url}{href}"
        return href

    async def search(
        self,
        query: str,
        categories: list[int] = None,
        *,
        offset: int = 0,
        limit: int = 50,
        imdb_id: Optional[str] = None,
        tvdb_id: Optional[int] = None,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        author: Optional[str] = None,
        title: Optional[str] = None,
        **kwargs
    ) -> list[SearchResult]:
        combined_query = self._combine_query(query, author, title)
        query_to_use = self.normalize_query(combined_query)
        self.logger.info(f"Buscando en Anna's Archive: '{query_to_use}'")
        if not query_to_use:
            return []

        results = []
        lang_code = self.query_language or "es"
        params = urlencode({'q': query_to_use, 'lang': lang_code, 'ext': 'epub'}, quote_via=quote_plus)
        search_url = f"{self.base_url}/search?{params}"

        try:
            resp = await self._fetch(search_url)
            soup = BeautifulSoup(resp.text, 'lxml')

            if self._is_cloudflare_challenge(soup):
                self.logger.error(f"Cloudflare challenge detected for search: {search_url}")
                return []

            seen_urls = set()
            for a in soup.select('a[href*="/md5/"]'):
                href = a.get('href')

                title_text = self._extract_title(a)
                if not title_text:
                    continue

                if not href or href in seen_urls:
                    continue

                seen_urls.add(href)
                internal_id = href.split('/md5/')[-1]

                result = SearchResult(
                    title=title_text,
                    guid=f"annasarchive-{internal_id}",
                    link=f"{self.base_url}{href}",
                    download_url=build_download_url(self.provider_id, internal_id, "epub"),
                    size_bytes=1000000,
                    pub_date=datetime.now(),
                    categories=[7000, 7020, 8000, 8010],
                    description=f"Libro: {title_text}",
                )
                results.append(result)

                if len(results) >= limit:
                    break

        except Exception as e:
            self.logger.error(f"Error parseando Anna's Archive: {e}")

        return results[offset:]

    async def get_download_url(self, internal_id: str, **kwargs) -> str | None:
        detail_url = f"{self.base_url}/md5/{internal_id}"

        try:
            resp = await self._fetch(detail_url)
            soup = BeautifulSoup(resp.text, 'lxml')

            if self._is_cloudflare_challenge(soup):
                self.logger.error(f"Cloudflare challenge detected for detail: {detail_url}")
                return None

            download_url = self._find_download_url(soup)
            if download_url:
                return download_url

            self.logger.warning(f"No se encontró enlace de descarga para {internal_id}")
        except Exception as e:
            self.logger.error(f"Error obteniendo download url de {internal_id}: {e}")

        return None

    async def browse(
        self,
        categories: list[int] = None,
        *,
        offset: int = 0,
        limit: int = 50,
        **kwargs
    ) -> list[SearchResult]:
        from bs4 import BeautifulSoup
        from datetime import datetime

        self.logger.info(f"Anna's Archive browse: homepage (offset={offset}, limit={limit})")
        results = []
        url = f"{self.base_url}/"

        try:
            resp = await self._fetch(url)
            soup = BeautifulSoup(resp.text, 'lxml')

            if self._is_cloudflare_challenge(soup):
                self.logger.error(f"Cloudflare challenge detected for browse: {url}")
                return []

            seen_urls = set()
            for a in soup.select('a[href*="/md5/"]'):
                href = a.get('href')
                title_text = self._extract_title(a)
                if not title_text:
                    continue

                if not href or href in seen_urls:
                    continue
                if len(title_text) < 3:
                    continue
                seen_urls.add(href)
                internal_id = href.split('/md5/')[-1]

                result = SearchResult(
                    title=title_text,
                    guid=f"annasarchive-{internal_id}",
                    link=f"{self.base_url}{href}",
                    download_url=build_download_url(self.provider_id, internal_id, "epub"),
                    size_bytes=1000000,
                    pub_date=datetime.now(),
                    categories=[7000, 7020, 8000, 8010],
                    description=f"Libro: {title_text}",
                )
                results.append(result)
                if len(results) >= limit:
                    break
        except Exception as e:
            self.logger.error(f"Anna's Archive browse error: {e}")

        return results[offset:]

    async def is_healthy(self) -> bool:
        try:
            resp = await self.http_client.get(self.base_url, use_scraper=True, rate_limit=0.5)
            if resp.status_code != 200:
                return False
            soup = BeautifulSoup(resp.text, 'lxml')
            return not self._is_cloudflare_challenge(soup)
        except Exception:
            return False
