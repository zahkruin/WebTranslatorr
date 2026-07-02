"""
Provider para BookSee (en.booksee.org) — Librería con 2.4M de títulos en inglés.

ESTRATEGIA: HTML scraping puro. BookSee no tiene Cloudflare, JS requerido, ni login.
- Búsqueda: GET /?q={query}&page=1 → resultados en tabla/lista de libros
- Detalle: GET /book/{internal_id}/ → scrape de enlace de descarga PDF
- Descarga: enlaces directos a PDF (href terminado en .pdf o atributo download)
"""

import re
import logging
from typing import Optional
from datetime import datetime

from bs4 import BeautifulSoup

from app.providers.base import BaseProvider
from app.core.models import SearchResult
from config import settings


class BookseeProvider(BaseProvider):
    """
    Provider para BookSee — HTML scraping puro sin protecciones anti-bot.
    BookSee ofrece PDFs bajo demanda o enlaces directos en la página de detalle.
    """

    def __init__(self, http_client, domain_resolver=None):
        domain = settings.BOOKSEE_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("booksee")
            if active_domain:
                domain = active_domain

        super().__init__(
            provider_id="booksee",
            display_name="BookSee",
            base_url=domain,
            http_client=http_client,
            categories=[7000, 7020, 8000, 8010],
            query_language="en",
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
        """
        Busca libros en BookSee mediante scraping HTML.

        Args:
            query: Término de búsqueda (puede combinarse con author/title).
            categories: Lista de categorías a filtrar (opcional, no se filtra a nivel provider).
            offset: Desplazamiento para paginación.
            limit: Máximo de resultados a devolver.
            author: Autor del libro (opcional, se combina con query).
            title: Título del libro (opcional, se combina con query).

        Returns:
            Lista de SearchResult (vacía si hay error).
        """
        combined_query = self._combine_query(query, author, title)
        query_to_use = self.normalize_query(combined_query)
        self.logger.info(f"Searching BookSee: '{query_to_use}'")
        if not query_to_use:
            return []

        results: list[SearchResult] = []
        search_url = f"{self.base_url}/?q={query_to_use}&page=1"

        try:
            resp = await self.http_client.get(search_url, use_scraper=False)
            soup = BeautifulSoup(resp.text, "lxml")

            # BookSee results can appear in different container patterns.
            # Try common selectors for book entries.
            book_containers = (
                soup.select("div.book-item")
                or soup.select("table.results tr")
                or soup.select("div.result-item")
                or soup.select("article.book")
                or soup.select("div[class*='book']")
            )

            seen_ids: set[str] = set()

            for container in book_containers:
                # ── Title & detail link ──
                title_elem = (
                    container.select_one("h3 a")
                    or container.select_one("h3")
                    or container.select_one("a.title")
                    or container.select_one("a[class*='title']")
                    or container.select_one("a[href*='/book/']")
                )

                if not title_elem:
                    continue

                title_text = title_elem.get_text(strip=True)
                if not title_text or len(title_text) < 3:
                    continue

                # Extract detail href from the title element or a nearby book link
                detail_href: Optional[str] = title_elem.get("href") if title_elem.name == "a" else None
                if not detail_href:
                    detail_a = container.select_one("a[href*='/book/']")
                    if detail_a:
                        detail_href = detail_a.get("href")

                if not detail_href:
                    continue

                # ── Internal ID ──
                internal_id = self._extract_internal_id(detail_href)
                if not internal_id or internal_id in seen_ids:
                    continue
                seen_ids.add(internal_id)

                # ── Author ──
                author_text: Optional[str] = None
                author_elem = (
                    container.select_one("span.author")
                    or container.select_one("[class*='author']")
                    or container.select_one("span[itemprop='author']")
                )
                if author_elem:
                    author_text = author_elem.get_text(strip=True)

                # ── Build full link ──
                if detail_href.startswith("/") and not detail_href.startswith("//"):
                    link_full = f"{self.base_url}{detail_href}"
                elif not detail_href.startswith("http"):
                    link_full = f"{self.base_url}/{detail_href}"
                else:
                    link_full = detail_href

                description = f"Book: {title_text}"
                if author_text:
                    description += f" by {author_text}"

                result = SearchResult(
                    title=title_text,
                    guid=f"booksee-{internal_id}",
                    link=link_full,
                    download_url=(
                        f"{settings.EXTERNAL_URL}/api/download"
                        f"?provider={self.provider_id}&id={internal_id}&fmt=pdf"
                    ),
                    size_bytes=2000000,
                    pub_date=datetime.now(),
                    categories=[7000, 7020, 8000, 8010],
                    description=description,
                    author=author_text,
                )
                results.append(result)

                if len(results) >= limit:
                    break

        except Exception as e:
            self.logger.error(f"Error parsing BookSee search results: {e}")

        return results[offset:]

    async def get_download_url(self, internal_id: str, **kwargs) -> str | None:
        """
        Resuelve la URL de descarga PDF scrapeando la página de detalle.

        Args:
            internal_id: ID interno del libro (slug o ID numérico).

        Returns:
            URL de descarga directa o None si no se encuentra o hay error.
        """
        detail_url = f"{self.base_url}/book/{internal_id}/"

        try:
            resp = await self.http_client.get(detail_url, use_scraper=False)
            soup = BeautifulSoup(resp.text, "lxml")

            # Strategy 1: <a> elements with download attribute
            for a in soup.find_all("a", href=True, download=True):
                href = a["href"]
                if href.startswith("/") and not href.startswith("//"):
                    return f"{self.base_url}{href}"
                if href.startswith("http"):
                    return href

            # Strategy 2: links ending in .pdf
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if ".pdf" in href.lower():
                    if href.startswith("/") and not href.startswith("//"):
                        return f"{self.base_url}{href}"
                    if href.startswith("http"):
                        return href

            # Strategy 3: links with download/pdf in visible text
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True).lower()
                if any(w in text for w in ("download", "pdf", "get", "read")):
                    href = a["href"]
                    if any(skip in href.lower() for skip in ("/book/", "/author/", "/category/")):
                        continue
                    if href.startswith("/") and not href.startswith("//"):
                        return f"{self.base_url}{href}"
                    if href.startswith("http"):
                        return href

            self.logger.warning(
                f"No download link found for BookSee book {internal_id}"
            )
        except Exception as e:
            self.logger.error(
                f"Error getting download URL for BookSee book {internal_id}: {e}"
            )

        return None

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _extract_internal_id(href: str) -> str | None:
        """
        Extrae el ID interno de un libro desde la URL de detalle.

        Espera patrones como /book/{slug}/ o /book/{id}/.
        """
        # Pattern: /book/{id}/  or  /book/{id}
        match = re.search(r"/book/([^/?#]+)", href)
        if match:
            return match.group(1)

        # Fallback: last path segment
        parts = [p for p in href.rstrip("/").split("/") if p and p != "book"]
        if parts:
            return parts[-1]

        return None

    # ── RSS / Browse mode ────────────────────────────────────────────────

    async def browse(
        self,
        categories: list[int] = None,
        *,
        offset: int = 0,
        limit: int = 50,
        **kwargs
    ) -> list[SearchResult]:
        """
        Modo RSS/browse: devuelve libros recientes desde la homepage.
        Útil cuando Readarr/etc hacen sync sin query de búsqueda (t=book sin q=).
        """
        self.logger.info(
            f"BookSee browse: homepage (offset={offset}, limit={limit})"
        )
        results: list[SearchResult] = []
        url = f"{self.base_url}/"

        try:
            resp = await self.http_client.get(url, use_scraper=False)
            soup = BeautifulSoup(resp.text, "lxml")

            seen_ids: set[str] = set()
            for a in soup.select("a[href*='/book/']"):
                href = a.get("href")
                title_text = a.get_text(strip=True)
                if not href or not title_text or len(title_text) < 3:
                    continue
                # Skip utility/navigation links
                if any(
                    skip in href.lower()
                    for skip in ("/category/", "/author/", "/tag/", "/page/")
                ):
                    continue

                internal_id = self._extract_internal_id(href)
                if not internal_id or internal_id in seen_ids:
                    continue
                seen_ids.add(internal_id)

                link_full = (
                    href if href.startswith("http")
                    else f"{self.base_url}{href}"
                )

                result = SearchResult(
                    title=title_text,
                    guid=f"booksee-{internal_id}",
                    link=link_full,
                    download_url=(
                        f"{settings.EXTERNAL_URL}/api/download"
                        f"?provider={self.provider_id}&id={internal_id}&fmt=pdf"
                    ),
                    size_bytes=2000000,
                    pub_date=datetime.now(),
                    categories=[7000, 7020, 8000, 8010],
                    description=f"Book: {title_text}",
                )
                results.append(result)

                if len(results) >= limit:
                    break
        except Exception as e:
            self.logger.error(f"BookSee browse error: {e}")

        return results[offset:]
