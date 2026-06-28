"""
Provider para libgen.ee - Library Genesis.

Library Genesis es un repositorio masivo de libros académicos y generales.
Estructura:
- Búsqueda: /search.php?req={query}&lg_topic=libgen&open=0&view=simple&res=25&phrase=1&column=def
- Detalle/Descarga: /book/index.php?md5={MD5_HASH}
- Descarga directa: diversos mirrors
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


logger = logging.getLogger("provider.libgen")


class LibgenProvider(BaseProvider):
    def __init__(self, http_client, domain_resolver=None):
        domain = settings.LIBGEN_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("libgen")
            if active_domain:
                domain = active_domain

        super().__init__(
            provider_id="libgen",
            display_name="Library Genesis",
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
        self.logger.info(f"Buscando en Library Genesis: '{query_to_use}'")
        if not query_to_use:
            return []

        results = []
        # Libgen search URL with simple view
        encoded_query = quote_plus(query_to_use)
        search_url = f"{self.base_url}/search.php?req={encoded_query}&lg_topic=libgen&open=0&view=simple&res=25&phrase=1&column=def"

        try:
            resp = await self.http_client.get(search_url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')

            # Libgen results are in a table
            # Find all rows that contain book data
            table = soup.find('table', class_='c')
            if not table:
                self.logger.debug("No se encontró tabla de resultados en Libgen")
                return []

            rows = table.find_all('tr')[1:]  # Skip header row
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 10:
                    continue

                # Extract title and author from columns
                title_td = cols[2] if len(cols) > 2 else None
                author_td = cols[1] if len(cols) > 1 else None

                if not title_td:
                    continue

                title_text = title_td.get_text(strip=True)
                author_text = author_td.get_text(strip=True) if author_td else ""

                # Find MD5 hash (usually in a link)
                md5_link = title_td.find('a', href=lambda h: h and 'md5=' in h)
                md5 = None
                if md5_link:
                    href = md5_link.get('href', '')
                    md5_match = re.search(r'md5=([a-f0-9]{32})', href, re.IGNORECASE)
                    if md5_match:
                        md5 = md5_match.group(1).lower()

                if not md5:
                    continue

                # Extract year and size
                year = cols[4].get_text(strip=True) if len(cols) > 4 else ""
                size_text = cols[6].get_text(strip=True) if len(cols) > 6 else ""
                extension = cols[7].get_text(strip=True).lower() if len(cols) > 7 else "epub"

                # Estimate size in bytes
                size_bytes = self._parse_size(size_text)

                result = SearchResult(
                    title=f"{title_text} - {author_text}",
                    guid=f"libgen-{md5}",
                    link=f"{self.base_url}/book/index.php?md5={md5}",
                    download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={md5}&fmt={extension}",
                    size_bytes=size_bytes,
                    pub_date=datetime.now(),
                    categories=[7000, 7020, 8000, 8010],
                    description=f"Libro: {title_text} | Autor: {author_text} | Año: {year} | Formato: {extension}",
                    author=author_text or None,
                    extra_attrs={"format": extension, "year": year},
                )
                results.append(result)

                if len(results) >= limit:
                    break

        except Exception as e:
            self.logger.error(f"Error parseando Library Genesis: {e}")

        return results[offset:]

    async def get_download_url(self, internal_id: str, **kwargs) -> str | None:
        """
        internal_id is the MD5 hash of the book.
        Resolves through the book detail page to find a working download mirror.
        """
        fmt = kwargs.get('fmt', 'epub').lower()
        detail_url = f"{self.base_url}/book/index.php?md5={internal_id}"

        try:
            resp = await self.http_client.get(detail_url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')

            # Find download links
            # Common patterns in Libgen
            for a in soup.find_all('a', href=True):
                href = a['href']
                text = a.get_text(strip=True).lower()

                # Direct download links
                if 'libgen' in href and ('get' in href or 'download' in href or 'main' in href):
                    if href.startswith('/'):
                        return f"{self.base_url}{href}"
                    return href

                # Mirror links
                if any(word in text for word in ['epub', 'mobi', 'pdf', 'download', fmt]):
                    if href.startswith('/'):
                        return f"{self.base_url}{href}"
                    return href

                # Cloudflare / IPFS gateway links
                if 'cloudflare' in href or 'ipfs' in href:
                    if href.startswith('/'):
                        return f"{self.base_url}{href}"
                    return href

            # Fallback: try direct download construction
            # Libgen often has direct download at /main/{first_two_chars_of_md5}/{md5}
            direct_url = f"{self.base_url}/main/{internal_id[:2]}/{internal_id}"
            self.logger.info(f"Intentando descarga directa: {direct_url}")
            return direct_url

        except Exception as e:
            self.logger.error(f"Error obteniendo download url de {internal_id}: {e}")

        return None

    @staticmethod
    def _parse_size(size_text: str) -> int:
        """Convierte texto de tamaño a bytes."""
        if not size_text:
            return 1000000

        size_text = size_text.strip().lower()
        try:
            if 'kb' in size_text:
                return int(float(size_text.replace('kb', '').strip()) * 1024)
            elif 'mb' in size_text:
                return int(float(size_text.replace('mb', '').strip()) * 1024 * 1024)
            elif 'gb' in size_text:
                return int(float(size_text.replace('gb', '').strip()) * 1024 * 1024 * 1024)
            else:
                # Try plain number
                return int(float(size_text))
        except ValueError:
            return 1000000

    async def browse(
        self,
        categories: list[int] = None,
        *,
        offset: int = 0,
        limit: int = 50,
        **kwargs
    ) -> list[SearchResult]:
        """RSS/browse mode: scrape LibGen /last.php for recently added books."""
        import re as re_mod
        from bs4 import BeautifulSoup
        from datetime import datetime

        self.logger.info(f"LibGen browse: /last.php (offset={offset}, limit={limit})")
        results = []
        url = f"{self.base_url}/last.php"

        try:
            resp = await self.http_client.get(url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')

            table = soup.find('table', class_='c')
            if not table:
                self.logger.debug("LibGen browse: no table found on /last.php")
                return []

            rows = table.find_all('tr')[1:]  # Skip header
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 10:
                    continue

                title_td = cols[2] if len(cols) > 2 else None
                author_td = cols[1] if len(cols) > 1 else None
                if not title_td:
                    continue

                title_text = title_td.get_text(strip=True)
                author_text = author_td.get_text(strip=True) if author_td else ""

                md5_link = title_td.find('a', href=lambda h: h and 'md5=' in h)
                md5 = None
                if md5_link:
                    href = md5_link.get('href', '')
                    md5_match = re_mod.search(r'md5=([a-f0-9]{32})', href, re_mod.IGNORECASE)
                    if md5_match:
                        md5 = md5_match.group(1).lower()
                if not md5:
                    continue

                year = cols[4].get_text(strip=True) if len(cols) > 4 else ""
                size_text = cols[6].get_text(strip=True) if len(cols) > 6 else ""
                extension = cols[7].get_text(strip=True).lower() if len(cols) > 7 else "epub"
                size_bytes = self._parse_size(size_text)

                result = SearchResult(
                    title=f"{title_text} - {author_text}",
                    guid=f"libgen-{md5}",
                    link=f"{self.base_url}/book/index.php?md5={md5}",
                    download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={md5}&fmt={extension}",
                    size_bytes=size_bytes,
                    pub_date=datetime.now(),
                    categories=[7000, 7020, 8000, 8010],
                    description=f"Libro: {title_text} | Autor: {author_text} | Año: {year} | Formato: {extension}",
                    author=author_text or None,
                    extra_attrs={"format": extension, "year": year},
                )
                results.append(result)
                if len(results) >= limit:
                    break
        except Exception as e:
            self.logger.error(f"LibGen browse error: {e}")

        return results[offset:]
