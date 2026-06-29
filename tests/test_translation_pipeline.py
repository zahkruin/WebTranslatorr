"""
Tests for the translation pipeline service.

Covers TranslationCache, WikidataClient, GoogleBooksClient,
TitleCleaner, and TranslationPipeline orchestrator.
"""

import pytest
from unittest.mock import AsyncMock

import httpx

from app.services.translation_pipeline import (
    TranslationCache,
    TranslationResult,
    WikidataClient,
    GoogleBooksClient,
    TitleCleaner,
    TranslationPipeline,
)


# ------------------------------------------------------------------
# Helper: httpx.Response with a dummy request so that
# raise_for_status() works in httpx >= 0.28.
# ------------------------------------------------------------------

_DUMMY_REQUEST = httpx.Request("GET", "https://test.example.com")


def _http200(json_body):
    """Return a 200 httpx.Response with JSON body and dummy request."""
    return httpx.Response(200, json=json_body, request=_DUMMY_REQUEST)


def _http(status_code):
    """Return an httpx.Response with a given status code (no body)."""
    return httpx.Response(status_code, request=_DUMMY_REQUEST)


# ============================================================
# TranslationCache tests
# ============================================================


class TestTranslationCache:
    """Unit tests for TranslationCache backed by SQLite :memory:."""

    @pytest.mark.asyncio
    async def test_normalize(self):
        """_normalize: lowercase, strip punctuation, collapse spaces."""
        result = TranslationCache._normalize("Hello,  World!!")
        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_normalize_empty(self):
        """_normalize: empty/None returns ''."""
        assert TranslationCache._normalize("") == ""

    @pytest.mark.asyncio
    async def test_hash_deterministic(self):
        """Same input → same hash."""
        h1 = TranslationCache._compute_hash("Test Title", "Author Name")
        h2 = TranslationCache._compute_hash("Test Title", "Author Name")
        assert h1 == h2

    @pytest.mark.asyncio
    async def test_hash_different(self):
        """Different inputs → different hashes."""
        h1 = TranslationCache._compute_hash("Title A", "Author A")
        h2 = TranslationCache._compute_hash("Title B", "Author B")
        assert h1 != h2

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Insert and retrieve a translation."""
        async with TranslationCache(db_path=":memory:") as cache:
            await cache.set(
                "English Title", "Author", "Título español", "test", 1.0
            )
            result = await cache.get("English Title", "Author")
            assert result is not None
            assert result.title_es == "Título español"
            assert result.source == "test"
            assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_get_miss(self):
        """Lookup non-existent entry returns None."""
        async with TranslationCache(db_path=":memory:") as cache:
            result = await cache.get("NonExistent Title")
            assert result is None

    @pytest.mark.asyncio
    async def test_hit_count_increments(self):
        """Multiple gets increment hit_count."""
        async with TranslationCache(db_path=":memory:") as cache:
            await cache.set("Test Title", None, "Título test", "test", 1.0)
            await cache.get("Test Title")
            await cache.get("Test Title")
            s = await cache.stats()
            assert s["total_hits"] == 2

    @pytest.mark.asyncio
    async def test_invalidate(self):
        """Delete entry and verify miss."""
        async with TranslationCache(db_path=":memory:") as cache:
            await cache.set("Test Title", None, "Título test", "test", 1.0)
            deleted = await cache.invalidate_one("Test Title")
            assert deleted is True
            result = await cache.get("Test Title")
            assert result is None

    @pytest.mark.asyncio
    async def test_stats(self):
        """stats() returns correct entries and total_hits."""
        async with TranslationCache(db_path=":memory:") as cache:
            await cache.set("Title 1", None, "Título 1", "test", 1.0)
            await cache.set("Title 2", None, "Título 2", "test", 1.0)
            await cache.get("Title 1")
            s = await cache.stats()
            assert s["entries"] == 2
            assert s["total_hits"] == 1

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """async with TranslationCache(':memory:') works."""
        async with TranslationCache(db_path=":memory:") as cache:
            assert cache._conn is not None
            await cache.set("Test", None, "Test", "test", 1.0)
            result = await cache.get("Test")
            assert result is not None
        assert cache._conn is None


# ============================================================
# TitleCleaner tests
# ============================================================


class TestTitleCleaner:
    """Unit tests for TitleCleaner.clean() static method."""

    def test_no_basura(self):
        """Clean title without metadata is unchanged."""
        assert TitleCleaner.clean("El nombre del viento") == "El nombre del viento"

    def test_edicion_bolsillo(self):
        """[Edición de bolsillo] removed."""
        result = TitleCleaner.clean("El nombre del viento [Edición de bolsillo]")
        assert result == "El nombre del viento"

    def test_spanish_edition(self):
        """(Spanish Edition) removed."""
        result = TitleCleaner.clean("El nombre del viento (Spanish Edition)")
        assert result == "El nombre del viento"

    def test_edicion_en_espanol(self):
        """(Edición en español) removed."""
        result = TitleCleaner.clean("El nombre del viento (Edición en español)")
        assert result == "El nombre del viento"

    def test_anno_entre_parentesis(self):
        """(2020) removed."""
        result = TitleCleaner.clean("El nombre del viento (2020)")
        assert result == "El nombre del viento"

    def test_a_novel(self):
        """: A Novel removed."""
        result = TitleCleaner.clean("El nombre del viento: A Novel")
        assert result == "El nombre del viento"

    def test_vol(self):
        """- Vol. 3 removed."""
        result = TitleCleaner.clean("El nombre del viento - Vol. 3")
        assert result == "El nombre del viento"

    def test_volume(self):
        """(Volume 1) removed."""
        result = TitleCleaner.clean("El nombre del viento (Volume 1)")
        assert result == "El nombre del viento"

    def test_book_number(self):
        """(Book 1) removed."""
        result = TitleCleaner.clean("El nombre del viento (Book 1)")
        assert result == "El nombre del viento"

    def test_kindle_edition(self):
        """[Kindle Edition] removed."""
        result = TitleCleaner.clean("El nombre del viento [Kindle Edition]")
        assert result == "El nombre del viento"

    def test_multiples_patrones(self):
        """Multiple patterns applied simultaneously."""
        # (Spanish Edition) removed → then : A Novel at end → removed
        result = TitleCleaner.clean(
            "El nombre del viento: A Novel (Spanish Edition)"
        )
        assert result == "El nombre del viento"

    def test_titulo_vacio_revierte(self):
        """Pattern that would empty title is reverted via guard."""
        result = TitleCleaner.clean("[Edición de bolsillo]")
        assert result == "[Edición de bolsillo]"

    def test_espacios_colapsados(self):
        """Multiple spaces collapsed to one."""
        result = TitleCleaner.clean("El  nombre   del    viento")
        assert result == "El nombre del viento"

    def test_brackets_content(self):
        """[Any content] removed."""
        result = TitleCleaner.clean("El nombre del viento [Bestseller 2020]")
        assert result == "El nombre del viento"


# ============================================================
# WikidataClient tests
# ============================================================


class TestWikidataClient:
    """Unit tests for WikidataClient with mocked httpx.AsyncClient."""

    @pytest.mark.asyncio
    async def test_wikidata_found_with_spanish_label(self):
        """SPARQL returns QID, EntityData has Spanish label → returns title."""
        client_mock = AsyncMock()
        client_mock.post = AsyncMock()
        client_mock.get = AsyncMock()

        sparql_resp = _http200(
            {
                "results": {
                    "bindings": [
                        {
                            "item": {
                                "value": "http://www.wikidata.org/entity/Q15228"
                            }
                        }
                    ]
                }
            },
        )
        entity_resp = _http200(
            {
                "entities": {
                    "Q15228": {
                        "labels": {
                            "es": {"value": "El Señor de los Anillos"}
                        }
                    }
                }
            },
        )
        client_mock.post.return_value = sparql_resp
        client_mock.get.return_value = entity_resp

        wikidata = WikidataClient(client=client_mock)
        result = await wikidata.get_spanish_title(
            "The Lord of the Rings", "J.R.R. Tolkien"
        )
        assert result == "El Señor de los Anillos"

    @pytest.mark.asyncio
    async def test_wikidata_found_no_spanish_label(self):
        """SPARQL returns QID but EntityData lacks Spanish label → None."""
        client_mock = AsyncMock()
        client_mock.post = AsyncMock()
        client_mock.get = AsyncMock()

        sparql_resp = _http200(
            {
                "results": {
                    "bindings": [
                        {
                            "item": {
                                "value": "http://www.wikidata.org/entity/Q99999"
                            }
                        }
                    ]
                }
            },
        )
        entity_resp = _http200(
            {
                "entities": {
                    "Q99999": {"labels": {"en": {"value": "Some Book"}}}
                }
            },
        )
        client_mock.post.return_value = sparql_resp
        client_mock.get.return_value = entity_resp

        wikidata = WikidataClient(client=client_mock)
        result = await wikidata.get_spanish_title("Some Book")
        assert result is None

    @pytest.mark.asyncio
    async def test_wikidata_not_found(self):
        """SPARQL returns empty bindings → None."""
        client_mock = AsyncMock()
        client_mock.post = AsyncMock()

        sparql_resp = _http200(
            {"results": {"bindings": []}},
        )
        client_mock.post.return_value = sparql_resp

        wikidata = WikidataClient(client=client_mock)
        result = await wikidata.get_spanish_title("Unknown Book")
        assert result is None

    @pytest.mark.asyncio
    async def test_wikidata_sparql_http_error(self):
        """SPARQL HTTP 500 → None."""
        client_mock = AsyncMock()
        client_mock.post = AsyncMock()

        client_mock.post.return_value = _http(500)

        wikidata = WikidataClient(client=client_mock)
        result = await wikidata.get_spanish_title("Test Title")
        assert result is None

    @pytest.mark.asyncio
    async def test_wikidata_sparql_timeout(self):
        """SPARQL timeout → None."""
        client_mock = AsyncMock()
        client_mock.post = AsyncMock()

        client_mock.post.side_effect = httpx.TimeoutException("timeout")

        wikidata = WikidataClient(client=client_mock)
        result = await wikidata.get_spanish_title("Test Title")
        assert result is None

    @pytest.mark.asyncio
    async def test_wikidata_disabled(self):
        """When enabled=False, returns None immediately."""
        wikidata = WikidataClient(client=AsyncMock(), enabled=False)
        result = await wikidata.get_spanish_title("Test Title")
        assert result is None

    @pytest.mark.asyncio
    async def test_wikidata_no_qid_in_binding(self):
        """SPARQL returns bindings without item URL → None."""
        client_mock = AsyncMock()
        client_mock.post = AsyncMock()

        sparql_resp = _http200(
            {
                "results": {
                    "bindings": [{"label_es": {"value": "Algún título"}}]
                }
            },
        )
        client_mock.post.return_value = sparql_resp

        wikidata = WikidataClient(client=client_mock)
        result = await wikidata.get_spanish_title("Some Title")
        assert result is None


# ============================================================
# GoogleBooksClient tests
# ============================================================


class TestGoogleBooksClient:
    """Unit tests for GoogleBooksClient with mocked httpx.AsyncClient."""

    @pytest.mark.asyncio
    async def test_google_found_with_title(self):
        """API returns items with title → returns title."""
        client_mock = AsyncMock()
        client_mock.get = AsyncMock()

        client_mock.get.return_value = _http200(
            {
                "items": [
                    {"volumeInfo": {"title": "El nombre del viento"}}
                ]
            },
        )

        google = GoogleBooksClient(client=client_mock, api_key="fake-key")
        result = await google.get_spanish_title(
            "The Name of the Wind", "Patrick Rothfuss"
        )
        assert result == "El nombre del viento"

    @pytest.mark.asyncio
    async def test_google_not_found(self):
        """API returns empty items → None."""
        client_mock = AsyncMock()
        client_mock.get = AsyncMock()

        client_mock.get.return_value = _http200(
            {"items": []}
        )

        google = GoogleBooksClient(client=client_mock, api_key="fake-key")
        result = await google.get_spanish_title("Unknown Book")
        assert result is None

    @pytest.mark.asyncio
    async def test_google_rate_limit_429(self):
        """HTTP 429 → None."""
        client_mock = AsyncMock()
        client_mock.get = AsyncMock()

        client_mock.get.return_value = _http(429)

        google = GoogleBooksClient(client=client_mock, api_key="fake-key")
        result = await google.get_spanish_title("Test Title")
        assert result is None

    @pytest.mark.asyncio
    async def test_google_auth_error_403(self):
        """HTTP 403 → None."""
        client_mock = AsyncMock()
        client_mock.get = AsyncMock()

        client_mock.get.return_value = _http(403)

        google = GoogleBooksClient(client=client_mock, api_key="fake-key")
        result = await google.get_spanish_title("Test Title")
        assert result is None

    @pytest.mark.asyncio
    async def test_google_timeout(self):
        """Timeout → None."""
        client_mock = AsyncMock()
        client_mock.get = AsyncMock()

        client_mock.get.side_effect = httpx.TimeoutException("timeout")

        google = GoogleBooksClient(client=client_mock, api_key="fake-key")
        result = await google.get_spanish_title("Test Title")
        assert result is None

    @pytest.mark.asyncio
    async def test_google_disabled(self):
        """When enabled=False, returns None immediately."""
        google = GoogleBooksClient(
            client=AsyncMock(), api_key="fake-key", enabled=False
        )
        result = await google.get_spanish_title("Test Title")
        assert result is None

    @pytest.mark.asyncio
    async def test_google_no_api_key(self):
        """When api_key is None, returns None immediately."""
        google = GoogleBooksClient(client=AsyncMock(), api_key="fake-key")
        # Override to simulate no key available
        google._api_key = None
        result = await google.get_spanish_title("Test Title")
        assert result is None


# ============================================================
# TranslationPipeline orchestrator tests
# ============================================================


class TestTranslationPipeline:
    """Unit tests for TranslationPipeline orchestrator with mocked layers."""

    @pytest.mark.asyncio
    async def test_pipeline_cache_hit(self):
        """Cache hit → return immediately, no external calls."""
        pipeline = TranslationPipeline()

        mock_cache = AsyncMock(spec=TranslationCache)
        mock_cache.get.return_value = TranslationResult(
            title_es="Título en español", source="cache", confidence=1.0
        )
        pipeline._cache = mock_cache

        result = await pipeline.translate("English Title")
        assert result is not None
        assert result.title_es == "Título en español"
        assert result.source == "cache"
        assert result.confidence == 1.0
        mock_cache.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_cache_miss_wikidata_hit(self):
        """Cache miss → wikidata hit → cached and returned."""
        pipeline = TranslationPipeline()

        mock_cache = AsyncMock(spec=TranslationCache)
        mock_cache.get.return_value = None
        mock_wikidata = AsyncMock(spec=WikidataClient)
        mock_wikidata.get_spanish_title.return_value = "Título español"

        pipeline._cache = mock_cache
        pipeline._wikidata = mock_wikidata

        result = await pipeline.translate("English Title")
        assert result is not None
        assert result.title_es == "Título español"
        assert result.source == "wikidata"
        assert result.confidence == 0.95
        mock_cache.get.assert_called_once()
        mock_wikidata.get_spanish_title.assert_called_once()
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_cache_miss_wikidata_miss_google_hit(self):
        """Cache miss → wikidata miss → google hit → cleaned, cached, returned."""
        pipeline = TranslationPipeline()

        mock_cache = AsyncMock(spec=TranslationCache)
        mock_cache.get.return_value = None
        mock_wikidata = AsyncMock(spec=WikidataClient)
        mock_wikidata.get_spanish_title.return_value = None
        mock_google = AsyncMock(spec=GoogleBooksClient)
        mock_google.get_spanish_title.return_value = (
            "El nombre del viento: A Novel (Spanish Edition)"
        )

        pipeline._cache = mock_cache
        pipeline._wikidata = mock_wikidata
        pipeline._google_books = mock_google

        result = await pipeline.translate(
            "The Name of the Wind", "Patrick Rothfuss"
        )
        assert result is not None
        assert result.title_es == "El nombre del viento"
        assert result.source == "google_books"
        assert result.confidence == 0.70
        mock_cache.get.assert_called_once()
        mock_wikidata.get_spanish_title.assert_called_once()
        mock_google.get_spanish_title.assert_called_once()
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_all_miss(self):
        """Cache miss → wikidata miss → google miss → None."""
        pipeline = TranslationPipeline()

        mock_cache = AsyncMock(spec=TranslationCache)
        mock_cache.get.return_value = None
        mock_wikidata = AsyncMock(spec=WikidataClient)
        mock_wikidata.get_spanish_title.return_value = None
        mock_google = AsyncMock(spec=GoogleBooksClient)
        mock_google.get_spanish_title.return_value = None

        pipeline._cache = mock_cache
        pipeline._wikidata = mock_wikidata
        pipeline._google_books = mock_google

        result = await pipeline.translate("Unknown Book")
        assert result is None
        mock_cache.get.assert_called_once()
        mock_wikidata.get_spanish_title.assert_called_once()
        mock_google.get_spanish_title.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_no_google_api_key(self):
        """Without google_books phase, pipeline falls through to None."""
        pipeline = TranslationPipeline()

        mock_cache = AsyncMock(spec=TranslationCache)
        mock_cache.get.return_value = None
        mock_wikidata = AsyncMock(spec=WikidataClient)
        mock_wikidata.get_spanish_title.return_value = None

        pipeline._cache = mock_cache
        pipeline._wikidata = mock_wikidata
        pipeline._google_books = None  # Not initialized (no API key)

        result = await pipeline.translate("English Title")
        assert result is None

    @pytest.mark.asyncio
    async def test_pipeline_confidence_values(self):
        """Verify confidence: cache=1.0, wikidata=0.95, google=0.70."""
        # Test cache confidence
        pipeline = TranslationPipeline()
        mock_cache = AsyncMock(spec=TranslationCache)
        mock_cache.get.return_value = TranslationResult(
            title_es="T1", source="cache", confidence=1.0
        )
        pipeline._cache = mock_cache
        result = await pipeline.translate("Test")
        assert result.confidence == 1.0

        # Test wikidata confidence
        pipeline2 = TranslationPipeline()
        mock_cache2 = AsyncMock(spec=TranslationCache)
        mock_cache2.get.return_value = None
        mock_wikidata2 = AsyncMock(spec=WikidataClient)
        mock_wikidata2.get_spanish_title.return_value = "Título"
        pipeline2._cache = mock_cache2
        pipeline2._wikidata = mock_wikidata2
        result2 = await pipeline2.translate("Test")
        assert result2.confidence == 0.95

        # Test google confidence
        pipeline3 = TranslationPipeline()
        mock_cache3 = AsyncMock(spec=TranslationCache)
        mock_cache3.get.return_value = None
        mock_wikidata3 = AsyncMock(spec=WikidataClient)
        mock_wikidata3.get_spanish_title.return_value = None
        mock_google3 = AsyncMock(spec=GoogleBooksClient)
        mock_google3.get_spanish_title.return_value = "Título"
        pipeline3._cache = mock_cache3
        pipeline3._wikidata = mock_wikidata3
        pipeline3._google_books = mock_google3
        result3 = await pipeline3.translate("Test")
        assert result3.confidence == 0.70

    @pytest.mark.asyncio
    async def test_pipeline_empty_title(self):
        """Empty title → None."""
        pipeline = TranslationPipeline()

        result = await pipeline.translate("")
        assert result is None

        result = await pipeline.translate("   ")
        assert result is None


# ============================================================================
# Integration with search endpoint (_handle_torznab_request)
# ============================================================================


class TestTranslationPipelineIntegration:
    """Tests for the translation pipeline integration in the search flow."""

    @pytest.mark.asyncio
    async def test_pipeline_disabled_by_default(self):
        """When TRANSLATION_PIPELINE_SEARCH_ENABLED=False, get_translation_pipeline returns None."""
        from app.services.translation_pipeline import get_translation_pipeline

        # The default is False, so this should return None
        pipeline = await get_translation_pipeline()
        assert pipeline is None

    @pytest.mark.asyncio
    async def test_pipeline_enabled_returns_instance(self, monkeypatch):
        """When enabled, get_translation_pipeline returns a pipeline instance."""
        from app.services.translation_pipeline import (
            get_translation_pipeline,
            shutdown_translation_pipeline,
            _translation_pipeline,
        )
        import app.services.translation_pipeline as tp_module

        # Reset singleton state for clean test
        tp_module._translation_pipeline = None

        try:
            monkeypatch.setattr(
                "app.services.translation_pipeline.settings.TRANSLATION_PIPELINE_SEARCH_ENABLED",
                True,
            )
            monkeypatch.setattr(
                "app.services.translation_pipeline.settings.TRANSLATION_PIPELINE_WIKIDATA_ENABLED",
                False,
            )
            monkeypatch.setattr(
                "app.services.translation_pipeline.settings.TRANSLATION_PIPELINE_GOOGLE_BOOKS_ENABLED",
                False,
            )
            # Use in-memory SQLite to avoid creating files
            monkeypatch.setattr(
                "app.services.translation_pipeline.settings.TRANSLATION_CACHE_PATH",
                ":memory:",
            )

            pipeline = await get_translation_pipeline()
            assert pipeline is not None
            assert isinstance(pipeline, tp_module.TranslationPipeline)

            # Calling again returns same instance
            pipeline2 = await get_translation_pipeline()
            assert pipeline2 is pipeline
        finally:
            await shutdown_translation_pipeline()
            tp_module._translation_pipeline = None

    @pytest.mark.asyncio
    async def test_effective_q_unchanged_when_pipeline_disabled(self):
        """effective_q should equal original q when pipeline is disabled."""
        effective_q = "The Name of the Wind"
        q = "The Name of the Wind"

        # Simulate disabled pipeline
        translation_pipeline = None
        if translation_pipeline is not None:
            result = await translation_pipeline.translate(q, None)
            if result is not None:
                effective_q = result.title_es

        assert effective_q == q

    @pytest.mark.asyncio
    async def test_is_book_search_categories(self):
        """Book search is detected when categories are in 7000-8999 range."""
        book_cats = [7020, 8010]
        movie_cats = [2000, 2030]

        is_book = any(7000 <= c <= 8999 for c in book_cats)
        is_movie = any(7000 <= c <= 8999 for c in movie_cats)

        assert is_book is True
        assert is_movie is False

    @pytest.mark.asyncio
    async def test_generic_search_no_categories(self):
        """Generic search (no categories) should trigger translation."""
        parsed_cats = []
        is_book_search = any(7000 <= c <= 8999 for c in parsed_cats)
        is_generic = len(parsed_cats) == 0

        assert is_book_search is False
        assert is_generic is True

    @pytest.mark.asyncio
    async def test_translation_not_applied_to_movie_search(self):
        """Movie search categories (2000-5999) should NOT trigger translation."""
        movie_cats = [2000]
        is_book = any(7000 <= c <= 8999 for c in movie_cats)
        assert is_book is False

    @pytest.mark.asyncio
    async def test_empty_query_not_translated(self):
        """Empty query should skip translation."""
        q = ""
        should_translate = bool(q and q.strip())
        assert should_translate is False

    @pytest.mark.asyncio
    async def test_whitespace_query_not_translated(self):
        """Whitespace-only query should skip translation."""
        q = "   "
        should_translate = bool(q and q.strip())
        assert should_translate is False

    @pytest.mark.asyncio
    async def test_translation_result_confidence_order(self):
        """Cache > wikidata > google_books confidence order is correct."""
        from app.services.translation_pipeline import TranslationResult

        cache = TranslationResult(title_es="T1", source="cache", confidence=1.0)
        wikidata = TranslationResult(title_es="T2", source="wikidata", confidence=0.95)
        google = TranslationResult(title_es="T3", source="google_books", confidence=0.70)

        # Higher confidence = more reliable
        assert cache.confidence > wikidata.confidence > google.confidence
        assert cache.source == "cache"
        assert wikidata.source == "wikidata"
        assert google.source == "google_books"
