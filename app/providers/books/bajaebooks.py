"""
Provider para bajaebooks.info / bajaebooks.com - Libros electrónicos.

Bajaebooks es un sitio HTML estático con catálogo de ~31,000 títulos.
Estructura:
- Búsqueda: GET /?s={query}
- Resultados: Cards con portada, título, autor, género
- Detalle: Página con sinopsis, portada, botón azul de descarga
- Descarga: Click en botón → popup con anuncio → redirección a página de descarga

Nota: bajaebooks.info tiene HTTPS. bajaebooks.com es HTTP solamente.
Este provider prefiere .info y solo usa .com como fallback.
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


logger = logging.getLogger("provider.bajaebooks")


class BajaebooksProvider(BaseProvider):
    """
    Provider para Bajaebooks - HTML scraping con redirección de descarga.
    """

    _FALLBACK_DOMAIN = "https://bajaebooks.com"

    def __init__(self, http_client, domain_resolver=None):
        domain = settings.BAJAEEBOOKS_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("bajaebooks")
            if active_domain:
                domain = active_domain

        super().__init__(
            provider_id="bajaebooks",
            display_name="Bajaebooks",
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
        self.logger.info(f"Buscando en Bajaebooks: '{query_to_use}'")
        if not query_to_use:
            return []

        # Try primary domain first, then fallback
        for domain in [self.base_url, self._FALLBACK_DOMAIN]:
            try:
                results = await self._do_search(query_to_use, offset, limit, domain)
                if results:
                    return results
            except Exception:
                continue

        return []

    async def _do_search(
        self, query_to_use: str, offset: int, limit: int, domain: str
    ) -> list[SearchResult]:
        results = []
        encoded_query = quote_plus(query_to_use)

        # Try multiple search URL patterns
        search_urls = [
            f"{domain}/?s={encoded_query}",
            f"{domain}/search?q={encoded_query}",
            f"{domain}/buscar?q={encoded_query}",
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
            self.logger.debug(f"No response from {domain}")
            return []

        try:
            soup = BeautifulSoup(resp.text, 'lxml')
            seen_urls = set()

            # Bajaebooks card-based layout. Try multiple selectors.
            selectors = [
                'a[href*="/libro/"]',
                'a[href*="/book/"]',
                'a[href*="/descargar/"]',
                'article a[href]',
                'div.book-card a[href]',
                'div.item a[href]',
                'h2 a', 'h3 a',
                '.entry-title a',
                'a[title]',
            ]

            for selector in selectors:
                for link in soup.select(selector):
                    href = link.get('href', '')
                    title_text = link.get('title') or link.get_text(strip=True)

                    if not href or not title_text or len(title_text) < 3:
                        continue

                    # Skip non-book links
                    if any(skip in href.lower() for skip in [
                        '/category/', '/autor/', '/author/', '/tag/',
                        '/page/', '/genero/', '/genre/', '/editorial/',
                        'wp-content', 'wp-admin', 'facebook', 'twitter',
                        'javascript:', 'mailto:',
                    ]):
                        continue
                    if title_text.lower() in (
                        'inicio', 'home', 'leer más', 'leer mas',
                        'biblioteca', 'contacto', 'categorías',
                        'últimos agregados', 'ultimos agregados',
                        'más leídos', 'mas leidos',
                    ):
                        continue

                    if href in seen_urls:
                        continue
                    seen_urls.add(href)

                    # Normalize link
                    if href.startswith('/'):
                        link_full = f"{domain}{href}"
                    elif not href.startswith('http'):
                        link_full = f"{domain}/{href}"
                    else:
                        link_full = href

                    # Extract internal ID
                    internal_id = self._extract_internal_id(href, title_text)

                    # Extract author from parent element context
                    author_text = self._extract_author_from_parent(link)

                    result = SearchResult(
                        title=title_text,
                        guid=f"bajaebooks-{internal_id}",
                        link=link_full,
                        download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={internal_id}&fmt=epub",
                        size_bytes=1500000,
                        pub_date=datetime.now(),
                        categories=[7020],
                        description=f"Libro: {title_text}" + (f" | Autor: {author_text}" if author_text else ""),
                        author=author_text or None,
                    )
                    results.append(result)

                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break

        except Exception as e:
            self.logger.error(f"Error parseando Bajaebooks: {e}")

        return results[offset:]

    async def get_download_url(self, internal_id: str, **kwargs) -> str | None:
        """
        Resuelve la URL de descarga siguiendo la cadena de redirección.
        Botón azul → popup con anuncio → página de descarga real.
        """
        fmt = kwargs.get('fmt', 'epub').lower()

        # Try both domains for detail page
        for domain in [self.base_url, self._FALLBACK_DOMAIN]:
            detail_url = f"{domain}/{internal_id}"
            if not internal_id.startswith('/'):
                detail_url = f"{domain}/{internal_id}"

            try:
                resp = await self.http_client.get(detail_url, use_scraper=True)
                soup = BeautifulSoup(resp.text, 'lxml')

                # Look for download button/links
                download_url = self._find_download_link(soup, fmt, domain)
                if download_url:
                    return download_url

                # If no direct link found, try following redirect chain
                # Look for buttons that lead to download pages
                for a in soup.find_all('a', href=True):
                    text = a.get_text(strip=True).lower()
                    href = a['href']
                    if any(w in text for w in ('descargar', 'download', 'descarga', 'enlace', 'link')):
                        if 'anuncio' not in text and 'publicidad' not in text:
                            redirect_url = href
                            if redirect_url.startswith('/'):
                                redirect_url = f"{domain}{redirect_url}"
                            elif not redirect_url.startswith('http'):
                                redirect_url = f"{domain}/{redirect_url}"
                            # Follow redirect
                            try:
                                resp2 = await self.http_client.get(redirect_url, use_scraper=True)
                                soup2 = BeautifulSoup(resp2.text, 'lxml')
                                final_url = self._find_download_link(soup2, fmt, domain)
                                if final_url:
                                    return final_url
                            except Exception:
                                continue

                # Look for popup/advertisement redirect patterns
                for btn in soup.select('a.btn, button.btn, a.button, button.button'):
                    onclick = btn.get('onclick', '')
                    href = btn.get('href', '')
                    if href and not href.startswith('#'):
                        if href.startswith('/'):
                            href = f"{domain}{href}"
                        return href

            except Exception as e:
                self.logger.debug(f"Error con {detail_url}: {e}")
                continue

        return None

    def _find_download_link(self, soup: BeautifulSoup, fmt: str, domain: str) -> str | None:
        """Find download link in parsed HTML, excluding redirect gateways."""
        for a in soup.find_all('a', href=True):
            href = a['href']
            if any(skip in href.lower() for skip in ('/go/', '/redir/', '/redirect/', '/ad/', '/anuncio/')):
                continue
            text = a.get_text(strip=True).lower()

            # Direct format links
            if href.lower().endswith(f'.{fmt}') or f'.{fmt}?' in href.lower():
                if href.startswith('/'):
                    return f"{domain}{href}"
                return href

            # Download button text
            if any(w in text for w in ('descargar', 'download', 'descarga', 'bajar')):
                if href.startswith('/'):
                    return f"{domain}{href}"
                return href

        # Look for any link that could be a download (skip redirects)
        for a in soup.find_all('a', href=True):
            href = a['href']
            if any(skip in href.lower() for skip in ('/go/', '/redir/', '/redirect/', '/ad/', '/anuncio/')):
                continue
            if any(ext in href.lower() for ext in ('.epub', '.pdf', '.mobi', '.zip', '.rar')):
                if href.startswith('/'):
                    return f"{domain}{href}"
                return href

        return None

    @staticmethod
    def _extract_internal_id(href: str, title: str) -> str:
        """Extract internal ID from URL."""
        parts = [p for p in href.rstrip('/').split('/') if p]
        if parts:
            return parts[-1]
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        return slug or title.replace(' ', '-').lower()

    @staticmethod
    def _extract_author_from_parent(link) -> str:
        """Try to extract author name from parent element context."""
        parent = link.parent
        if parent:
            # Look for author span/div nearby
            for cls in ['author', 'autor', 'writer']:
                elem = parent.select_one(f'[class*="{cls}"]')
                if elem:
                    return elem.get_text(strip=True)
            # Check siblings
            for sibling in parent.find_all(['span', 'div', 'small', 'p']):
                text = sibling.get_text(strip=True)
                if text and len(text) > 2 and any(c.isupper() for c in text[:3]):
                    return text
        return ""
