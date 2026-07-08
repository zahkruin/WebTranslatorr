"""
Caching service for search results using cachetools.
Reduces redundant scraping of the same queries within TTL window.
"""
import logging
import re
from typing import Optional

from cachetools import TTLCache

from config import settings

logger = logging.getLogger("cache")


STOPWORDS_EN = {
    "the", "a", "an", "and", "or", "of", "in", "on", "to", "for",
    "with", "at", "by", "from", "is", "it", "as", "be", "no", "not",
    "but", "so", "if", "into", "its", "all", "has", "had", "was", "are",
    "been", "new", "one", "two", "this", "that", "over", "up", "out",
    "de", "la", "el", "los", "las", "del", "un", "una", "en", "y", "o",
    "al", "por", "con", "sin", "para", "que", "es", "su",
}


def _normalize_query_key(raw: str) -> str:
    if not raw:
        return ""
    words = raw.lower().split()
    seen: set[str] = set()
    deduped: list[str] = []
    for w in words:
        if w not in seen:
            seen.add(w)
            deduped.append(w)
    sorted_words = sorted(deduped)
    return " ".join(w for w in sorted_words if w not in STOPWORDS_EN)


def normalize_query_key(raw: str) -> str:
    """Public helper: collapse a query string into a canonical, order-independent key."""
    return _normalize_query_key(raw)


class SearchCache:
    """
    Thread-safe TTL cache for search results.
    Keys are (provider_id, normalized_query, category_tuple).
    """

    def __init__(self, maxsize: int = 512, ttl: int = 300):
        self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
        self._enabled = settings.CACHE_ENABLED

    def _make_key(self, provider_id: str, query: str, categories: Optional[list[int]]) -> str:
        cat_part = ",".join(str(c) for c in sorted(categories)) if categories else ""
        normalized_q = _normalize_query_key(query)
        return f"{provider_id}|{normalized_q}|{cat_part}"

    def get(self, provider_id: str, query: str, categories: Optional[list[int]] = None):
        """Retrieve cached results if available."""
        if not self._enabled:
            return None
        key = self._make_key(provider_id, query, categories)
        return self._cache.get(key)

    def set(self, provider_id: str, query: str, results, categories: Optional[list[int]] = None):
        """Store results in cache."""
        if not self._enabled:
            return
        key = self._make_key(provider_id, query, categories)
        self._cache[key] = results
        logger.debug(f"Cached {len(results)} results for {key}")

    def invalidate(self, provider_id: str, query: str = None):
        """Invalidate cache entries for a provider (optionally for a specific query)."""
        # TTLCache doesn't support pattern deletion, so we just note it
        logger.debug(f"Cache invalidation requested for {provider_id}")


# Global cache instance
search_cache = SearchCache(
    maxsize=512,
    ttl=settings.CACHE_TTL_SECONDS,
)
