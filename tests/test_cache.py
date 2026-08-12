"""
Tests for SearchCache service.
"""

import asyncio
import time
import pytest

from app.services.cache import SearchCache


class TestSearchCache:
    """Tests for the SearchCache TTL cache wrapper."""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        cache = SearchCache(maxsize=128, ttl=300)
        results = ["item1", "item2"]
        await cache.set("test_prov", "harry potter", results, [7020])
        cached = await cache.get("test_prov", "harry potter", [7020])
        assert cached == results

    @pytest.mark.asyncio
    async def test_miss_on_different_query(self):
        cache = SearchCache(maxsize=128, ttl=300)
        await cache.set("test_prov", "query1", ["result1"])
        cached = await cache.get("test_prov", "query2")
        assert cached is None

    @pytest.mark.asyncio
    async def test_miss_on_different_provider(self):
        cache = SearchCache(maxsize=128, ttl=300)
        await cache.set("prov_a", "query", ["result_a"])
        cached = await cache.get("prov_b", "query")
        assert cached is None

    @pytest.mark.asyncio
    async def test_miss_on_different_categories(self):
        cache = SearchCache(maxsize=128, ttl=300)
        await cache.set("prov", "query", ["result"], [7000])
        cached = await cache.get("prov", "query", [7020])
        assert cached is None

    @pytest.mark.asyncio
    async def test_key_order_independent(self):
        cache = SearchCache(maxsize=128, ttl=300)
        await cache.set("prov", "q", ["r"], [7000, 7020])
        cached = await cache.get("prov", "q", [7020, 7000])
        assert cached == ["r"]

    @pytest.mark.asyncio
    async def test_miss_on_ttl_expiry(self):
        cache = SearchCache(maxsize=128, ttl=0.1)
        await cache.set("prov", "q", ["result"])
        await asyncio.sleep(0.15)
        cached = await cache.get("prov", "q")
        assert cached is None

    @pytest.mark.asyncio
    async def test_empty_categories(self):
        cache = SearchCache(maxsize=128, ttl=300)
        await cache.set("prov", "q", ["result"])
        cached = await cache.get("prov", "q")
        assert cached == ["result"]

    @pytest.mark.asyncio
    async def test_offset_limit_in_key(self):
        cache = SearchCache(maxsize=128, ttl=300)
        await cache.set("prov", "q", ["page0"], offset=0, limit=50)
        await cache.set("prov", "q", ["page1"], offset=50, limit=50)
        assert await cache.get("prov", "q", offset=0, limit=50) == ["page0"]
        assert await cache.get("prov", "q", offset=50, limit=50) == ["page1"]

    @pytest.mark.asyncio
    async def test_invalidate(self):
        cache = SearchCache(maxsize=128, ttl=300)
        await cache.set("prov", "q", ["result"])
        await cache.invalidate("prov")
        cached = await cache.get("prov", "q")
        assert cached is None

    @pytest.mark.asyncio
    async def test_disabled_cache(self):
        cache = SearchCache(maxsize=128, ttl=300)
        cache._enabled = False
        await cache.set("prov", "q", ["result"])
        cached = await cache.get("prov", "q")
        assert cached is None
