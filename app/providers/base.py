"""
Clase base abstracta para todos los scrapers/providers.

Contrato:
- Cada provider DEBE implementar: search(), get_download_url(), get_capabilities()
- Cada provider PUEDE sobrescribir: is_healthy(), normalize_query()
- El provider NO conoce el formato Torznab; solo devuelve SearchResult
"""

from abc import ABC, abstractmethod
from typing import Optional
import logging
import re

from app.core.models import SearchResult, ProviderCapabilities
from app.scraping.http_client import HttpClient


class BaseProvider(ABC):
    """
    Clase base abstracta para todos los providers.
    """

    def __init__(self, http_client: HttpClient, provider_id: str = None, display_name: str = None, base_url: str = None, categories: list[int] = None, **kwargs):
        self.http_client = http_client
        self.provider_id = provider_id or self.__class__.__name__.lower()
        self.display_name = display_name or self.__class__.__name__
        self.base_url = base_url or ""
        self.categories = categories or [7000, 7020, 8000, 8010]
        self.logger = logging.getLogger(f"provider.{self.provider_id}")

    def get_capabilities(self) -> ProviderCapabilities:
        """Declara qué categorías y parámetros soporta este provider."""
        return ProviderCapabilities(
            provider_id=self.provider_id,
            display_name=self.display_name,
            supported_categories=self.categories,
            supported_search_params=["q"],
            supports_movie_search=False,
            supports_tv_search=False,
            supports_book_search=True
        )

    @abstractmethod
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
    ):
        """
        Busca contenido. Devuelve lista.
        """
        ...

    @abstractmethod
    async def get_download_url(self, internal_id: str) -> str:
        """
        Dado un ID interno (ej: '1828/epub'), resuelve la URL final
        de descarga directa del archivo.
        """
        ...

    async def is_healthy(self) -> bool:
        """Verifica que el provider esté operativo."""
        try:
            resp = await self.http_client.get(self.base_url)
            return resp.status_code == 200
        except Exception:
            return False

    def normalize_query(self, raw_query: str) -> str:
        """Limpia y normaliza el query de búsqueda."""
        cleaned = re.sub(r'[^\w\s\-]', ' ', raw_query)
        return ' '.join(cleaned.split()).strip().lower()

    def _combine_query(self, query: str, author: Optional[str], title: Optional[str]) -> str:
        """Combina query con author/title si vienen separados."""
        parts = []
        if author:
            parts.append(author)
        if title:
            parts.append(title)
        if query and not parts:
            parts.append(query)
        elif query and parts:
            if query not in ' '.join(parts):
                parts.append(query)
        return ' '.join(parts)

    def _build_search_url(self, query: str, page: int = 1) -> str:
        """Helper para construir la URL, opcional."""
        pass

    def _parse_results(self, html: str) -> list[SearchResult]:
        """Helper para parsear resultados, opcional."""
        pass
