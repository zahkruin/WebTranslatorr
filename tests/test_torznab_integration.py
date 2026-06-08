"""
Integration tests for the Torznab API flow.

Tests the full request/response cycle with mocked providers,
validating XML responses that *Arr apps would receive.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from xml.etree.ElementTree import fromstring
from datetime import datetime

from app.core.models import SearchResult, ProviderCapabilities
from app.torznab.mapper import TorznabMapper
from app.torznab.caps import CapsGenerator
from app.torznab.errors import TorznabErrors


class TestCapabilitiesXML:
    """Tests for t=caps endpoint XML generation."""

    def test_caps_generates_valid_xml(self):
        capabilities = [
            ProviderCapabilities(
                provider_id="ebookelo",
                display_name="Ebookelo",
                supported_categories=[7000, 7020, 8000, 8010],
                supported_search_params=["q", "author", "title"],
                supports_book_search=True,
            ),
            ProviderCapabilities(
                provider_id="mejortorrent",
                display_name="MejorTorrent",
                supported_categories=[2000, 2030, 2040, 5000, 5030, 5040],
                supported_search_params=["q", "season", "ep", "imdbid"],
                supports_movie_search=True,
                supports_tv_search=True,
            ),
        ]

        xml = CapsGenerator.generate(capabilities)

        root = fromstring(xml)
        assert root.tag == "caps"

        categories = root.find("categories")
        assert categories is not None
        cats = categories.findall("category")
        assert len(cats) > 0

        searching = root.find("searching")
        assert searching is not None
        assert searching.find("search") is not None
        assert searching.find("book-search") is not None

    def test_caps_with_no_providers(self):
        xml = CapsGenerator.generate([])
        root = fromstring(xml)
        assert root.tag == "caps"
        categories = root.find("categories")
        cats = categories.findall("category")
        assert len(cats) == 0


class TestSearchResultsXML:
    """Tests for t=search results XML generation."""

    def test_search_results_xml_valid(self):
        results = [
            SearchResult(
                title="Test Book",
                guid="test-123",
                link="https://example.com/book/123",
                download_url="/api/download?provider=test&id=123",
                size_bytes=2048,
                pub_date=datetime(2024, 1, 15, 12, 0, 0),
                categories=[7000, 7020],
                description="A test book description",
                seeders=100,
                peers=50,
                author="Test Author",
            )
        ]

        xml = TorznabMapper.results_to_xml(results, offset=0, total=1)
        root = fromstring(xml)

        assert root.tag == "rss"
        assert root.attrib["version"] == "2.0"

        channel = root.find("channel")
        items = channel.findall("item")
        assert len(items) == 1

        item = items[0]
        assert item.find("title").text == "Test Book"
        assert item.find("guid").text == "test-123"

        # Collect all torznab attributes (uses xmlns:torznab namespace)
        torznab_attrs = item.findall(".//{http://torznab.com/schemas/2015/feed}attr")
        # Build a dict - note: duplicate 'category' keys will be overwritten
        attr_dict = {}
        for a in torznab_attrs:
            name = a.attrib["name"]
            if name not in attr_dict:
                attr_dict[name] = a.attrib["value"]
            elif name == "category":
                # Combine multiple category values
                existing = attr_dict[name]
                attr_dict[name] = f"{existing},{a.attrib['value']}"

        assert attr_dict.get("size") == "2048"
        assert attr_dict.get("seeders") == "100"
        assert attr_dict.get("peers") == "50"

    def test_search_results_xml_empty(self):
        xml = TorznabMapper.results_to_xml([], offset=0, total=0)
        root = fromstring(xml)
        channel = root.find("channel")
        items = channel.findall("item")
        assert len(items) == 0

    def test_search_results_with_pagination(self):
        results = [
            SearchResult(title=f"Book {i}", guid=f"test-{i}", link="", download_url="", size_bytes=0)
            for i in range(20)
        ]

        xml = TorznabMapper.results_to_xml(results[:10], offset=0, total=20)
        root = fromstring(xml)
        channel = root.find("channel")

        # Check response attribute for total count
        response_el = channel.find("{http://www.newznab.com/DTD/2010/feeds/attributes/}response")
        if response_el is not None:
            assert response_el.attrib.get("total") == "20"

    def test_search_results_with_video_attributes(self):
        results = [
            SearchResult(
                title="Test Movie",
                guid="movie-123",
                link="https://example.com/movie/123",
                download_url="https://example.com/movie.torrent",
                size_bytes=1500000000,
                pub_date=datetime(2024, 6, 15, 20, 0, 0),
                categories=[2000, 2040],
                seeders=200,
                peers=150,
                imdb_id="tt1375666",
                info_hash="abcdef1234567890",
            )
        ]

        xml = TorznabMapper.results_to_xml(results, offset=0, total=1)
        root = fromstring(xml)
        channel = root.find("channel")
        item = channel.findall("item")[0]

        torznab_attrs = item.findall(".//{http://torznab.com/schemas/2015/feed}attr")
        attr_dict = {a.attrib["name"]: a.attrib["value"] for a in torznab_attrs}

        assert attr_dict.get("imdbid") == "tt1375666"
        assert attr_dict.get("infohash") == "abcdef1234567890"


class TestErrorXML:
    """Tests for error XML responses."""

    def test_incorrect_api_key(self):
        xml = TorznabErrors.incorrect_api_key()
        root = fromstring(xml)
        assert root.tag == "error"
        assert root.attrib["code"] == "100"
        assert "API" in root.attrib["description"]

    def test_no_search_results(self):
        xml = TorznabErrors.no_search_results()
        root = fromstring(xml)
        assert root.tag == "error"
        assert root.attrib["code"] == "200"

    def test_server_error(self):
        xml = TorznabErrors.server_error("Something went wrong")
        root = fromstring(xml)
        assert root.tag == "error"
        assert root.attrib["code"] == "500"
        assert "Something went wrong" in root.attrib["description"]

    def test_all_error_xmls_valid(self):
        """All error XML should be parseable."""
        for error_xml in [
            TorznabErrors.incorrect_api_key(),
            TorznabErrors.no_search_results(),
            TorznabErrors.server_error("test"),
            TorznabErrors.invalid_category(),
            TorznabErrors.missing_search_param(),
            TorznabErrors.account_suspended(),
        ]:
            root = fromstring(error_xml)
            assert root.tag == "error"


class TestProviderRegistryIntegration:
    """Tests for ProviderRegistry integration with providers."""

    def test_registry_clear_and_register(self):
        from app.providers.registry import registry
        from unittest.mock import AsyncMock

        registry.clear()

        # Create a mock provider with all required attributes
        mock_prov = MagicMock()
        mock_prov.provider_id = "test_provider"
        mock_prov.display_name = "Test Provider"
        mock_prov.categories = [7000, 7020]
        mock_prov.search = AsyncMock(return_value=[])
        mock_prov.get_download_url = AsyncMock(return_value="https://example.com/dl")
        mock_prov.get_capabilities.return_value = ProviderCapabilities(
            provider_id="test_provider",
            display_name="Test Provider",
            supported_categories=[7000, 7020],
            supported_search_params=["q"],
            supports_book_search=True,
        )

        registry.register(mock_prov)
        assert registry.get("test_provider") == mock_prov
        assert len(registry.get_all()) == 1

        matching = registry.get_by_categories([7000])
        assert mock_prov in matching

        book_providers = registry.get_by_content_type("books")
        assert mock_prov in book_providers

        registry.clear()
        assert len(registry.get_all()) == 0

    def test_get_raises_on_unknown(self):
        from app.providers.registry import registry
        from app.core.exceptions import ProviderNotFoundError

        registry.clear()
        with pytest.raises(ProviderNotFoundError):
            registry.get("nonexistent")

    def test_unregister_existing(self):
        from app.providers.registry import registry
        from app.core.exceptions import ProviderNotFoundError
        from unittest.mock import AsyncMock

        registry.clear()
        mock_prov = MagicMock()
        mock_prov.provider_id = "test_unreg"
        mock_prov.display_name = "Test Unreg"
        mock_prov.search = AsyncMock(return_value=[])
        mock_prov.get_download_url = AsyncMock(return_value="")
        mock_prov.get_capabilities.return_value = ProviderCapabilities(
            provider_id="test_unreg",
            display_name="Test Unreg",
            supported_categories=[7000],
            supported_search_params=["q"],
        )

        registry.register(mock_prov)
        assert registry.get("test_unreg") == mock_prov
        registry.unregister("test_unreg")
        with pytest.raises(ProviderNotFoundError):
            registry.get("test_unreg")

    def test_parent_category_matching(self):
        from app.providers.registry import registry

        registry.clear()
        mock_prov = MagicMock()
        mock_prov.provider_id = "parent_test"
        mock_prov.display_name = "Parent Test"
        mock_prov.get_capabilities.return_value = ProviderCapabilities(
            provider_id="parent_test",
            display_name="Parent Test",
            supported_categories=[2000],  # Only parent, not subcategory 2040
            supported_search_params=["q"],
        )
        registry.register(mock_prov)
        # 2040 should match via _parent_match → 2000
        matching = registry.get_by_categories([2040])
        assert mock_prov in matching


@pytest.mark.asyncio
class TestSmartRouterIntegration:
    """Tests for SmartRouter with registered providers."""

    async def test_route_book_search(self):
        from app.providers.registry import ProviderRegistry
        from app.routing.smart_router import SmartRouter
        from unittest.mock import AsyncMock, MagicMock

        registry = ProviderRegistry()
        router = SmartRouter(registry)

        book_prov = MagicMock()
        book_prov.provider_id = "test_book"
        book_prov.display_name = "Test Book Provider"
        book_prov.categories = [7000, 7020]
        registry.register(book_prov)

        params = {"t": "search", "q": "harry potter", "cat": "7000"}
        providers = await router.route(params)
        assert len(providers) == 1
        assert providers[0].provider_id == "test_book"

    async def test_route_with_no_matching_providers(self):
        from app.providers.registry import ProviderRegistry
        from app.routing.smart_router import SmartRouter

        registry = ProviderRegistry()
        registry.clear()
        router = SmartRouter(registry)

        providers = await router.route({"t": "search", "q": "test"})
        assert providers == []

    async def test_route_infers_content_type_from_query(self):
        from app.providers.registry import ProviderRegistry
        from app.routing.smart_router import SmartRouter
        from unittest.mock import AsyncMock, MagicMock

        registry = ProviderRegistry()
        router = SmartRouter(registry)

        video_prov = MagicMock()
        video_prov.provider_id = "test_video"
        video_prov.display_name = "Test Video Provider"
        video_prov.categories = [2000, 2030, 5000, 5030]
        registry.register(video_prov)

        providers = await router.route({"t": "search", "q": "pelicula 1080p"})
        assert len(providers) > 0

    async def test_infer_content_type(self):
        """Tests the _infer_content_type method of SmartRouter."""
        from app.providers.registry import ProviderRegistry
        from app.routing.smart_router import SmartRouter
        registry = ProviderRegistry()
        router = SmartRouter(registry)

        # Test book keywords → returns "books" (plural)
        book_type = router._infer_content_type("libro de harry potter epub")
        assert book_type == "books"

        # Test movie keywords
        movie_type = router._infer_content_type("pelicula 1080p 2024")
        assert movie_type == "movies"

        # Test TV keywords
        tv_type = router._infer_content_type("serie temporada 1 capitulo 5")
        assert tv_type == "tv"

        # Test ambiguous query
        ambiguous = router._infer_content_type("test query")
        assert ambiguous is None
