"""
Provider para es.booobook.bond - Libros electrónicos en español.

Estructura típica (sitio de catálogo de libros):
- Búsqueda: /?s={query} o /search/{query}
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


logger = logging.getLogger("provider.booobook")


class BooobookProvider(BaseProvider):
    def __init__(self, http_client, domain_resolver=None):
        domain = settings.BOOOBOOK_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("booobook")
            if active_domain:
                domain = active_domain

        super().__init__(
            provider_id="booobook",
            display_name="B00k.Bond",
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
        self.logger.info(f"Buscando en B00k.Bond: '{query_to_use}'")
        if not query_to_use:
            return []

        results = []

        # Try multiple search URL patterns
        search_urls = [
            f"{self.base_url}/?s={query_to_use}",
            f"{self.base_url}/search/{query_to_use}",
        ]

        resp = None
        for url in search_urls:
            try:
                resp = await self.http_client.get(url, use_scraper=True)
                if resp.status_code == 200:
                    search_url = url
                    break
            except Exception:
                continue

        if resp is None:
            self.logger.warning("No se pudo realizar búsqueda en B00k.Bond")
            return []

        try:
            soup = BeautifulSoup(resp.text, 'lxml')

            seen_urls = set()
            # Try multiple selectors common in book sites
            for selector in ['a[href*="/book/"]', 'a[href*="/libro/"]',
                             'h2.entry-title a', 'h3.entry-title a',
                             'article a[href*="/"]']:
                for a in soup.select(selector):
                    href = a.get('href')
                    title_text = a.get_text(strip=True)

                    if not href or not title_text or href in seen_urls:
                        continue

                    # Skip navigation/utility links
                    if any(skip in href for skip in ['/genre/', '/autor/', '/category/',
                                                      '/tag/', '/page/', '#']):
                        continue

                    seen_urls.add(href)
                    # Extract internal ID from URL
                    match = re.search(r'/(?:book|libro)/([^/]+)/?', href)
                    internal_id = match.group(1) if match else None

                    if not internal_id:
                        internal_id = [x for x in href.rstrip('/').split('/') if x][-1]

                    # Skip if title looks like a site section
                    if title_text.lower() in ['inicio', 'home', 'biblioteca', 'contacto']:
                        continue

                    result = SearchResult(
                        title=title_text,
                        guid=f"booobook-{internal_id}",
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

                if len(results) >= limit:
                    break

        except Exception as e:
            self.logger.error(f"Error parseando B00k.Bond: {e}")

        return results[offset:]

    async def get_download_url(self, internal_id: str, **kwargs) -> str | None:
        fmt = kwargs.get('fmt', 'epub').lower()

        # Try multiple path patterns
        for path_prefix in ['/book/', '/libro/', '/descargar/']:
            detail_url = f"{self.base_url}{path_prefix}{internal_id}/"
            try:
                resp = await self.http_client.get(detail_url, use_scraper=True)
                soup = BeautifulSoup(resp.text, 'lxml')

                # Look for download links
                target_text = f"EN {fmt.upper()}"
                for a in soup.find_all('a', href=True):
                    text = a.get_text(strip=True).upper()
                    href = a['href']

                    if target_text in text or 'DESCARGAR' in text or 'DOWNLOAD' in text:
                        if href.startswith('/'):
                            return f"{self.base_url}{href}"
                        return href

                    # Direct file links
                    if href.endswith(f'.{fmt}') or f'.{fmt}?' in href:
                        if href.startswith('/'):
                            return f"{self.base_url}{href}"
                        return href

            except Exception as e:
                self.logger.debug(f"Error con {detail_url}: {e}")
                continue

        self.logger.warning(f"No se encontró enlace de descarga para {internal_id} en {fmt}")
        return None
