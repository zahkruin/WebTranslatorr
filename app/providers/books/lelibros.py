"""
Provider para lelibros.online - Libros electrónicos en español.

LeLibros es un sitio con descarga directa desde servidor propio,
sin redirecciones ni anuncios. Estructura:

- Búsqueda: GET /?s={query}
- Resultados: Grid de portadas con título y autor
- Detalle: Página con metadatos y 4 botones de descarga directa
- Descarga: Enlaces directos a EPUB/PDF/MOBI en servidor propio

Nota: Sitio bloqueado judicialmente en España (2020). Puede cambiar de dominio.
"""

import re
import logging
from typing import Optional
from datetime import datetime
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from app.providers.base import BaseProvider
from app.core.models import SearchResult
from config import settings


logger = logging.getLogger("provider.lelibros")


class LeLibrosProvider(BaseProvider):
    """
    Provider para LeLibros - descarga directa sin anuncios.
    Probablemente el más simple de implementar de los nuevos.
    """

    def __init__(self, http_client, domain_resolver=None):
        domain = settings.LELIBROS_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("lelibros")
            if active_domain:
                domain = active_domain

        super().__init__(
            provider_id="lelibros",
            display_name="LeLibros",
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
        self.logger.info(f"Buscando en LeLibros: '{query_to_use}'")
        if not query_to_use:
            return []

        results = []
        encoded_query = quote_plus(query_to_use)
        # Try multiple search URL patterns
        search_urls = [
            f"{self.base_url}/?s={encoded_query}",
            f"{self.base_url}/search?q={encoded_query}",
        ]

        resp = None
        for url in search_urls:
            try:
                resp = await self.http_client.get(url, use_scraper=True)
                if resp.status_code == 200 and len(resp.text) > 500:
                    break
            except Exception:
                continue

        if resp is None or resp.status_code != 200:
            self.logger.warning("No se pudo realizar búsqueda en LeLibros")
            return []

        try:
            soup = BeautifulSoup(resp.text, 'lxml')
            seen_urls = set()

            # LeLibros usually has a grid of book cards/entries
            # Try multiple selectors for book links
            selectors = [
                'article a[href]',
                'div.entry-content a[href]',
                'div.book a[href]',
                'a[href*="/libro/"]',
                'a[href*="/book/"]',
                '.entry-title a',
                'h2 a', 'h3 a',
            ]

            for selector in selectors:
                for link in soup.select(selector):
                    href = link.get('href', '')
                    title_text = link.get_text(strip=True)

                    # Skip utility links
                    if not href or not title_text or len(title_text) < 3:
                        continue
                    if any(skip in href.lower() for skip in [
                        '/category/', '/author/', '/tag/', '/page/',
                        'facebook', 'twitter', 'instagram',
                        'wp-content', 'wp-admin', 'wp-login',
                    ]):
                        continue
                    if title_text.lower() in (
                        'inicio', 'home', 'leer más', 'leer mas',
                        'biblioteca', 'contacto', 'busque', 'buscar',
                        'literatura e ficción', 'tecnicos e academicos',
                        'vida practica y otros',
                    ):
                        continue

                    if href in seen_urls:
                        continue
                    seen_urls.add(href)

                    # Normalize link
                    if href.startswith('/'):
                        link_full = f"{self.base_url}{href}"
                    elif not href.startswith('http'):
                        link_full = f"{self.base_url}/{href}"
                    else:
                        link_full = href

                    # Extract internal ID from URL
                    internal_id = self._extract_internal_id(href, title_text)

                    result = SearchResult(
                        title=title_text,
                        guid=f"lelibros-{internal_id}",
                        link=link_full,
                        download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={internal_id}&fmt=epub",
                        size_bytes=2000000,
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
            self.logger.error(f"Error parseando LeLibros: {e}")

        return results[offset:]

    async def get_download_url(self, internal_id: str, **kwargs) -> str | None:
        """
        Resuelve la URL de descarga para un libro de LeLibros.
        LeLibros tiene botones directos: Descargar en PDF, EPUB, MOBI.
        """
        fmt = kwargs.get('fmt', 'epub').lower()

        # Reconstruct detail URL from internal_id
        detail_url = f"{self.base_url}/{internal_id}"
        if not internal_id.startswith('/'):
            detail_url = f"{self.base_url}/{internal_id}"

        try:
            resp = await self.http_client.get(detail_url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')

            # LeLibros has direct download buttons with text patterns
            fmt_patterns = {
                'epub': ['descargar en epub', 'descargar epub', 'epub', 'download epub'],
                'pdf': ['descargar en pdf', 'descargar pdf', 'pdf', 'download pdf'],
                'mobi': ['descargar en mobi', 'descargar mobi', 'mobi', 'download mobi'],
            }

            patterns_to_try = fmt_patterns.get(fmt, fmt_patterns['epub'])

            # Pass 1: Try format-specific matches (button text + extension)
            for a in soup.find_all('a', href=True):
                href = a['href']
                text = a.get_text(strip=True).lower()

                # Check button text for requested format
                if any(pat in text for pat in patterns_to_try):
                    if href.startswith('/'):
                        return f"{self.base_url}{href}"
                    return href

                # Check href for format extension
                if href.endswith(f'.{fmt}') or f'.{fmt}?' in href:
                    if href.startswith('/'):
                        return f"{self.base_url}{href}"
                    return href

            # Pass 2: Fallback - any generic download link
            for a in soup.find_all('a', href=True):
                href = a['href']
                text = a.get_text(strip=True).lower()
                if any(word in text for word in ('descargar', 'download', 'descarga')):
                    if href.startswith('/'):
                        return f"{self.base_url}{href}"
                    return href

            # Pass 3: Final fallback - any direct file links
            for a in soup.find_all('a', href=True):
                href = a['href']
                if any(href.lower().endswith(ext) for ext in ('.epub', '.pdf', '.mobi', '.zip')):
                    if href.startswith('/'):
                        return f"{self.base_url}{href}"
                    return href

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
        """RSS/browse mode: scrape homepage for recent books."""
        import re as re_mod
        from bs4 import BeautifulSoup
        from datetime import datetime

        self.logger.info(f"LeLibros browse: homepage (offset={offset}, limit={limit})")
        results = []
        url = self.base_url

        try:
            resp = await self.http_client.get(url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')

            seen_urls = set()
            for selector in ['article a[href]', 'div.entry-content a[href]', 'div.book a[href]',
                             'a[href*="/libro/"]', 'a[href*="/book/"]', '.entry-title a',
                             'h2 a', 'h3 a']:
                for a in soup.select(selector):
                    href = a.get('href')
                    title_text = a.get_text(strip=True)
                    if not href or not title_text or href in seen_urls:
                        continue
                    if len(title_text) < 5 or '/' not in href:
                        continue
                    seen_urls.add(href)
                    internal_id = re_mod.search(r'/([^/]+)/?$', href.rstrip('/'))
                    internal_id = internal_id.group(1) if internal_id else None
                    if not internal_id or internal_id in ('libro', 'book', self.base_url.rstrip('/').split('/')[-1]):
                        continue
                    result = SearchResult(
                        title=title_text,
                        guid=f"lelibros-{internal_id}",
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
            self.logger.error(f"LeLibros browse error: {e}")

        return results[offset:]


    @staticmethod
    def _extract_internal_id(href: str, title: str) -> str:
        """Extract internal ID from URL or generate from title."""
        # Try to get slug from URL
        parts = [p for p in href.rstrip('/').split('/') if p]
        if parts:
            return parts[-1]
        # Fallback: slugify title
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        return slug or title.replace(' ', '-').lower()
