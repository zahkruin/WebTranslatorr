"""
Tests for SearchCache service.
"""

import time
import pytest

from app.services.cache import SearchCache


class TestSearchCache:
    """Tests for the SearchCache TTL cache wrapper."""

    def test_set_and_get(self):
        cache = SearchCache(maxsize=128, ttl=300)
        results = ["item1", "item2"]
        cache.set("test_prov", "harry potter", results, [7020])
        cached = cache.get("test_prov", "harry potter", [7020])
        assert cached == results

    def test_miss_on_different_query(self):
        cache = SearchCache(maxsize=128, ttl=300)
        cache.set("test_prov", "query1", ["result1"])
        cached = cache.get("test_prov", "query2")
        assert cached is None

    def test_miss_on_different_provider(self):
        cache = SearchCache(maxsize=128, ttl=300)
        cache.set("prov_a", "query", ["result_a"])
        cached = cache.get("prov_b", "query")
        assert cached is None

    def test_miss_on_different_categories(self):
        cache = SearchCache(maxsize=128, ttl=300)
        cache.set("prov", "query", ["result"], [7000])
        cached = cache.get("prov", "query", [7020])
        assert cached is None

    def test_key_order_independent(self):
        cache = SearchCache(maxsize=128, ttl=300)
        cache.set("prov", "q", ["r"], [7000, 7020])
        # Same categories in different order
        cached = cache.get("prov", "q", [7020, 7000])
        assert cached == ["r"]

    def test_miss_on_ttl_expiry(self):
        cache = SearchCache(maxsize=128, ttl=0.1)  # 100ms TTL
        cache.set("prov", "q", ["result"])
        time.sleep(0.15)
        cached = cache.get("prov", "q")
        assert cached is None

    def test_empty_categories(self):
        cache = SearchCache(maxsize=128, ttl=300)
        cache.set("prov", "q", ["result"])
        cached = cache.get("prov", "q")
        assert cached == ["result"]

    def test_invalidate(self):
        cache = SearchCache(maxsize=128, ttl=300)
        cache.set("prov", "q", ["result"])
        cache.invalidate("prov")
        # invalidate is a no-op currently (log only), but should not error
        cached = cache.get("prov", "q")
        assert cached == ["result"]  # Still cached since invalidate is log-only

    def test_disabled_cache(self):
        """When cache is disabled, get should always return None."""
        cache = SearchCache(maxsize=128, ttl=300)
        cache._enabled = False
        cache.set("prov", "q", ["result"])
        cached = cache.get("prov", "q")
        assert cached is None
