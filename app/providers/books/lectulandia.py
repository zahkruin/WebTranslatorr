import re
import logging
from typing import Optional
from datetime import datetime

from bs4 import BeautifulSoup

from app.providers.base import BaseProvider
from app.core.models import SearchResult
from config import settings


logger = logging.getLogger("provider.lectulandia")


class LectulandiaProvider(BaseProvider):
    def __init__(self, http_client, domain_resolver=None):
        domain = settings.LECTULANDIA_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("lectulandia")
            if active_domain:
                domain = active_domain

        super().__init__(
            provider_id="lectulandia",
            display_name="Lectulandia",
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
        self.logger.info(f"Buscando en Lectulandia: '{query_to_use}'")
        if not query_to_use:
            return []

        results = []
        search_url = f"{self.base_url}/search/{query_to_use}"

        try:
            resp = await self.http_client.get(search_url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')

            seen_urls = set()
            for a in soup.select('a[href*="/book/"]'):
                href = a.get('href')
                title_text = a.get_text(strip=True)

                if not href or not title_text or title_text.lower() == 'libros' or href in seen_urls:
                    continue

                seen_urls.add(href)
                match = re.search(r'/book/([^/]+)/', href)
                internal_id = match.group(1) if match else None

                if not internal_id:
                    continue

                result = SearchResult(
                    title=title_text,
                    guid=f"lectulandia-{internal_id}",
                    link=f"{self.base_url}{href}" if href.startswith('/') else href,
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
            self.logger.error(f"Error parseando Lectulandia: {e}")

        return results[offset:]

    # ── LinkCode extraction regexes (tried in order) ──
    _LINKCODE_REGEXES = [
        re.compile(r'var linkCode = ["\']([^"\']+)["\'];'),           # var linkCode = "...";
        re.compile(r'let linkCode = ["\']([^"\']+)["\'];'),           # let linkCode = "...";
        re.compile(r'const linkCode = ["\']([^"\']+)["\'];'),         # const linkCode = "...";
        re.compile(r'linkCode\s*=\s*["\']([^"\']+)["\']'),           # linkCode = "...";
        re.compile(r'window\.linkCode\s*=\s*["\']([^"\']+)["\']'),   # window.linkCode = "...";
        re.compile(r'"linkCode"\s*:\s*"([^"]+)"'),                    # JSON: "linkCode": "..."
        re.compile(r'["\']([^"\']{8,})["\']'),                        # Fallback: any quoted string 8+ chars
    ]

    async def get_download_url(self, internal_id: str, **kwargs) -> str | None:
        detail_url = f"{self.base_url}/book/{internal_id}/"

        try:
            resp = await self.http_client.get(detail_url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')

            # Step 1: find /download.php? link
            download_php_link = None
            for a in soup.find_all('a', href=True):
                if '/download.php?' in a['href']:
                    download_php_link = a['href']
                    break

            if not download_php_link:
                self.logger.warning(
                    f"No se encontró enlace download.php en Lectulandia para {internal_id}"
                )
                # Fallback: search for direct download links on the detail page
                return self._fallback_download(soup, internal_id)

            # Step 2: follow the intermediate page
            inter_url = (
                self.base_url + download_php_link
                if download_php_link.startswith('/')
                else download_php_link
            )
            resp_inter = await self.http_client.get(
                inter_url, follow_redirects=True, use_scraper=True
            )

            # Step 3: parse linkCode from JS (try multiple regexes)
            code = self._extract_linkcode(resp_inter.text)
            if code:
                final_url = f"{self.base_url}/download/{code}"
                self.logger.debug(f"Lectulandia linkCode resolved: {code}")
                return final_url

            self.logger.warning(
                f"No se pudo extraer linkCode en download.php de {internal_id}"
            )

        except Exception as e:
            self.logger.error(f"Error obteniendo download url de {internal_id}: {e}")

        return None

    def _extract_linkcode(self, text: str) -> str | None:
        """Try multiple regex patterns to extract linkCode from JS/HTML."""
        for i, regex in enumerate(self._LINKCODE_REGEXES):
            match = regex.search(text)
            if match:
                code = match.group(1).strip()
                # Validate: linkCode should be alphanumeric, 6-32 chars
                if re.match(r'^[a-zA-Z0-9_-]{6,32}$', code):
                    self.logger.debug(
                        f"Lectulandia linkCode extracted with regex #{i+1}: {code}"
                    )
                    return code
        return None

    def _fallback_download(self, soup, internal_id: str) -> str | None:
        """
        Fallback: if download.php is not found, search for direct download
        links on the detail page.
        """
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True).upper()
            if any(kw in text for kw in ('DESCARGAR', 'DOWNLOAD', 'EPUB', 'PDF', 'MOBI')):
                if href.startswith('/'):
                    return f"{self.base_url}{href}"
                return href
        return None

    async def browse(
        self,
        categories: list[int] = None,
        *,
        offset: int = 0,
        limit: int = 50,
        **kwargs
    ) -> list[SearchResult]:
        """RSS/browse mode: scrape Lectulandia homepage for recent books."""
        import re as re_mod
        from bs4 import BeautifulSoup
        from datetime import datetime

        self.logger.info(f"Lectulandia browse: homepage (offset={offset}, limit={limit})")
        results = []
        url = f"{self.base_url}/"

        try:
            resp = await self.http_client.get(url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')

            seen_urls = set()
            for a in soup.select('a[href*="/book/"]'):
                href = a.get('href')
                title_text = a.get_text(strip=True)
                if not href or not title_text or title_text.lower() == 'libros' or href in seen_urls:
                    continue
                seen_urls.add(href)
                match = re_mod.search(r'/book/([^/]+)/', href)
                internal_id = match.group(1) if match else None
                if not internal_id:
                    continue
                result = SearchResult(
                    title=title_text,
                    guid=f"lectulandia-{internal_id}",
                    link=f"{self.base_url}{href}" if href.startswith('/') else href,
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
            self.logger.error(f"Lectulandia browse error: {e}")

        return results[offset:]
