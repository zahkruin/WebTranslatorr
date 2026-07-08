"""
Provider para z-library.sk - Z-Library.

Z-Library es un repositorio masivo de libros electrónicos.
Nota: Z-Library cambia frecuentemente de dominio. El dominio base
se mantiene actualizado vía DomainResolver.

Estructura:
- Búsqueda: /s/{query}?page=1&language=spanish&ext=epub
- Detalle: /book/{id}
- Descarga: /book/{id}/download o enlace directo en página de detalle
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


logger = logging.getLogger("provider.zlibrary")


class ZLibraryProvider(BaseProvider):
    def __init__(self, http_client, domain_resolver=None):
        domain = settings.ZLIBRARY_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("zlibrary")
            if active_domain:
                domain = active_domain

        super().__init__(
            provider_id="zlibrary",
            display_name="Z-Library",
            base_url=domain,
            http_client=http_client,
            categories=[7000, 7020, 8000, 8010],
            query_language="es",
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
        self.logger.info(f"Buscando en Z-Library: '{query_to_use}'")
        if not query_to_use:
            return []

        results = []
        encoded_query = quote_plus(query_to_use)
        lang_code = self.query_language or "es"

        # Try multiple search URL patterns (Z-Library has changed patterns over time)
        search_urls = [
            f"{self.base_url}/s/{encoded_query}/?language={lang_code}&ext=epub",
            f"{self.base_url}/s/{encoded_query}?language=spanish&ext=epub",
            f"{self.base_url}/search?q={encoded_query}&lang={lang_code}",
        ]

        resp = None
        url_used = None
        for url in search_urls:
            try:
                resp = await self.http_client.get(url, use_scraper=True)
                if resp.status_code == 200 and len(resp.text) > 500:
                    url_used = url
                    break
            except Exception:
                continue

        if resp is None:
            self.logger.warning("No se pudo realizar búsqueda en Z-Library")
            return []

        try:
            soup = BeautifulSoup(resp.text, 'lxml')

            # Try multiple result selectors common in Z-Library
            # Z-Library typically uses card-based layouts
            seen_ids = set()

            # Method 1: Modern Z-Library (book cards)
            for card in soup.select('div[class*="book"], div[class*="card"], article, div[class*="result"]'):
                link = card.find('a', href=True)
                if not link:
                    continue

                href = link.get('href', '')

                # Extract book ID from URL
                book_id = None
                id_match = re.search(r'/book/(\d+)', href)
                if id_match:
                    book_id = id_match.group(1)

                if not book_id:
                    continue

                if book_id in seen_ids:
                    continue
                seen_ids.add(book_id)

                title_elem = card.find(['h2', 'h3', 'h4', 'h5', 'span', 'div'],
                                       class_=re.compile(r'title|name|book', re.I))
                if not title_elem:
                    title_elem = link
                title_text = title_elem.get_text(strip=True)

                if not title_text or len(title_text) < 3:
                    continue

                # Try to find author
                author_elem = card.find(['span', 'div', 'p', 'small'],
                                        class_=re.compile(r'auth', re.I))
                author_text = author_elem.get_text(strip=True) if author_elem else ""

                # Try to find extension/size
                ext_elem = card.find(['span', 'div', 'small'],
                                     class_=re.compile(r'format|ext|type', re.I))
                extension = ext_elem.get_text(strip=True).lower() if ext_elem else "epub"
                # Clean extension
                extension = re.sub(r'[^a-z0-9]', '', extension)
                if extension not in ('epub', 'mobi', 'pdf', 'azw3', 'fb2', 'djvu', 'txt'):
                    extension = 'epub'

                result = SearchResult(
                    title=f"{title_text} - {author_text}" if author_text else title_text,
                    guid=f"zlibrary-{book_id}",
                    link=href if href.startswith('http') else f"{self.base_url}{href}",
                    download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={book_id}&fmt={extension}",
                    size_bytes=1000000,
                    pub_date=datetime.now(),
                    categories=[7000, 7020, 8000, 8010],
                    description=f"Libro: {title_text} | Autor: {author_text} | Formato: {extension}",
                    author=author_text or None,
                    extra_attrs={"format": extension},
                )
                results.append(result)

                if len(results) >= limit:
                    break

            # Method 2: Fallback - search for any /book/ links
            if not results:
                seen_urls = set()
                for a in soup.select('a[href*="/book/"]'):
                    href = a.get('href', '')
                    title_text = a.get_text(strip=True)

                    if not title_text or len(title_text) < 3 or href in seen_urls:
                        continue

                    seen_urls.add(href)
                    id_match = re.search(r'/book/(\d+)', href)
                    book_id = id_match.group(1) if id_match else None

                    if not book_id:
                        continue

                    result = SearchResult(
                        title=title_text,
                        guid=f"zlibrary-{book_id}",
                        link=href if href.startswith('http') else f"{self.base_url}{href}",
                        download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={book_id}&fmt=epub",
                        size_bytes=1000000,
                        pub_date=datetime.now(),
                        categories=[7000, 7020, 8000, 8010],
                        description=f"Libro: {title_text}",
                    )
                    results.append(result)

                    if len(results) >= limit:
                        break

        except Exception as e:
            self.logger.error(f"Error parseando Z-Library: {e}")

        return results[offset:]

    async def get_download_url(self, internal_id: str, **kwargs) -> str | None:
        """
        Resuelve la URL de descarga para un libro de Z-Library.
        internal_id: ID numérico del libro.
        """
        fmt = kwargs.get('fmt', 'epub').lower()

        # Try multiple download URL patterns
        download_patterns = [
            f"{self.base_url}/book/{internal_id}/download",
            f"{self.base_url}/book/{internal_id}",
            f"{self.base_url}/d/{internal_id}",
            f"{self.base_url}/dl/{internal_id}",
        ]

        for detail_url in download_patterns:
            try:
                resp = await self.http_client.get(detail_url, use_scraper=True)
                soup = BeautifulSoup(resp.text, 'lxml')

                # Look for download buttons/links
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    text = a.get_text(strip=True).lower()

                    # Download button text
                    if any(word in text for word in ['download', 'descargar', 'epub', fmt]):
                        if href.startswith('/'):
                            return f"{self.base_url}{href}"
                        return href

                    # Direct file links
                    if href.endswith(f'.{fmt}') or f'/dl/{internal_id}' in href:
                        if href.startswith('/'):
                            return f"{self.base_url}{href}"
                        return href

                # Look for download form/button with specific classes
                for btn in soup.select('a[class*="download"], button[class*="download"], '
                                        'a[class*="btn"], button[class*="btn"]'):
                    href = btn.get('href') or btn.get('data-url') or btn.get('data-link')
                    if href:
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
        """RSS/browse mode: scrape Z-Library homepage for featured/recent books."""
        import re as re_mod
        from bs4 import BeautifulSoup
        from datetime import datetime

        self.logger.info(f"Z-Library browse: homepage (offset={offset}, limit={limit})")
        results = []
        url = f"{self.base_url}/"

        try:
            resp = await self.http_client.get(url, use_scraper=True)
            if resp.status_code != 200 or len(resp.text) < 500:
                self.logger.warning("Z-Library browse: homepage returned empty/short response")
                return []

            soup = BeautifulSoup(resp.text, 'lxml')
            seen_ids = set()

            # Method 1: card-based layouts (same as search)
            for card in soup.select('div[class*="book"], div[class*="card"], article, div[class*="result"]'):
                link = card.find('a', href=True)
                if not link:
                    continue
                href = link.get('href', '')
                book_id = None
                id_match = re_mod.search(r'/book/(\d+)', href)
                if id_match:
                    book_id = id_match.group(1)
                if not book_id or book_id in seen_ids:
                    continue
                seen_ids.add(book_id)

                title_elem = card.find(['h2', 'h3', 'h4', 'h5', 'span', 'div'],
                                       class_=re_mod.compile(r'title|name|book', re_mod.I))
                if not title_elem:
                    title_elem = link
                title_text = title_elem.get_text(strip=True)
                if not title_text or len(title_text) < 3:
                    continue

                author_elem = card.find(['span', 'div', 'p', 'small'],
                                        class_=re_mod.compile(r'auth', re_mod.I))
                author_text = author_elem.get_text(strip=True) if author_elem else ""

                ext_elem = card.find(['span', 'div', 'small'],
                                     class_=re_mod.compile(r'format|ext|type', re_mod.I))
                extension = ext_elem.get_text(strip=True).lower() if ext_elem else "epub"
                extension = re_mod.sub(r'[^a-z0-9]', '', extension)
                if extension not in ('epub', 'mobi', 'pdf', 'azw3', 'fb2', 'djvu', 'txt'):
                    extension = 'epub'

                result = SearchResult(
                    title=f"{title_text} - {author_text}" if author_text else title_text,
                    guid=f"zlibrary-{book_id}",
                    link=href if href.startswith('http') else f"{self.base_url}{href}",
                    download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={book_id}&fmt={extension}",
                    size_bytes=1000000,
                    pub_date=datetime.now(),
                    categories=[7000, 7020, 8000, 8010],
                    description=f"Libro: {title_text} | Autor: {author_text} | Formato: {extension}",
                    author=author_text or None,
                    extra_attrs={"format": extension},
                )
                results.append(result)
                if len(results) >= limit:
                    break

            # Method 2: Fallback — any /book/ links
            if not results:
                seen_urls = set()
                for a in soup.select('a[href*="/book/"]'):
                    href = a.get('href', '')
                    title_text = a.get_text(strip=True)
                    if not title_text or len(title_text) < 3 or href in seen_urls:
                        continue
                    seen_urls.add(href)
                    id_match = re_mod.search(r'/book/(\d+)', href)
                    book_id = id_match.group(1) if id_match else None
                    if not book_id:
                        continue
                    result = SearchResult(
                        title=title_text,
                        guid=f"zlibrary-{book_id}",
                        link=href if href.startswith('http') else f"{self.base_url}{href}",
                        download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={book_id}&fmt=epub",
                        size_bytes=1000000,
                        pub_date=datetime.now(),
                        categories=[7000, 7020, 8000, 8010],
                        description=f"Libro: {title_text}",
                    )
                    results.append(result)
                    if len(results) >= limit:
                        break
        except Exception as e:
            self.logger.error(f"Z-Library browse error: {e}")

        return results[offset:]
