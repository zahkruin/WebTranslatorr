"""
Smart Router: Determina qué provider(s) invocar basándose en:
1. Las categorías solicitadas (cat=7000 → libros, cat=2000 → películas)
2. El tipo de búsqueda (t=search, t=tvsearch, t=movie, t=book)
3. Parámetros específicos (imdbid → video provider, author → book provider)
4. Inferencia inteligente de contenido desde el query
"""
import logging
from enum import Enum
from typing import Optional

from app.providers.registry import ProviderRegistry, registry
from app.providers.base import BaseProvider
from app.core.enums import SearchType
from app.core.categories import CategoryMapper


logger = logging.getLogger("smart_router")

# Palabras clave para detectar tipo de contenido en queries genéricas
BOOK_KEYWORDS = [
    "libro", "novela", "lectura", "pdf", "epub", "mobi", "autor", "author",
    "book", "literatura", "poesía", "poesia", "cuento", "ensayo",
    "editorial", "saga", "trilogía", "trilogia", "biografía", "biografia",
]
MOVIE_KEYWORDS = [
    "película", "pelicula", "movie", "film", "cine", "ver", "subtitulada",
    "1080p", "2160p", "4k", "bluray", "blu-ray", "dvdrip", "hdrip",
    "cam", "ts", "director's cut",
]
TV_KEYWORDS = [
    "serie", "tv", "capítulo", "capitulo", "episodio", "temporada",
    "chapter", "season", "episode", "tvshow", "sitcom",
]


class SmartRouter:
    def __init__(self, registry: ProviderRegistry):
        self.registry = registry

    async def route(self, params: dict) -> list[BaseProvider]:
        """
        Algoritmo de routing con inferencia inteligente:

        1. Si hay `t=tvsearch` o `t=movie` → solo providers de video
        2. Si hay `t=book` → solo providers de libros
        3. Si hay `cat` → filtrar por categorías
        4. Si hay `imdbid` o `tvdbid` → solo providers de video
        5. Si hay `author` o `title` → solo providers de libros
        6. Si hay `q` (query) → inferir tipo por palabras clave
        7. Sin filtros → devolver providers más rápidos/estables
        """
        search_type = self._detect_search_type(params)
        categories = self._extract_categories(params)
        query = params.get("q", "")

        # Routing por tipo de búsqueda explícito
        if search_type == SearchType.BOOK:
            return self._get_book_providers()
        elif search_type in (SearchType.TV, SearchType.MOVIE):
            return self._get_video_providers()

        # Routing por categorías
        if categories:
            detected = CategoryMapper.categorize_request(categories)
            if "books" in detected and "movies" not in detected and "tv" not in detected:
                return self._get_book_providers()
            elif ("movies" in detected or "tv" in detected) and "books" not in detected:
                return self._get_video_providers()
            return self.registry.get_by_categories(categories)

        # Routing por parámetros especiales
        if params.get("imdbid") or params.get("tvdbid"):
            return self._get_video_providers()
        if params.get("author") or params.get("title"):
            return self._get_book_providers()

        # Inferencia inteligente desde el query
        if query:
            inferred_type = self._infer_content_type(query)
            if inferred_type == "books":
                return self._get_book_providers()
            elif inferred_type in ("movies", "tv", "video"):
                return self._get_video_providers()

        # Sin filtros → devolver providers más estables primero
        return self.registry.get_all()

    def _infer_content_type(self, query: str) -> Optional[str]:
        """
        Infiere el tipo de contenido desde el texto de búsqueda
        usando palabras clave y heurísticas simples.
        """
        query_lower = query.lower()

        # Contar coincidencias por categoría
        book_score = sum(1 for kw in BOOK_KEYWORDS if kw in query_lower)
        movie_score = sum(1 for kw in MOVIE_KEYWORDS if kw in query_lower)
        tv_score = sum(1 for kw in TV_KEYWORDS if kw in query_lower)

        winners = []
        max_score = max(book_score, movie_score, tv_score)

        if max_score == 0:
            return None  # No se pudo inferir

        if book_score == max_score:
            winners.append("books")
        if movie_score == max_score:
            winners.append("movies")
        if tv_score == max_score:
            winners.append("tv")

        # Si hay empate entre movies y tv, devolver video en general
        if len(winners) == 2 and "movies" in winners and "tv" in winners:
            return "video"

        return winners[0] if winners else None

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
