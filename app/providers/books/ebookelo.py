"""
Provider para ww2.ebookelo.com

Estructura del sitio:
- Búsqueda: /search/{query}/page/{n}
- Detalle:  /ebook/{id}/{slug}
- Descarga: /download/{id}/{format}  (format: epub, mobi, pdf, magnet)

IMPORTANTE — Pasos intermedios de descarga:
La página de detalle muestra DOS tipos de enlaces:
1. Enlaces SUPERIORES (trampa): Apuntan a profitablecpmgate.com (ignorar)
2. Enlaces INFERIORES (reales): Apuntan a /download/{id}/{format}
"""

from typing import Optional
from urllib.parse import quote_plus
from datetime import datetime

from bs4 import BeautifulSoup

from app.providers.base import BaseProvider
from app.core.models import SearchResult, ProviderCapabilities
from app.core.categories import CategoryMapper
from app.scraping.http_client import HttpClient


class EbookeloProvider(BaseProvider):
    """
    Provider para Ebookelo - libros en español.
    """

    provider_id = "ebookelo"
    display_name = "Ebookelo"

    PREFERRED_FORMAT_ORDER = ["epub", "mobi", "pdf"]

    def __init__(self, http_client: HttpClient, base_url: str = None, domain_resolver=None):
        if domain_resolver:
            active_domain = domain_resolver.get_current("ebookelo")
            if active_domain:
                base_url = active_domain
                
        super().__init__(
            http_client=http_client,
            provider_provider_id="ebookelo",
            display_display_name="Ebookelo",
            base_url=base_url or settings.EBOOKELO_DOMAIN,
            categories=[7000, 7020, 8000, 8010]
        )

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            display_name=self.display_name,
            supported_categories=[7000, 7020, 8000, 8010],
            supported_search_params=["q", "author", "title"],
            supports_book_search=True,
        )

    async def search(
        self,
        query: str,
        categories: list[int],
        *,
        offset: int = 0,
        limit: int = 50,
        imdb_id: Optional[str] = None,
        tvdb_id: Optional[int] = None,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        author: Optional[str] = None,
        title: Optional[str] = None,
    ) -> list[SearchResult]:

        combined_query = self._combine_query(query, author, title)
        normalized = self.normalize_query(combined_query)

        if not normalized:
            return []

        url = self._build_search_url(normalized)

        try:
            response = await self.http_client.get(url)
            results = self._parse_results(response.text)
        except Exception as e:
            self.logger.error(f"Error en búsqueda: {e}")
            return []

        # Enriquecer los top-N resultados con detalle
        enriched = []
        for result in results[:limit]:
            try:
                detail = await self._parse_book_detail(result.link)
                if detail.get("author"):
                    result.author = detail["author"]
                if detail.get("formats"):
                    # Elegir mejor formato disponible
                    fmt = self._select_best_format(detail["formats"])
                    result.download_url = f"/api/download?provider=ebookelo&id={result.guid.split('-')[1]}&fmt={fmt}"
                    result.extra_attrs["format"] = fmt
                if detail.get("genre"):
                    result.extra_attrs["genre"] = detail["genre"]
            except Exception as e:
                self.logger.warning(f"Error enriqueciendo {result.guid}: {e}")
            enriched.append(result)

        # Aplicar offset
        if offset:
            enriched = enriched[offset:]

        return enriched

    def _build_search_url(self, query: str, page: int = 1) -> str:
        return f"{self.base_url}/search/{quote_plus(query)}/page/{page}"

    def _parse_results(self, html: str) -> list[SearchResult]:
        """
        Parsea la página de resultados de búsqueda.
        Cada resultado es un <a> con href="/ebook/{id}/{slug}".
        """
        soup = BeautifulSoup(html, "lxml")
        results = []

        # Buscar todos los enlaces a libros
        for link in soup.select('a[href*="/ebook/"]'):
            href = link.get("href", "")
            parts = href.rstrip("/").split("/")
            if len(parts) < 4:
                continue

            book_id = parts[-2]
            slug = parts[-1]

            title = link.get_text(strip=True)

            if not title or not book_id.isdigit():
                continue

            result = SearchResult(
                title=title,
                guid=f"ebookelo-{book_id}",
                link=f"{self.base_url}/ebook/{book_id}/{slug}",
                download_url=f"/api/download?provider=ebookelo&id={book_id}&fmt=epub",
                size_bytes=0,
                pub_date=datetime.now(),
                categories=[7000, 7020, 8000, 8010],
                seeders=100,
                peers=100,
                extra_attrs={"booktitle": title},
            )
            results.append(result)

        # Deduplicar por GUID
        seen = set()
        unique = []
        for r in results:
            if r.guid not in seen:
                seen.add(r.guid)
                unique.append(r)

        return unique

    async def _parse_book_detail(self, url: str) -> dict:
        """
        Parsea la página de detalle de un libro.
        """
        response = await self.http_client.get(url)
        soup = BeautifulSoup(response.text, "lxml")

        detail = {}

        # Autor
        author_link = soup.select_one('a[href*="/ebooks/autor/"]')
        if author_link:
            detail["author"] = author_link.get_text(strip=True)

        # Formatos disponibles
        formats = []
        for dl_link in soup.select('a[href*="/download/"]'):
            href = dl_link.get("href", "")
            fmt = href.rstrip("/").split("/")[-1]
            if fmt in ("epub", "mobi", "pdf", "magnet"):
                formats.append(fmt)
        detail["formats"] = formats

        # Género
        genre_link = soup.select_one('a[href*="/ebooks/genero/"]')
        if genre_link:
            detail["genre"] = genre_link.get_text(strip=True)

        # Idioma
        lang_link = soup.select_one('a[href^="/ebooks/"]')
        if lang_link:
            lang_href = lang_link.get("href", "")
            if "/ebooks/" in lang_href and "/genero/" not in lang_href:
                lang = lang_href.split("/")[-1]
                detail["language"] = lang

        return detail

    def _select_best_format(self, formats: list[str]) -> str:
        """Selecciona el mejor formato disponible según preferencia."""
        for fmt in self.PREFERRED_FORMAT_ORDER:
            if fmt in formats:
                return fmt
        return formats[0] if formats else "epub"

    async def get_download_url(self, internal_id: str) -> str:
        """
        Resuelve la URL final de descarga.
        internal_id format: "{book_id}/{format}" ej: "1828/epub"
        """
        parts = internal_id.split("/", 1)
        if len(parts) == 2:
            book_id, fmt = parts
        else:
            book_id = parts[0]
            fmt = "epub"

        download_url = f"{self.base_url}/download/{book_id}/{fmt}"

        try:
            response = await self.http_client.get(
                download_url,
                follow_redirects=False,
                headers={"Referer": f"{self.base_url}/ebook/{book_id}/"}
            )

            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("Location", "")
                if "profitablecpmgate" not in location:
                    return location or download_url

            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type:
                    return download_url
                else:
                    soup = BeautifulSoup(response.text, "lxml")
                    for link in soup.select("a[href]"):
                        href = link.get("href", "")
                        if "profitablecpmgate" in href:
                            continue
                        if href.endswith(f".{fmt}") or f"/download/" in href:
                            if href.startswith("/"):
                                return f"{self.base_url}{href}"
                            return href

        except Exception as e:
            self.logger.error(f"Error resolviendo URL de descarga: {e}")

        return download_url
