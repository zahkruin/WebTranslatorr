"""
Provider para ebiblioteca.org - Libros electrónicos en español.

Ebiblioteca es un sitio PHP custom con catálogo de ~177,000 títulos.
Estructura:
- Búsqueda: GET /?search={query} (probable, requiere confirmación)
- Resultados: Lista paginada tipo catálogo con vista "Detalle" o "Lista"
- Detalle: Página con sinopsis extensa, biografía del autor, botones de descarga
- Descarga: Botón → página con anuncio → "Completar e ir a la descarga" → ZIP
  El ZIP contiene EPUB + PDF + TXT. Requiere ZipExtractor.

Clase con is_zipped = True para activar extracción automática del EPUB del ZIP.
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


logger = logging.getLogger("provider.ebiblioteca")


class EbibliotecaProvider(BaseProvider):
    """
    Provider para Ebiblioteca - HTML scraping + extracción ZIP.
    La descarga devuelve un ZIP con EPUB + PDF + TXT.
    """

    is_zipped = True  # ⚡ Activa ZipExtractor en download_proxy

    def __init__(self, http_client, domain_resolver=None):
        domain = settings.EBIBLIOTECA_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("ebiblioteca")
            if active_domain:
                domain = active_domain

        super().__init__(
            provider_id="ebiblioteca",
            display_name="Ebiblioteca",
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
        self.logger.info(f"Buscando en Ebiblioteca: '{query_to_use}'")
        if not query_to_use:
            return []

        results = []
        encoded_query = quote_plus(query_to_use)

        # Ebiblioteca search URL patterns (to be confirmed with live testing)
        search_urls = [
            f"{self.base_url}/?search={encoded_query}",
            f"{self.base_url}/search?q={encoded_query}",
            f"{self.base_url}/?s={encoded_query}",
            f"{self.base_url}/buscar?q={encoded_query}",
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
            self.logger.warning("No se pudo realizar búsqueda en Ebiblioteca")
            return []

        try:
            soup = BeautifulSoup(resp.text, 'lxml')
            seen_ids = set()

            # Ebiblioteca has a catalog-style list with cards in "Detalle" view
            # or simple name list in "Lista" view

            # Try card/view styles first
            selectors = [
                'a[href*="/libro/"]',
                'a[href*="/book/"]',
                'a[href*="/descargar/"]',
                'a[href*="/read/"]',
                'a[href*="/id/"]',
                'div.card a[href]',
                'div.item a[href]',
                'div[class*="book"] a[href]',
                'div[class*="libro"] a[href]',
                'table a[href]',
                'h2 a', 'h3 a',
            ]

            for selector in selectors:
                for link in soup.select(selector):
                    href = link.get('href', '')
                    title_text = link.get_text(strip=True)

                    if not href or not title_text or len(title_text) < 3:
                        continue

                    # Skip navigation/utility links
                    if any(skip in href.lower() for skip in [
                        '/category/', '/author/', '/autor/', '/tag/',
                        '/page/', '/genero/', '/genre/', '/editorial/',
                        '/login', '/registro', '/register',
                        'javascript:', 'mailto:', '#',
                    ]):
                        continue
                    if title_text.lower() in (
                        'inicio', 'home', 'biblioteca', 'contacto',
                        'autores', 'títulos', 'titulos', 'géneros', 'generos',
                        'novedades', 'favoritos', 'leer más', 'leer mas',
                        'ir a la descarga', 'completar', 'descargar',
                    ):
                        continue

                    # Extract internal ID
                    internal_id = self._extract_internal_id(href, title_text)
                    if internal_id in seen_ids:
                        continue
                    seen_ids.add(internal_id)

                    # Normalize link
                    if href.startswith('/'):
                        link_full = f"{self.base_url}{href}"
                    elif not href.startswith('http'):
                        link_full = f"{self.base_url}/{href}"
                    else:
                        link_full = href

                    # Extract author from context
                    author_text = self._extract_author_from_context(link)

                    # Extract genre
                    genre_text = self._extract_genre_from_context(link)

                    # Extract size info
                    size_text = self._extract_size_from_context(link)
                    size_bytes = self._parse_size(size_text)

                    description_parts = [f"Libro: {title_text}"]
                    if author_text:
                        description_parts.append(f"Autor: {author_text}")
                    if genre_text:
                        description_parts.append(f"Género: {genre_text}")

                    result = SearchResult(
                        title=title_text,
                        guid=f"ebiblioteca-{internal_id}",
                        link=link_full,
                        download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={internal_id}&fmt=epub",
                        size_bytes=size_bytes or 3000000,
                        pub_date=datetime.now(),
                        categories=[7000, 7020, 8000, 8010],
                        description=" | ".join(description_parts),
                        author=author_text or None,
                        extra_attrs={"genre": genre_text} if genre_text else {},
                    )
                    results.append(result)

                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break

        except Exception as e:
            self.logger.error(f"Error parseando Ebiblioteca: {e}")

        return results[offset:]

    async def get_download_url(self, internal_id: str, **kwargs) -> str | None:
        """
        Resuelve la URL de descarga navegando la cadena de anuncios.
        El archivo final es un ZIP que contiene EPUB + PDF + TXT.
        """
        fmt = kwargs.get('fmt', 'epub').lower()

        # Reconstruct detail URL
        detail_url = f"{self.base_url}/{internal_id}"
        if internal_id.startswith('/'):
            detail_url = f"{self.base_url}{internal_id}"

        try:
            resp = await self.http_client.get(detail_url, use_scraper=True)
            soup = BeautifulSoup(resp.text, 'lxml')

            # Look for download buttons
            download_url = self._find_download_link(soup, fmt)
            if download_url:
                return download_url

            # Follow "Completar e ir a la página de descarga" chain
            for a in soup.find_all('a', href=True):
                text = a.get_text(strip=True).lower()
                href = a['href']
                if any(w in text for w in ('descargar', 'download', 'descarga', 'bajar', 'completar', 'ir a')):
                    if href.startswith('/'):
                        href = f"{self.base_url}{href}"
                    elif not href.startswith('http'):
                        href = f"{self.base_url}/{href}"

                    # Follow the redirect chain (up to 3 hops)
                    for _ in range(3):
                        try:
                            resp2 = await self.http_client.get(href, use_scraper=True)
                            soup2 = BeautifulSoup(resp2.text, 'lxml')
                            found = self._find_download_link(soup2, fmt)
                            if found:
                                return found
                            # Look for next redirect
                            next_link = None
                            for a2 in soup2.find_all('a', href=True):
                                t2 = a2.get_text(strip=True).lower()
                                if any(w in t2 for w in ('descargar', 'download', 'completar', 'continuar', 'ir a')):
                                    next_link = a2['href']
                                    break
                            if next_link:
                                if next_link.startswith('/'):
                                    href = f"{self.base_url}{next_link}"
                                elif not next_link.startswith('http'):
                                    href = f"{self.base_url}/{next_link}"
                                else:
                                    href = next_link
                            else:
                                break
                        except Exception:
                            break

        except Exception as e:
            self.logger.error(f"Error obteniendo download url de {internal_id}: {e}")

        return None

    def _find_download_link(self, soup: BeautifulSoup, fmt: str) -> str | None:
        """Find download link in parsed HTML, excluding redirect gateways."""
        # Direct format links (skip redirect gateways)
        for a in soup.find_all('a', href=True):
            href = a['href']
            if any(skip in href.lower() for skip in ('/go/', '/redir/', '/redirect/', '/ad/', '/anuncio/')):
                continue
            text = a.get_text(strip=True).lower()

            # ZIP files (most common for Ebiblioteca)
            if href.lower().endswith('.zip') or '.zip?' in href.lower():
                if href.startswith('/'):
                    return f"{self.base_url}{href}"
                return href

            # Specific format
            if href.lower().endswith(f'.{fmt}') or f'.{fmt}?' in href.lower():
                if href.startswith('/'):
                    return f"{self.base_url}{href}"
                return href

            # Download buttons
            if any(w in text for w in ('descargar', 'download', 'descarga', 'bajar')):
                if 'anuncio' not in text and 'publicidad' not in text:
                    if href.startswith('/'):
                        return f"{self.base_url}{href}"
                    return href

        # Any archive links (skip redirects)
        for a in soup.find_all('a', href=True):
            href = a['href']
            if any(skip in href.lower() for skip in ('/go/', '/redir/', '/redirect/', '/ad/', '/anuncio/')):
                continue
            if any(ext in href.lower() for ext in ('.zip', '.rar', '.epub', '.pdf', '.mobi')):
                if href.startswith('/'):
                    return f"{self.base_url}{href}"
                return href

        return None

    @staticmethod
    def _extract_internal_id(href: str, title: str) -> str:
        """Extract internal ID from URL."""
        # Try numeric ID
        num_match = re.search(r'/(?:libro|book|id|read|descargar)/(\d+)', href)
        if num_match:
            return num_match.group(1)
        # Try slug
        parts = [p for p in href.rstrip('/').split('/') if p]
        if parts:
            return parts[-1]
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        return slug or title.replace(' ', '-').lower()

    @staticmethod
    def _extract_author_from_context(link) -> str:
        """Try to extract author from parent/element context."""
        # Check parent and grandparent
        for search_elem in [link.parent, link.parent.parent if link.parent else None]:
            if not search_elem:
                continue
            for cls in ['author', 'autor', 'writer', 'escritor']:
                elem = search_elem.select_one(f'[class*="{cls}"]')
                if elem:
                    text = elem.get_text(strip=True)
                    if text and text.lower() not in ('autor:', 'author:', 'por:'):
                        return text
            # Check parent text
            parent_text = search_elem.get_text(separator='|', strip=True)
            parts = [p.strip() for p in parent_text.split('|')]
            for part in parts:
                if part and len(part) > 2 and any(c.isupper() for c in part[:3]):
                    if part != link.get_text(strip=True):
                        return part
        return ""

    @staticmethod
    def _extract_genre_from_context(link) -> str:
        """Try to extract genre from context."""
        parent = link.parent
        if parent:
            for cls in ['genre', 'genero', 'category', 'categoria', 'tag']:
                elem = parent.select_one(f'[class*="{cls}"]')
                if elem:
                    return elem.get_text(strip=True)
        return ""

    @staticmethod
    def _extract_size_from_context(link) -> str:
        """Try to extract file size from context."""
        parent = link.parent
        if parent:
            for cls in ['size', 'tamano', 'tamaño', 'filesize']:
                elem = parent.select_one(f'[class*="{cls}"]')
                if elem:
                    return elem.get_text(strip=True)
            # Look for size pattern in parent text
            parent_text = parent.get_text(strip=True)
            size_match = re.search(r'(\d+[\.,]?\d*\s*(?:KB|MB|GB|kb|mb|gb))', parent_text)
            if size_match:
                return size_match.group(1)
        return ""

    @staticmethod
    def _parse_size(size_text: str) -> int:
        """Convert size text to bytes."""
        if not size_text:
            return 0
        size_text = size_text.strip().lower()
        try:
            if 'kb' in size_text:
                return int(float(size_text.replace('kb', '').replace(',', '.').strip()) * 1024)
            elif 'mb' in size_text:
                return int(float(size_text.replace('mb', '').replace(',', '.').strip()) * 1024 * 1024)
            elif 'gb' in size_text:
                return int(float(size_text.replace('gb', '').replace(',', '.').strip()) * 1024 * 1024 * 1024)
        except ValueError:
            pass
        return 0

    async def browse(
        self,
        categories: list[int] = None,
        *,
        offset: int = 0,
        limit: int = 50,
        **kwargs
    ) -> list[SearchResult]:
        """RSS/browse mode: scrape Ebiblioteca homepage (catalog listing)."""
        from bs4 import BeautifulSoup
        from datetime import datetime

        self.logger.info(f"Ebiblioteca browse: homepage catalog (offset={offset}, limit={limit})")
        results = []
        url = f"{self.base_url}/"

        try:
            resp = await self.http_client.get(url, use_scraper=True)
            if resp.status_code != 200 or len(resp.text) < 500:
                self.logger.warning("Ebiblioteca browse: homepage returned empty/short response")
                return []

            soup = BeautifulSoup(resp.text, 'lxml')
            seen_ids = set()

            # Reuse the same comprehensive selectors from search()
            selectors = [
                'a[href*="/libro/"]',
                'a[href*="/book/"]',
                'a[href*="/descargar/"]',
                'a[href*="/read/"]',
                'a[href*="/id/"]',
                'div.card a[href]',
                'div.item a[href]',
                'div[class*="book"] a[href]',
                'div[class*="libro"] a[href]',
                'table a[href]',
                'h2 a', 'h3 a',
            ]

            for selector in selectors:
                for link in soup.select(selector):
                    href = link.get('href', '')
                    title_text = link.get_text(strip=True)
                    if not href or not title_text or len(title_text) < 3:
                        continue
                    if any(skip in href.lower() for skip in [
                        '/category/', '/author/', '/autor/', '/tag/',
                        '/page/', '/genero/', '/genre/', '/editorial/',
                        '/login', '/registro', '/register',
                        'javascript:', 'mailto:', '#',
                    ]):
                        continue
                    if title_text.lower() in (
                        'inicio', 'home', 'biblioteca', 'contacto',
                        'autores', 'títulos', 'titulos', 'géneros', 'generos',
                        'novedades', 'favoritos', 'leer más', 'leer mas',
                        'ir a la descarga', 'completar', 'descargar',
                    ):
                        continue

                    internal_id = self._extract_internal_id(href, title_text)
                    if internal_id in seen_ids:
                        continue
                    seen_ids.add(internal_id)

                    if href.startswith('/'):
                        link_full = f"{self.base_url}{href}"
                    elif not href.startswith('http'):
                        link_full = f"{self.base_url}/{href}"
                    else:
                        link_full = href

                    author_text = self._extract_author_from_context(link)
                    genre_text = self._extract_genre_from_context(link)
                    size_text = self._extract_size_from_context(link)
                    size_bytes = self._parse_size(size_text)

                    description_parts = [f"Libro: {title_text}"]
                    if author_text:
                        description_parts.append(f"Autor: {author_text}")
                    if genre_text:
                        description_parts.append(f"Género: {genre_text}")

                    result = SearchResult(
                        title=title_text,
                        guid=f"ebiblioteca-{internal_id}",
                        link=link_full,
                        download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={internal_id}&fmt=epub",
                        size_bytes=size_bytes or 3000000,
                        pub_date=datetime.now(),
                        categories=[7000, 7020, 8000, 8010],
                        description=" | ".join(description_parts),
                        author=author_text or None,
                        extra_attrs={"genre": genre_text} if genre_text else {},
                    )
                    results.append(result)
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break
        except Exception as e:
            self.logger.error(f"Ebiblioteca browse error: {e}")

        return results[offset:]
