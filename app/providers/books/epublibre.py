import re
import logging
from typing import Optional
from datetime import datetime

from bs4 import BeautifulSoup

from app.providers.base import BaseProvider
from app.core.models import SearchResult
from config import settings


logger = logging.getLogger("provider.epublibre")


class EpubLibreProvider(BaseProvider):
    def __init__(self, http_client, domain_resolver=None):
        domain = settings.EPUBLIBRE_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("epublibre")
            if active_domain:
                domain = active_domain

        super().__init__(
            provider_id="epublibre",
            display_name="EpubLibre",
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
        self.logger.info(f"Buscando en EpubLibre: '{query_to_use}'")
        if not query_to_use:
            return []

        results = []
        search_url = f"{self.base_url}/?s={query_to_use}"

        try:
            resp = await self.http_client.get(search_url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')

            seen_urls = set()
            for a in soup.select('a[href*="/book/"]'):
                href = a.get('href')
                title_text = a.get_text(strip=True)

                if not href or not title_text or title_text.lower() == 'biblioteca' or href in seen_urls:
                    continue

                seen_urls.add(href)
                match = re.search(r'/book/([^/]+)/', href)
                internal_id = match.group(1) if match else None

                if not internal_id:
                    continue

                result = SearchResult(
                    title=title_text,
                    guid=f"epublibre-{internal_id}",
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
            self.logger.error(f"Error parseando EpubLibre: {e}")

        return results[offset:]

    async def get_download_url(self, internal_id: str, **kwargs) -> str | None:
        fmt = kwargs.get('fmt', 'epub').lower()
        detail_url = f"{self.base_url}/book/{internal_id}/"

        try:
            resp = await self.http_client.get(detail_url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')

            target_text = f"EN {fmt.upper()}"
            for a in soup.find_all('a', href=True):
                text = a.get_text(strip=True).upper()
                if target_text in text or 'DESCARGAR' in text:
                    href = a['href']
                    if href.startswith('/'):
                        return f"{self.base_url}{href}"
                    return href

            self.logger.warning(f"No se encontró enlace de descarga para {internal_id} en {fmt}")
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
        import re
        from bs4 import BeautifulSoup
        from datetime import datetime
        from config import settings

        self.logger.info(f"EpubLibre browse: homepage scrape (offset={offset}, limit={limit})")
        results = []
        url = self.base_url

        try:
            resp = await self.http_client.get(url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')

            seen_urls = set()
            for a in soup.select('a[href*="/book/"]'):
                href = a.get('href')
                title_text = a.get_text(strip=True)
                if not href or not title_text or title_text.lower() == 'biblioteca' or href in seen_urls:
                    continue
                seen_urls.add(href)
                match = re.search(r'/book/([^/]+)/', href)
                internal_id = match.group(1) if match else None
                if not internal_id:
                    continue
                result = SearchResult(
                    title=title_text,
                    guid=f"epublibre-{internal_id}",
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
            self.logger.error(f"EpubLibre browse error: {e}")

        return results[offset:]
