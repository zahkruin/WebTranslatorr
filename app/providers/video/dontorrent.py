"""
Provider para DonTorrent (dontorrent.reisen, dominio variable).

Diferencias con MejorTorrent:
1. Comparte el mismo esquema de IDs
2. El dominio cambia semanalmente
3. La búsqueda NO tiene endpoint GET público (usa formulario JS)
4. Sirve como FALLBACK si MejorTorrent está caído
"""

import re
from typing import Optional
from datetime import datetime

from bs4 import BeautifulSoup

from app.providers.base import BaseProvider
from app.core.models import SearchResult, ProviderCapabilities
from app.core.categories import CategoryMapper
from app.scraping.http_client import HttpClient
from config import settings


class DonTorrentProvider(BaseProvider):
    """
    Provider para DonTorrent - películas y series en español (fallback).
    """

    provider_id = "dontorrent"
    display_name = "DonTorrent"

    def __init__(self, http_client: HttpClient, domain_resolver=None):
        base_url = settings.DONTORRENT_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("dontorrent")
            if active_domain:
                base_url = active_domain
                
        super().__init__(
            http_client=http_client,
            provider_id="dontorrent",
            display_name="DonTorrent",
            base_url=base_url
        )

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            display_name=self.display_name,
            supported_categories=[2000, 2030, 2040, 2045, 5000, 5030, 5040],
            supported_search_params=["q"],
            supports_tv_search=True,
            supports_movie_search=True,
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
        """
        DonTorrent no tiene búsqueda GET pública.
        Estrategia: Navegar listados recientes.
        """
        results = []

        # Determinar qué listados scrapear
        cat = categories[0] if categories else None

        if not cat or CategoryMapper.is_movie_category(cat):
            results.extend(await self._scrape_listings("/peliculas"))
            results.extend(await self._scrape_listings("/peliculas/hd"))
            results.extend(await self._scrape_listings("/peliculas/4K"))

        if not cat or CategoryMapper.is_tv_category(cat):
            results.extend(await self._scrape_listings("/series"))
            results.extend(await self._scrape_listings("/series/hd"))

        # Filtrar por query si hay uno
        if query:
            normalized = self.normalize_query(query)
            results = [
                r for r in results
                if normalized in self.normalize_query(r.title)
            ]

        # Aplicar offset y limit
        if offset:
            results = results[offset:]
        results = results[:limit]

        return results

    async def _scrape_listings(self, path: str) -> list[SearchResult]:
        """Scrapea una página de listado de DonTorrent."""
        url = f"{self.base_url}{path}"

        try:
            response = await self.http_client.get(url)
            return self._parse_results(response.text)
        except Exception as e:
            self.logger.error(f"Error scrapeando {path}: {e}")
            return []

    def _parse_results(self, html: str) -> list[SearchResult]:
        """Parsea HTML de listado."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        for link in soup.select('a[href*="/pelicula/"], a[href*="/serie/"]'):
            href = link.get("href", "")
            title = link.get_text(strip=True)

            if not title:
                continue

            match = re.search(r'/(pelicula|serie)/(\d+)/', href)
            if not match:
                continue

            content_type = match.group(1)
            item_id = match.group(2)

            categories = [2000, 2030] if content_type == "pelicula" else [5000, 5030]

            result = SearchResult(
                title=title,
                guid=f"dontorrent-{item_id}",
                link=f"{self.base_url}{href}" if href.startswith('/') else href,
                download_url="",
                size_bytes=0,
                pub_date=datetime.now(),
                categories=categories,
                seeders=50,
                peers=50,
            )
            results.append(result)

        return results

    def _build_search_url(self, query: str, page: int = 1) -> str:
        """No hay endpoint de búsqueda GET, usar listados."""
        return f"{self.base_url}/peliculas"

    async def get_download_url(self, internal_id: str) -> str:
        """El download_url ya es la URL directa."""
        return internal_id
