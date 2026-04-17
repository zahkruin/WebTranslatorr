"""
Smart Router: Determina qué provider(s) invocar basándose en:
1. Las categorías solicitadas (cat=7000 → libros, cat=2000 → películas)
2. El tipo de búsqueda (t=search, t=tvsearch, t=movie, t=book)
3. Parámetros específicos (imdbid → video provider, author → book provider)
"""
from enum import Enum
from typing import Optional

from app.providers.registry import ProviderRegistry, registry
from app.providers.base import BaseProvider
from app.core.enums import SearchType
from app.core.categories import CategoryMapper


class SmartRouter:
    def __init__(self, registry: ProviderRegistry):
        self.registry = registry

    async def route(self, params: dict) -> list[BaseProvider]:
        """
        Algoritmo de routing:

        1. Si hay `t=tvsearch` o `t=movie` → solo providers de video
        2. Si hay `t=book` → solo providers de libros
        3. Si hay `cat` → filtrar por categorías
        4. Si hay `imdbid` → solo providers de video con soporte IMDb
        5. Si hay `author` → solo providers de libros
        6. Sin filtros (t=search sin cat) → TODOS los providers
        """
        search_type = self._detect_search_type(params)
        categories = self._extract_categories(params)

        # Routing por tipo de búsqueda explícito
        if search_type == SearchType.BOOK:
            return self._get_book_providers()
        elif search_type in (SearchType.TV, SearchType.MOVIE):
            return self._get_video_providers()

        # Routing por categorías
        if categories:
            return self.registry.get_by_categories(categories)

        # Routing por parámetros especiales
        if params.get("imdbid") or params.get("tvdbid"):
            return self._get_video_providers()
        if params.get("author") or params.get("title"):
            return self._get_book_providers()

        # Sin filtros → todos
        return self.registry.get_all()

    def _detect_search_type(self, params: dict) -> SearchType:
        t = params.get("t", "search").lower()
        mapping = {
            "search": SearchType.GENERIC,
            "tvsearch": SearchType.TV,
            "movie": SearchType.MOVIE,
            "book": SearchType.BOOK,
        }
        return mapping.get(t, SearchType.GENERIC)

    def _extract_categories(self, params: dict) -> list[int]:
        cat_str = params.get("cat", "")
        if not cat_str:
            return []
        return [int(c) for c in cat_str.split(",") if c.isdigit()]

    def _get_book_providers(self) -> list[BaseProvider]:
        return self.registry.get_by_content_type("books")

    def _get_video_providers(self) -> list[BaseProvider]:
        movies = self.registry.get_by_content_type("movies")
        tv = self.registry.get_by_content_type("tv")
        # Unir y eliminar duplicados
        seen = set()
        result = []
        for p in movies + tv:
            if p.provider_id not in seen:
                seen.add(p.provider_id)
                result.append(p)
        return result


# Instancia global del router
smart_router = SmartRouter(registry)
