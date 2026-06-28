"""
Provider para epubgratis.org - Libros electrónicos en español.

HÍBRIDO: Usa WordPress REST API para búsqueda (rápido, estructurado).
Si la API no devuelve resultados, fallback a scraping HTML.

Epubgratis es un WordPress con tema personalizado y plugin epub-directory.
Estructura:
- WP REST API: /wp-json/wp/v2/posts?search={query}&per_page=20&_embed
- Búsqueda HTML: /?s={query}
- Detalle: Página individual del post con sinopsis, metadatos, enlaces de descarga
- Descarga: Enlaces públicos (sin registro) y privados (requieren login)
  Solo se usan enlaces públicos. Redirección con espera + botón "CONTINUAR".

Similar a Epubflix1Provider pero con URL base y domain_id propios.
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


logger = logging.getLogger("provider.epubgratis")


class EpubgratisProvider(BaseProvider):
    """
    Provider para Epubgratis - WordPress híbrido API + HTML scraping.
    Mismo patrón que Epubflix1Provider y LectuEpubLibre5Provider.
    """

    _USE_API = True
    _API_PER_PAGE = 20

    def __init__(self, http_client, domain_resolver=None):
        domain = settings.EPUBGRATIS_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("epubgratis")
            if active_domain:
                domain = active_domain

        super().__init__(
            provider_id="epubgratis",
            display_name="Epubgratis",
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
        self.logger.info(f"Buscando en Epubgratis: '{query_to_use}'")
        if not query_to_use:
            return []

        # ── Strategy 1: WordPress REST API ──
        if self._USE_API:
            try:
                # Try both standard posts and custom post type epub_directory
                api_results = await self._api.search(
                    query_to_use, limit=limit, offset=offset
                )
                if api_results:
                    self.logger.info(
                        f"Epubgratis API: {len(api_results)} results for '{query_to_use}'"
                    )
                    return api_results
            except Exception as e:
                self.logger.warning(f"Epubgratis API fallback: {e}")

        # ── Strategy 2: HTML scraping (fallback) ──
        self.logger.info(f"Epubgratis: falling back to HTML scraping for '{query_to_use}'")
        return await self._search_scrape(query_to_use, offset, limit)

    async def _search_scrape(
        self, query_to_use: str, offset: int, limit: int
    ) -> list[SearchResult]:
        """HTML scraping fallback."""
        results = []
        search_url = f"{self.base_url}/?s={query_to_use}"

        try:
            resp = await self.http_client.get(search_url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')

            seen_urls = set()

            # Epubgratis uses custom post type epub_directory
            # Look for various book link patterns
            selectors = [
                'a[href*="/epub-directory/"]',
                'a[href*="/epub_directory/"]',
                'a[href*="/libro/"]',
                'a[href*="/book/"]',
                'a[href*="/descargar/"]',
                'article a[href]',
                'h2.entry-title a', 'h3.entry-title a',
                'div.card a[href]',
                '.book-item a[href]',
            ]

            for selector in selectors:
                for a in soup.select(selector):
                    href = a.get('href')
                    title_text = a.get_text(strip=True)

                    if not href or not title_text or len(title_text) < 3:
                        continue

                    if href in seen_urls:
                        continue
                    seen_urls.add(href)

                    # Skip utility links
                    if any(skip in href.lower() for skip in [
                        '/category/', '/author/', '/autor/', '/tag/',
                        '/page/', '/genero/', '/genre/',
                        'wp-content', 'wp-admin', 'wp-login',
                        'facebook', 'twitter', 'instagram',
                        'javascript:', '#comment', '#respond',
                    ]):
                        continue
                    if title_text.lower() in (
                        'inicio', 'home', 'leer más', 'leer mas',
                        'biblioteca', 'contacto', 'buscar',
                        'registro', 'login', 'entrar',
                        'colecciones', 'autores', 'géneros',
                    ):
                        continue

                    # Extract internal ID
                    internal_id = self._extract_internal_id(href, title_text)

                    # Normalize link
                    if href.startswith('/'):
                        link_full = f"{self.base_url}{href}"
                    elif not href.startswith('http'):
                        link_full = f"{self.base_url}/{href}"
                    else:
                        link_full = href

                    result = SearchResult(
                        title=title_text,
                        guid=f"epubgratis-{internal_id}",
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
            self.logger.error(f"Error parseando Epubgratis: {e}")

        return results[offset:]

    async def get_download_url(self, internal_id: str, **kwargs) -> str | None:
        """
        Resuelve la URL de descarga para un libro de Epubgratis.
        Solo usa enlaces públicos (evita enlaces privados que requieren login).
        Maneja el patrón de redirección con espera + botón "CONTINUAR".
        """
        fmt = kwargs.get('fmt', 'epub').lower()

        # Try different URL patterns for detail page
        path_prefixes = ['/', '/libro/', '/epub-directory/',
                         '/epub_directory/', '/descargar/']

        for prefix in path_prefixes:
            if prefix == '/':
                detail_url = f"{self.base_url}/{internal_id}"
            else:
                detail_url = f"{self.base_url.rstrip('/')}{prefix}{internal_id}/"

            try:
                resp = await self.http_client.get(detail_url, use_scraper=True)
                soup = BeautifulSoup(resp.text, 'lxml')

                # Look for download links, skipping login-required ones
                download_url = self._find_public_download(soup, fmt)
                if download_url:
                    return download_url

                # Look for "hacer click para mostrar" toggle pattern
                toggle = soup.select_one('[class*="toggle"], [class*="show"], [class*="reveal"], [class*="mostrar"]')
                if toggle:
                    # Check links inside toggle
                    for a in toggle.find_all('a', href=True):
                        href = a['href']
                        if not any(skip in href.lower() for skip in ('login', 'registro', 'register', 'mi-cuenta')):
                            if href.startswith('/'):
                                return f"{self.base_url}{href}"
                            return href

            except Exception as e:
                self.logger.debug(f"Error con {detail_url}: {e}")
                continue

        return None

    def _find_public_download(self, soup: BeautifulSoup, fmt: str) -> str | None:
        """Find public download link (skipping login-required ones)."""
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True).lower()

            # Skip login-required links
            if any(skip in href.lower() for skip in (
                'login', 'registro', 'register', 'wp-login',
                'mi-cuenta', 'my-account', 'private', 'privado',
            )):
                continue
            if any(skip in text for skip in (
                'registro', 'login', 'privado', 'private',
                'iniciar sesión', 'registrarse',
            )):
                continue

            # Direct format links
            if href.lower().endswith(f'.{fmt}') or f'.{fmt}?' in href.lower():
                if href.startswith('/'):
                    return f"{self.base_url}{href}"
                return href

            # Download button text
            if any(w in text for w in ('descargar', 'download', 'descarga',
                                        'continuar', 'enlace', 'link',
                                        'epub', 'pdf', 'mobi')):
                if href.startswith('/') and not href.startswith('//'):
                    return f"{self.base_url}{href}"
                if href.startswith('http'):
                    return href

        # Broad search for any file link
        for a in soup.find_all('a', href=True):
            href = a['href']
            if any(ext in href.lower() for ext in ('.epub', '.pdf', '.mobi', '.zip')):
                if not any(skip in href.lower() for skip in ('login', 'registro', 'register')):
                    if href.startswith('/'):
                        return f"{self.base_url}{href}"
                    return href

        return None

    @staticmethod
    def _extract_internal_id(href: str, title: str) -> str:
        """Extract internal ID from URL."""
        # Try WordPress post ID from URL
        num_match = re.search(r'[?&]p=(\d+)', href)
        if num_match:
            return num_match.group(1)

        # Try numeric ID from path
        num_match = re.search(r'/(\d+)/?$', href.rstrip('/'))
        if num_match:
            return num_match.group(1)

        # Try slug
        parts = [p for p in href.rstrip('/').split('/') if p]
        if parts:
            return parts[-1]

        # Fallback
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        return slug or title.replace(' ', '-').lower()
