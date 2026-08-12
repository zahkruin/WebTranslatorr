"""
Caching service for search results using cachetools.
Reduces redundant scraping of the same queries within TTL window.
"""
import asyncio
import logging
from typing import Optional

from cachetools import TTLCache

from config import settings

logger = logging.getLogger("cache")


class SearchCache:
    """
    Thread-safe TTL cache for search results.
    Keys are (provider_id, normalized_query, category_tuple, offset, limit).
    """

    def __init__(self, maxsize: int = 512, ttl: int = 300):
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._enabled = settings.CACHE_ENABLED
        self._lock = asyncio.Lock()

    def _make_key(
        self,
        provider_id: str,
        query: str,
        categories: Optional[list[int]],
        offset: int = 0,
        limit: int = 50,
    ) -> str:
        cat_part = ",".join(str(c) for c in sorted(categories)) if categories else ""
        return f"{provider_id}|{query}|{cat_part}|{offset}|{limit}"

    async def get(
        self,
        provider_id: str,
        query: str,
        categories: Optional[list[int]] = None,
        offset: int = 0,
        limit: int = 50,
    ):
        if not self._enabled:
            return None
        key = self._make_key(provider_id, query, categories, offset, limit)
        async with self._lock:
            return self._cache.get(key)

    async def set(
        self,
        provider_id: str,
        query: str,
        results,
        categories: Optional[list[int]] = None,
        offset: int = 0,
        limit: int = 50,
    ):
        if not self._enabled:
            return
        key = self._make_key(provider_id, query, categories, offset, limit)
        async with self._lock:
            self._cache[key] = results
        logger.debug(f"Cached {len(results)} results for {key}")

    async def invalidate(self, provider_id: str, query: str = None):
        async with self._lock:
            if query is None:
                keys_to_delete = [
                    key for key in list(self._cache.keys())
                    if key.startswith(f"{provider_id}|")
                ]
            else:
                keys_to_delete = [
                    key for key in list(self._cache.keys())
                    if key.startswith(f"{provider_id}|{query}|")
                ]
            for key in keys_to_delete:
                del self._cache[key]
            logger.debug(f"Cache invalidated for {provider_id}")


search_cache = SearchCache(
    maxsize=512,
    ttl=settings.CACHE_TTL_SECONDS,
)
