"""
Provider para OceanOfPDF (oceanofpdf.com) - Libros en inglés.

HÍBRIDO: Intenta WordPress REST API primero para búsqueda estructurada.
Si la API no está expuesta o no devuelve resultados, fallback a scraping HTML
de los resultados de búsqueda estándar de WordPress.

OceanOfPDF es un sitio WordPress estándar. Sin Cloudflare, sin JS requerido,
sin login. Enlaces de descarga directa en páginas de detalle.

Estructura:
- WP REST API:   /wp-json/wp/v2/posts?search={query}
- Búsqueda HTML: /?s={query}
- Detalle:       /{post-slug}/
- Descarga:      Enlaces directos a PDF/EPUB/MOBI en páginas de detalle
"""

import json
import re
import logging
from typing import Optional
from datetime import datetime

from bs4 import BeautifulSoup

from app.providers.base import BaseProvider
from app.core.models import SearchResult
from app.scraping.wp_api_client import WordPressApiClient
from config import settings


logger = logging.getLogger("provider.oceanofpdf")


class OceanOfPDFProvider(BaseProvider):
    """
    Provider para OceanOfPDF - WordPress híbrido API + HTML scraping.

    OceanOfPDF es un repositorio de libros en inglés con estructura WordPress
    estándar. La REST API puede o no estar expuesta, por lo que se implementa
    un fallback robusto a scraping HTML.
    """

    _USE_API = True
    _API_PER_PAGE = 20

    def __init__(self, http_client, domain_resolver=None):
        domain = settings.OCEANOFPDF_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("oceanofpdf")
            if active_domain:
                domain = active_domain

        super().__init__(
            provider_id="oceanofpdf",
            display_name="OceanOfPDF",
            base_url=domain,
            http_client=http_client,
            categories=[7000, 7020, 8000, 8010],
            query_language="en",
        )

        # WordPress REST API client (try API first, fall back to scraping)
        self._api = WordPressApiClient(
            http_client=http_client,
            base_url=domain,
            provider_id=self.provider_id,
            requires_scraper=False,  # No Cloudflare
            per_page=self._API_PER_PAGE,
        )

    # ── search ──────────────────────────────────────────────────────

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
        self.logger.info(f"Buscando en OceanOfPDF: '{query_to_use}'")
        if not query_to_use:
            return []

        # ── Strategy 1: WordPress REST API ──
        if self._USE_API:
            try:
                api_results = await self._api.search(
                    query_to_use, limit=limit, offset=offset
                )
                if api_results:
                    self.logger.info(
                        f"OceanOfPDF API: {len(api_results)} results for '{query_to_use}'"
                    )
                    return api_results
            except Exception as e:
                self.logger.warning(f"OceanOfPDF API fallback: {e}")

        # ── Strategy 2: HTML scraping (fallback) ──
        self.logger.info(
            f"OceanOfPDF: falling back to HTML scraping for '{query_to_use}'"
        )
        return await self._search_scrape(query_to_use, offset, limit)

    async def _search_scrape(
        self, query_to_use: str, offset: int, limit: int
    ) -> list[SearchResult]:
        """HTML scraping fallback — parsea resultados de búsqueda WordPress."""

        results: list[SearchResult] = []
        search_url = f"{self.base_url}/?s={query_to_use}"

        try:
            resp = await self.http_client.get(search_url, use_scraper=False)
            soup = BeautifulSoup(resp.text, "lxml")

            seen_urls: set[str] = set()

            # Standard WordPress selectors for post entries
            for a in soup.select(
                "article.post h2.entry-title a, "
                "article.type-post h2.entry-title a, "
                "article.post .entry-title a, "
                "h2.entry-title a, h3.entry-title a, "
                "a[rel='bookmark']"
            ):
                href = a.get("href")
                if not href:
                    continue

                title_text = a.get_text(strip=True)
                if not title_text or len(title_text) < 3:
                    continue

                if href in seen_urls:
                    continue
                seen_urls.add(href)

                # Skip utility / non-book links
                if any(skip in href.lower() for skip in (
                    "/category/", "/tag/", "/author/", "/page/",
                    "wp-content", "wp-admin", "wp-login",
                    "facebook", "twitter", "instagram",
                    "javascript:", "#comment", "#respond",
                )):
                    continue
                if title_text.lower() in (
                    "home", "inicio", "read more", "leer más",
                    "contact", "contacto", "about", "privacy policy",
                ):
                    continue

                # Build normalized link
                if href.startswith("/"):
                    link_full = f"{self.base_url}{href}"
                elif not href.startswith("http"):
                    link_full = f"{self.base_url}/{href}"
                else:
                    link_full = href

                # Extract internal ID (slug from URL)
                internal_id = self._extract_internal_id(href, title_text)

                # Try to extract author from nearby meta / article container
                book_author: Optional[str] = None
                parent = a.find_parent("article") or a.find_parent("div")
                if parent:
                    book_author = self._extract_author_from_meta(parent)

                if not book_author:
                    # Fallback: try "| Author" or "by Author" pattern in title
                    book_author = self._extract_author_from_title(title_text)

                # Clean author out of title display (regardless of where author was found)
                clean_title = self._clean_title(title_text)
                if clean_title:
                    title_text = clean_title

                description_parts = [f"Book: {title_text}"]
                if book_author:
                    description_parts.append(f"by {book_author}")

                result = SearchResult(
                    title=title_text,
                    guid=f"oceanofpdf-{internal_id}",
                    link=link_full,
                    download_url=(
                        f"{settings.EXTERNAL_URL}/api/download"
                        f"?provider={self.provider_id}"
                        f"&id={internal_id}"
                        f"&fmt=epub"
                    ),
                    size_bytes=2000000,
                    pub_date=datetime.now(),
                    categories=[7000, 7020, 8000, 8010],
                    description=" | ".join(description_parts),
                    author=book_author,
                )
                results.append(result)

                if len(results) >= limit:
                    break

        except Exception as e:
            self.logger.error(f"Error parseando OceanOfPDF: {e}")

        return results[offset:]

    # ── download URL ────────────────────────────────────────────────

    async def get_download_url(self, internal_id: str, **kwargs) -> Optional[str]:
        """
        Resuelve la URL de descarga escrapeando la página de detalle.

        internal_id puede ser un slug (del scraping HTML) o un ID numérico
        (de la REST API). Prueba múltiples patrones de URL para dar con la
        página correcta.
        """
        fmt = kwargs.get("fmt", "epub").lower()

        # Build candidate detail-page URLs
        candidates: list[str] = []

        if internal_id.isdigit():
            # Numeric post ID from WP API — try ?p= pattern and resolve slug
            candidates.append(f"{self.base_url}/?p={internal_id}")
            # Also try to resolve the slug via WP API
            try:
                api_url = f"{self.base_url}/wp-json/wp/v2/posts/{internal_id}"
                api_resp = await self.http_client.get(api_url, use_scraper=False)
                post = json.loads(api_resp.text) if isinstance(api_resp.text, str) else {}
                slug = post.get("slug", "")
                if slug:
                    candidates.insert(0, f"{self.base_url}/{slug}/")
            except Exception:
                pass

        # Always try slug-based URL
        candidates.append(f"{self.base_url}/{internal_id}/")
        candidates.append(f"{self.base_url}/{internal_id}")

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_candidates: list[str] = []
        for url in candidates:
            if url not in seen:
                seen.add(url)
                unique_candidates.append(url)

        for detail_url in unique_candidates:
            try:
                resp = await self.http_client.get(detail_url, use_scraper=False)
                if resp.status_code == 404:
                    continue

                soup = BeautifulSoup(resp.text, "lxml")

                download_url = self._find_download_link(soup, fmt)
                if download_url:
                    return download_url

            except Exception as e:
                self.logger.debug(f"Error con {detail_url}: {e}")
                continue

        self.logger.warning(
            f"No se encontró enlace de descarga para {internal_id}"
        )
        return None

    def _find_download_link(self, soup: BeautifulSoup, fmt: str) -> Optional[str]:
        """
        Busca un enlace de descarga en la página de detalle.

        Estrategias (en orden):
        1. Enlaces directos a archivos (.pdf, .epub, .mobi)
        2. Botones con texto "Download" / "Descargar"
        3. Cualquier enlace que contenga "download" en el href
        """

        # Strategy 1: Direct file extensions
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if any(
                href.lower().endswith(ext)
                for ext in (".epub", ".pdf", ".mobi", ".azw3", ".fb2")
            ):
                if href.startswith("/"):
                    return f"{self.base_url}{href}"
                if href.startswith("http"):
                    return href

        # Strategy 2: Download buttons by text
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True).lower()
            href = a["href"]
            if any(
                word in text
                for word in ("download", "descargar", "descarga",
                             "epub", "pdf", "mobi", "get book",
                             "free download")
            ):
                # Skip links that are clearly navigation
                if any(skip in href.lower() for skip in (
                    "wp-login", "register", "login", "comment",
                )):
                    continue
                if href.startswith("/"):
                    return f"{self.base_url}{href}"
                if href.startswith("http"):
                    return href

        # Strategy 3: Any link with "download" in the href
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "download" in href.lower() or "descargar" in href.lower():
                if href.startswith("/"):
                    return f"{self.base_url}{href}"
                if href.startswith("http"):
                    return href

        return None

    # ── browse (RSS / recent) ──────────────────────────────────────

    async def browse(
        self,
        categories: list[int] = None,
        *,
        offset: int = 0,
        limit: int = 50,
        **kwargs
    ) -> list[SearchResult]:
        """RSS/browse mode: return most recent books via WordPress API."""
        self.logger.info(
            f"OceanOfPDF browse: recent posts (offset={offset}, limit={limit})"
        )
        try:
            return await self._api.list_recent(limit=limit, offset=offset)
        except Exception as e:
            self.logger.warning(f"OceanOfPDF browse API error: {e}")
            return []

    # ── static helpers ─────────────────────────────────────────────

    @staticmethod
    def _extract_internal_id(href: str, title: str) -> str:
        """Extrae el ID interno (slug) de una URL de post WordPress."""

        # Try numeric post ID from query param
        num_match = re.search(r"[?&]p=(\d+)", href)
        if num_match:
            return num_match.group(1)

        # Try numeric ID from path
        num_match = re.search(r"/(\d+)/?$", href.rstrip("/"))
        if num_match:
            return num_match.group(1)

        # Extract slug from path (last meaningful segment)
        path = href.rstrip("/").split("/")[-1]
        # Remove any query string or fragment
        path = re.sub(r"[?#].*$", "", path)
        if path and path not in ("index.php", "wp-admin", "wp-content"):
            return path

        # Fallback: slugify the title
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        return slug or title.replace(" ", "-").lower()

    @staticmethod
    def _extract_author_from_meta(parent_elem) -> Optional[str]:
        """
        Extrae el autor desde metadatos de WordPress.

        Busca patrones como:
        - <span class="entry-author">Author Name</span>
        - <span class="byline">by Author Name</span>
        - <a class="url fn" ...>Author Name</a>
        - "by Author Name" in entry-meta text
        """
        # Entry-author span
        author_span = parent_elem.select_one(
            ".entry-author, .author, .byline .author, "
            "span.author, a.url.fn"
        )
        if author_span:
            author_text = author_span.get_text(strip=True)
            if author_text and len(author_text) > 1:
                return author_text

        # Entry-meta full text — look for "by X" pattern
        meta_div = parent_elem.select_one(".entry-meta, .post-meta")
        if meta_div:
            meta_text = meta_div.get_text(strip=True)
            # "by Author Name", "By Author Name", "por Author Name"
            by_match = re.search(
                r"(?:by|By|por|Por)\s+([A-Z][\w\s.'\-]+?)(?:\s*(?:on|en|,|$|\.))",
                meta_text
            )
            if by_match:
                return by_match.group(1).strip()

        return None

    @staticmethod
    def _extract_author_from_title(title_text: str) -> Optional[str]:
        """
        Intenta extraer el autor desde el título.

        Patrones: "Title | Author", "Title by Author"
        """
        if " | " in title_text:
            parts = title_text.rsplit(" | ", 1)
            if len(parts) > 1:
                candidate = parts[1].strip()
                if candidate and candidate[0].isupper():
                    return candidate

        if " – " in title_text:
            parts = title_text.rsplit(" – ", 1)
            if len(parts) > 1:
                candidate = parts[1].strip()
                if candidate and candidate[0].isupper():
                    return candidate

        if " — " in title_text:
            parts = title_text.rsplit(" — ", 1)
            if len(parts) > 1:
                candidate = parts[1].strip()
                if candidate and candidate[0].isupper():
                    return candidate

        # "Title by Author"
        by_match = re.search(r"\s+by\s+([A-Z][\w\s.'\-]+?)$", title_text)
        if by_match:
            return by_match.group(1).strip()

        return None

    @staticmethod
    def _clean_title(title_text: str) -> Optional[str]:
        """
        Elimina el autor del título si está en formato 'Title | Author'
        o 'Title by Author', devolviendo solo el título.
        """
        if " | " in title_text:
            parts = title_text.rsplit(" | ", 1)
            if len(parts) > 1:
                return parts[0].strip()

        if " – " in title_text:
            parts = title_text.rsplit(" – ", 1)
            if len(parts) > 1:
                return parts[0].strip()

        if " — " in title_text:
            parts = title_text.rsplit(" — ", 1)
            if len(parts) > 1:
                return parts[0].strip()

        by_match = re.search(r"\s+by\s+[A-Z][\w\s.'\-]+?$", title_text)
        if by_match:
            return title_text[:by_match.start()].strip()

        return None
