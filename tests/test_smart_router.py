"""
Tests for Smart Router.
"""

import pytest
import pytest_asyncio
from app.core.enums import SearchType
from app.routing.smart_router import SmartRouter


def test_detect_search_type():
    from app.providers.registry import ProviderRegistry
    router = SmartRouter(ProviderRegistry())

    assert router._detect_search_type({"t": "search"}) == SearchType.GENERIC
    assert router._detect_search_type({"t": "tvsearch"}) == SearchType.TV
    assert router._detect_search_type({"t": "movie"}) == SearchType.MOVIE
    assert router._detect_search_type({"t": "book"}) == SearchType.BOOK
    assert router._detect_search_type({}) == SearchType.GENERIC


def test_extract_categories():
    from app.providers.registry import ProviderRegistry
    router = SmartRouter(ProviderRegistry())

    assert router._extract_categories({"cat": "7000,7020"}) == [7000, 7020]
    assert router._extract_categories({"cat": "2000"}) == [2000]
    assert router._extract_categories({"cat": ""}) == []
    assert router._extract_categories({}) == []


@pytest.mark.asyncio
async def test_route_by_search_type_book(empty_registry, router):
    params = {"t": "book"}
    providers = await router.route(params)
    assert isinstance(providers, list)


@pytest.mark.asyncio
async def test_route_by_search_type_movie(empty_registry, router):
    params = {"t": "movie"}
    providers = await router.route(params)
    assert isinstance(providers, list)


@pytest.mark.asyncio
async def test_route_by_categories(empty_registry, router):
    params = {"t": "search", "cat": "7000"}
    providers = await router.route(params)
    assert isinstance(providers, list)


@pytest.mark.asyncio
async def test_route_by_imdbid(empty_registry, router):
    params = {"imdbid": "tt1234567"}
    providers = await router.route(params)
    assert isinstance(providers, list)


@pytest.mark.asyncio
async def test_route_by_author(empty_registry, router):
    params = {"author": "John Doe"}
    providers = await router.route(params)
    assert isinstance(providers, list)
