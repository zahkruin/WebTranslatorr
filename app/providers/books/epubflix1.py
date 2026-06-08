"""
Provider para epubflix1.com - Libros electrónicos en español.

HÍBRIDO: Usa WordPress REST API para búsqueda (rápido, estructurado).
Si la API no devuelve resultados, fallback a scraping HTML.
La descarga sigue usando scraping de la página de detalle.

WordPress REST API: /wp-json/wp/v2/posts?search={query}
"""
import re
import logging
from typing import Optional
from datetime import datetime

from bs4 import BeautifulSoup

from app.providers.base import BaseProvider
from app.core.models import SearchResult
from app.scraping.wp_api_client import WordPressApiClient
from config import settings


logger = logging.getLogger("provider.epubflix1")


class Epubflix1Provider(BaseProvider):
    # WordPress REST API confirmed enabled as of 2026-06-08
    _USE_API = True
    _API_PER_PAGE = 20

    def __init__(self, http_client, domain_resolver=None):
        domain = settings.EPUBFLIX1_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("epubflix1")
            if active_domain:
                domain = active_domain

        super().__init__(
            provider_id="epubflix1",
            display_name="Epubflix1",
            base_url=domain,
            http_client=http_client,
            categories=[7000, 7020, 8000, 8010]
        )

        # WordPress REST API client (try API first, fall back to scraping)
        self._api = WordPressApiClient(
            http_client=http_client,
            base_url=domain,
            provider_id=self.provider_id,
            requires_scraper=True,
            per_page=self._API_PER_PAGE,
        )

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
        self.logger.info(f"Buscando en Epubflix1: '{query_to_use}'")
        if not query_to_use:
            return []

        # ── Strategy 1: WordPress REST API ──
        if self._USE_API:
            try:
                api_results = await self._api.search(
                    query_to_use, limit=limit, offset=offset
                )
                if api_results:
                    self.logger.info(
                        f"Epubflix1 API: {len(api_results)} results for '{query_to_use}'"
                    )
                    return api_results
            except Exception as e:
                self.logger.warning(f"Epubflix1 API fallback: {e}")

        # ── Strategy 2: HTML scraping (fallback) ──
        self.logger.info(f"Epubflix1: falling back to HTML scraping for '{query_to_use}'")
        return await self._search_scrape(query_to_use, offset, limit)

    async def _search_scrape(
        self, query_to_use: str, offset: int, limit: int
    ) -> list[SearchResult]:
        """HTML scraping fallback (original implementation)."""
        results = []
        search_url = f"{self.base_url}/?s={query_to_use}"

        try:
            resp = await self.http_client.get(search_url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')

            seen_urls = set()
            for a in soup.select(
                'a[href*="/book/"], a[href*="/libro/"], h2.entry-title a, h3.entry-title a'
            ):
                href = a.get('href')
                title_text = a.get_text(strip=True)

                if not href or not title_text or href in seen_urls:
                    continue

                seen_urls.add(href)
                match = re.search(r'/(?:book|libro)/([^/]+)/?', href)
                internal_id = match.group(1) if match else None

                if not internal_id:
                    internal_id = [x for x in href.rstrip('/').split('/') if x][-1]

                result = SearchResult(
                    title=title_text,
                    guid=f"epubflix1-{internal_id}",
                    link=href if href.startswith('http') else f"{self.base_url}{href}",
                    download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={internal_id}&fmt=epub",
                    size_bytes=1000000,
                    pub_date=datetime.now(),
                    categories=[7020],
                    description=f"Libro: {title_text}",
                )
                results.append(result)

                if len(results) >= limit:
                    break

        except Exception as e:
            self.logger.error(f"Error parseando Epubflix1: {e}")

        return results[offset:]

    async def get_download_url(self, internal_id: str, **kwargs) -> str | None:
        fmt = kwargs.get('fmt', 'epub').lower()
        # Try both /book/ and /libro/ paths
        for path_prefix in ['/book/', '/libro/']:
            detail_url = f"{self.base_url}{path_prefix}{internal_id}/"
            try:
                resp = await self.http_client.get(detail_url, use_scraper=True)
                soup = BeautifulSoup(resp.text, 'lxml')

                target_text = f"EN {fmt.upper()}"
                for a in soup.find_all('a', href=True):
                    text = a.get_text(strip=True).upper()
                    if target_text in text or 'DESCARGAR' in text or 'DOWNLOAD' in text:
                        href = a['href']
                        if href.startswith('/'):
                            return f"{self.base_url}{href}"
                        return href

                # Also try any link with .epub / .mobi / .pdf extension
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if href.endswith(f'.{fmt}') or f'.{fmt}?' in href:
                        if href.startswith('/'):
                            return f"{self.base_url}{href}"
                        return href

            except Exception as e:
                self.logger.debug(f"Error con {detail_url}: {e}")
                continue

        self.logger.warning(f"No se encontró enlace de descarga para {internal_id} en {fmt}")
        return None
