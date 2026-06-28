"""
Provider para mundoepublibre1.com - Libros electrónicos en español.

Estructura típica (WordPress con catálogo de libros):
- Búsqueda: /?s={query}
- Detalle: /book/{slug}/ o /libro/{slug}/
- Descarga: enlace directo en página de detalle
"""

import re
import logging
from typing import Optional
from datetime import datetime

from bs4 import BeautifulSoup

from app.providers.base import BaseProvider
from app.core.models import SearchResult
from config import settings


logger = logging.getLogger("provider.mundoepublibre1")


class MundoEpubLibre1Provider(BaseProvider):
    def __init__(self, http_client, domain_resolver=None):
        domain = settings.MUNDOEPUBLIBRE1_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("mundoepublibre1")
            if active_domain:
                domain = active_domain

        super().__init__(
            provider_id="mundoepublibre1",
            display_name="MundoEpubLibre1",
            base_url=domain,
            http_client=http_client,
            categories=[7000, 7020, 8000, 8010]
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
        self.logger.info(f"Buscando en MundoEpubLibre1: '{query_to_use}'")
        if not query_to_use:
            return []

        results = []
        search_url = f"{self.base_url}/?s={query_to_use}"

        try:
            resp = await self.http_client.get(search_url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')

            seen_urls = set()
            for selector in ['a[href*="/book/"]', 'a[href*="/libro/"]',
                             'h2.entry-title a', 'h3.entry-title a']:
                for a in soup.select(selector):
                    href = a.get('href')
                    title_text = a.get_text(strip=True)

                    if not href or not title_text or title_text.lower() in ['biblioteca', 'inicio', 'home']:
                        continue

                    if href in seen_urls:
                        continue

                    seen_urls.add(href)
                    match = re.search(r'/(?:book|libro)/([^/]+)/', href)
                    internal_id = match.group(1) if match else None

                    if not internal_id:
                        internal_id = [x for x in href.rstrip('/').split('/') if x][-1]

                    result = SearchResult(
                        title=title_text,
                        guid=f"mundoepublibre1-{internal_id}",
                        link=href if href.startswith('http') else f"{self.base_url}{href}",
                        download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={internal_id}&fmt=epub",
                        size_bytes=1000000,
                        pub_date=datetime.now(),
                        categories=[7000, 7020, 8000, 8010],
                        description=f"Libro: {title_text}",
                    )
                    results.append(result)

                    if len(results) >= limit:
                        break

                if len(results) >= limit:
                    break

        except Exception as e:
            self.logger.error(f"Error parseando MundoEpubLibre1: {e}")

        return results[offset:]

    async def get_download_url(self, internal_id: str, **kwargs) -> str | None:
        fmt = kwargs.get('fmt', 'epub').lower()

        for path_prefix in ['/book/', '/libro/', '/descargar/']:
            detail_url = f"{self.base_url}{path_prefix}{internal_id}/"
            try:
                resp = await self.http_client.get(detail_url, use_scraper=True)
                soup = BeautifulSoup(resp.text, 'lxml')

                target_text = f"EN {fmt.upper()}"
                for a in soup.find_all('a', href=True):
                    text = a.get_text(strip=True).upper()
                    href = a['href']

                    if target_text in text or 'DESCARGAR' in text or 'DOWNLOAD' in text:
                        if '/genre/' not in href and '/autor/' not in href:
                            if href.startswith('/'):
                                return f"{self.base_url}{href}"
                            return href

                    if href.endswith(f'.{fmt}') or f'.{fmt}?' in href:
                        if href.startswith('/'):
                            return f"{self.base_url}{href}"
                        return href

            except Exception as e:
                self.logger.debug(f"Error con {detail_url}: {e}")
                continue

        self.logger.warning(f"No se encontró enlace de descarga para {internal_id} en {fmt}")
        return None

    async def browse(
        self,
        categories: list[int] = None,
        *,
        offset: int = 0,
        limit: int = 50,
        **kwargs
    ) -> list[SearchResult]:
        """RSS/browse mode: scrape homepage for recent books."""
        import re as re_mod
        from bs4 import BeautifulSoup
        from datetime import datetime

        self.logger.info(f"MundoEpubLibre1 browse: homepage (offset={offset}, limit={limit})")
        results = []
        url = f"{self.base_url}/"

        try:
            resp = await self.http_client.get(url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')

            seen_urls = set()
            for a in soup.select('a[href*="/book/"], a[href*="/libro/"]'):
                href = a.get('href')
                title_text = a.get_text(strip=True)
                if not href or not title_text or href in seen_urls:
                    continue
                if len(title_text) < 3:
                    continue
                seen_urls.add(href)
                match = re_mod.search(r'/(?:book|libro)/([^/]+)/', href)
                internal_id = match.group(1) if match else None
                if not internal_id:
                    continue
                result = SearchResult(
                    title=title_text,
                    guid=f"mundoepublibre1-{internal_id}",
                    link=href if href.startswith('http') else f"{self.base_url}{href}",
                    download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={internal_id}&fmt=epub",
                    size_bytes=1000000,
                    pub_date=datetime.now(),
                    categories=[7000, 7020, 8000, 8010],
                    description=f"Libro: {title_text}",
                )
                results.append(result)
                if len(results) >= limit:
                    break
        except Exception as e:
            self.logger.error(f"MundoEpubLibre1 browse error: {e}")

        return results[offset:]

