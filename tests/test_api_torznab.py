"""
Tests for the Torznab API endpoints (/api and /api/download).
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api import torznab
from app.scraping.http_client import ScraperResponse
from app.scraping.http_client import ScraperResponse
from app.utils.torrent_generator import parse_info_hash
from app.scraping.http_client import HttpClient


def _mock_http_client():
    mock_http = MagicMock(spec=HttpClient)
    mock_http.download_file = AsyncMock(return_value=b"file content here")
    mock_http.get = AsyncMock(
        return_value=ScraperResponse(
            status_code=200,
            text="<html></html>",
            content=b"<html></html>",
            headers={},
            url="https://example.com",
        )
    )
    mock_http.head = AsyncMock(
        return_value=ScraperResponse(
            status_code=200,
            text="",
            content=b"",
            headers={},
            url="https://example.com",
        )
    )
    return mock_http


def _make_test_app(mock_http=None):
    app = FastAPI()
    app.state.http_client = mock_http or _mock_http_client()
    app.include_router(torznab.router)
    return app


@pytest.fixture(autouse=True)
def mock_auth_settings():
    with patch("app.api.auth.settings") as mock_settings:
        mock_settings.API_KEY = "testkey"
        yield


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset module-level globals before each test."""
    torznab.registry.clear()
    yield


# ── caps endpoint ──────────────────────────────────────────────────



def _init_providers_sync(*args, **kwargs):
    """Call async _init_providers from sync or async pytest contexts."""
    coro = torznab._init_providers(*args, **kwargs)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class TestCapsEndpoint:
    """Tests for t=caps via the /api endpoint."""

    def test_caps_returns_xml_with_wrong_api_key(self):
        """Should return caps XML even with wrong API key (Jackett-compatible behavior).
        
        Like Jackett, WebTranslatorr now allows t=caps without a valid API key
        so *Arr apps can discover the indexer before authentication is configured.
        Search/download operations still require a valid API key.
        """
        app = FastAPI()
        app.include_router(torznab.router)
        client = TestClient(app)
        response = client.get("/api?t=caps&apikey=wrong")
        assert response.status_code == 200
        assert "caps" in response.text.lower()
        # No error — caps is returned for service discovery

    def test_caps_returns_xml_with_valid_key(self):
        """Should return capabilities XML with valid API key."""
        with patch("app.api.torznab.settings") as mock_settings:
            mock_settings.API_KEY = "testkey"
            mock_settings.EBOOKELO_ENABLED = True
            mock_settings.EPUBLIBRE_ENABLED = True
            mock_settings.LECTULANDIA_ENABLED = True
            mock_settings.ESPAEBOOK_ENABLED = True
            mock_settings.HOLAEBOOK_ENABLED = True
            mock_settings.ANNASARCHIVE_ENABLED = True
            mock_settings.MEJORTORRENT_ENABLED = True
            mock_settings.DONTORRENT_ENABLED = False
            mock_settings.ELEJANDRIA_ENABLED = False
            mock_settings.GUTENBERG_ENABLED = False
            mock_settings.EPUBFLIX1_ENABLED = False
            mock_settings.LIBGEN_ENABLED = False
            mock_settings.BOOOBOOK_ENABLED = False
            mock_settings.LECTUEPUBLIBRE5_ENABLED = False
            mock_settings.MUNDOEPUBLIBRE1_ENABLED = False
            mock_settings.ZLIBRARY_ENABLED = False
            mock_settings.RATE_LIMIT_PER_SECOND = 100.0
            mock_settings.MAX_RETRIES = 1
            mock_settings.REQUEST_TIMEOUT = 5
            mock_settings.HTTP_PROXY = ""
            mock_settings.CACHE_ENABLED = True
            mock_settings.CACHE_TTL_SECONDS = 300

            app = _make_test_app()
            client = TestClient(app)

            _init_providers_sync(None, app.state.http_client)
            response = client.get("/api?t=caps&apikey=testkey")
            assert response.status_code == 200
            assert "<?xml" in response.text
            assert "caps" in response.text.lower()


# ── search endpoint ────────────────────────────────────────────────


class TestSearchEndpoint:
    """Tests for t=search via the /api endpoint."""

    @pytest.mark.asyncio
    async def test_search_no_results(self):
        """Should return empty results XML when no providers match."""
        with patch("app.api.torznab.settings") as mock_settings:
            mock_settings.API_KEY = "testkey"
            mock_settings.EBOOKELO_ENABLED = False
            mock_settings.EPUBLIBRE_ENABLED = False
            mock_settings.LECTULANDIA_ENABLED = False
            mock_settings.ESPAEBOOK_ENABLED = False
            mock_settings.HOLAEBOOK_ENABLED = False
            mock_settings.ANNASARCHIVE_ENABLED = False
            mock_settings.MEJORTORRENT_ENABLED = False
            mock_settings.DONTORRENT_ENABLED = False
            mock_settings.ELEJANDRIA_ENABLED = False
            mock_settings.GUTENBERG_ENABLED = False
            mock_settings.EPUBFLIX1_ENABLED = False
            mock_settings.LIBGEN_ENABLED = False
            mock_settings.BOOOBOOK_ENABLED = False
            mock_settings.LECTUEPUBLIBRE5_ENABLED = False
            mock_settings.MUNDOEPUBLIBRE1_ENABLED = False
            mock_settings.ZLIBRARY_ENABLED = False
            mock_settings.RATE_LIMIT_PER_SECOND = 100.0
            mock_settings.MAX_RETRIES = 1
            mock_settings.REQUEST_TIMEOUT = 5
            mock_settings.HTTP_PROXY = ""
            mock_settings.CACHE_ENABLED = False
            mock_settings.CACHE_TTL_SECONDS = 300

            app = _make_test_app()
            client = TestClient(app)

            _init_providers_sync(None, app.state.http_client)
            response = client.get("/api?t=search&q=test&apikey=testkey")
            assert response.status_code == 200
            assert "<?xml" in response.text

    @pytest.mark.asyncio
    async def test_search_book_with_results(self):
        """Book search should route to book providers and return results."""
        with patch("app.api.torznab.settings") as mock_settings:
            mock_settings.API_KEY = "testkey"
            mock_settings.EBOOKELO_ENABLED = True
            mock_settings.EPUBLIBRE_ENABLED = False
            mock_settings.LECTULANDIA_ENABLED = False
            mock_settings.ESPAEBOOK_ENABLED = False
            mock_settings.HOLAEBOOK_ENABLED = False
            mock_settings.ANNASARCHIVE_ENABLED = False
            mock_settings.MEJORTORRENT_ENABLED = False
            mock_settings.DONTORRENT_ENABLED = False
            mock_settings.ELEJANDRIA_ENABLED = False
            mock_settings.GUTENBERG_ENABLED = False
            mock_settings.EPUBFLIX1_ENABLED = False
            mock_settings.LIBGEN_ENABLED = False
            mock_settings.BOOOBOOK_ENABLED = False
            mock_settings.LECTUEPUBLIBRE5_ENABLED = False
            mock_settings.MUNDOEPUBLIBRE1_ENABLED = False
            mock_settings.ZLIBRARY_ENABLED = False
            mock_settings.RATE_LIMIT_PER_SECOND = 100.0
            mock_settings.MAX_RETRIES = 1
            mock_settings.REQUEST_TIMEOUT = 5
            mock_settings.HTTP_PROXY = ""
            mock_settings.CACHE_ENABLED = False
            mock_settings.CACHE_TTL_SECONDS = 300

            # Mock HttpClient to avoid real HTTP calls
            with patch("app.api.torznab.HttpClient") as mock_http_cls:
                mock_http = MagicMock()
                mock_http_cls.return_value = mock_http

                app = _make_test_app()
                client = TestClient(app)

                _init_providers_sync(None, app.state.http_client)
                response = client.get("/api?t=search&q=test&apikey=testkey&cat=8000")
                assert response.status_code == 200
                # Should return valid XML
                assert "<?xml" in response.text


# ── download endpoint ──────────────────────────────────────────────


class TestDownloadEndpoint:
    """Tests for /api/download endpoint."""

    @pytest.mark.asyncio
    async def test_download_unknown_provider(self):
        """Download with unknown provider should return error."""
        with patch("app.api.torznab.settings") as mock_settings:
            mock_settings.API_KEY = "testkey"
            mock_settings.RATE_LIMIT_PER_SECOND = 100.0
            mock_settings.MAX_RETRIES = 1
            mock_settings.REQUEST_TIMEOUT = 5
            mock_settings.HTTP_PROXY = ""
            mock_settings.EBOOKELO_ENABLED = False
            mock_settings.EPUBLIBRE_ENABLED = False
            mock_settings.LECTULANDIA_ENABLED = False
            mock_settings.ESPAEBOOK_ENABLED = False
            mock_settings.HOLAEBOOK_ENABLED = False
            mock_settings.ANNASARCHIVE_ENABLED = False
            mock_settings.MEJORTORRENT_ENABLED = False
            mock_settings.DONTORRENT_ENABLED = False
            mock_settings.ELEJANDRIA_ENABLED = False
            mock_settings.GUTENBERG_ENABLED = False
            mock_settings.EPUBFLIX1_ENABLED = False
            mock_settings.LIBGEN_ENABLED = False
            mock_settings.BOOOBOOK_ENABLED = False
            mock_settings.LECTUEPUBLIBRE5_ENABLED = False
            mock_settings.MUNDOEPUBLIBRE1_ENABLED = False
            mock_settings.ZLIBRARY_ENABLED = False
            mock_settings.CACHE_ENABLED = False
            mock_settings.CACHE_TTL_SECONDS = 300

            app = _make_test_app()
            client = TestClient(app)

            _init_providers_sync(None, app.state.http_client)
            response = client.get("/api/download?provider=nonexistent&id=123&apikey=testkey")
            assert response.status_code == 200
            assert "error" in response.text.lower()

    @pytest.mark.asyncio
    async def test_download_success(self):
        """Download with valid provider and URL should return file content (lines 225-250)."""
        with patch("app.api.torznab.settings") as mock_settings:
            mock_settings.API_KEY = "testkey"
            mock_settings.EBOOKELO_ENABLED = False
            mock_settings.EPUBLIBRE_ENABLED = False
            mock_settings.LECTULANDIA_ENABLED = False
            mock_settings.ESPAEBOOK_ENABLED = True
            mock_settings.HOLAEBOOK_ENABLED = False
            mock_settings.ANNASARCHIVE_ENABLED = False
            mock_settings.MEJORTORRENT_ENABLED = False
            mock_settings.DONTORRENT_ENABLED = False
            mock_settings.ELEJANDRIA_ENABLED = False
            mock_settings.GUTENBERG_ENABLED = False
            mock_settings.EPUBFLIX1_ENABLED = False
            mock_settings.LIBGEN_ENABLED = False
            mock_settings.BOOOBOOK_ENABLED = False
            mock_settings.LECTUEPUBLIBRE5_ENABLED = False
            mock_settings.MUNDOEPUBLIBRE1_ENABLED = False
            mock_settings.ZLIBRARY_ENABLED = False
            mock_settings.RATE_LIMIT_PER_SECOND = 100.0
            mock_settings.MAX_RETRIES = 1
            mock_settings.REQUEST_TIMEOUT = 5
            mock_settings.HTTP_PROXY = ""
            mock_settings.CACHE_ENABLED = False
            mock_settings.CACHE_TTL_SECONDS = 300
            mock_settings.EXTERNAL_URL = "http://localhost:9811"
            mock_settings.MAX_DOWNLOAD_BYTES = 524288000
            mock_settings.MAX_VIDEO_DOWNLOAD_BYTES = 2147483648
            mock_settings.DOWNLOAD_TOKEN_TTL = 3600

            mock_http = _mock_http_client()
            app = _make_test_app(mock_http)
            client = TestClient(app)

            _init_providers_sync(None, app.state.http_client)

            espaebook = torznab.registry.get("espaebook")
            espaebook.get_download_url = AsyncMock(
                return_value="https://example.com/book.epub"
            )

            response = client.get(
                "/api/download?provider=espaebook&id=123&fmt=epub&apikey=testkey"
            )
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/x-bittorrent"
            assert "attachment" in response.headers["content-disposition"]
            info_hash = parse_info_hash(response.content)
            assert len(info_hash) == 40
            assert all(c in "0123456789abcdef" for c in info_hash)

    @pytest.mark.asyncio
    async def test_download_provider_without_results(self):
        """Download with valid provider but no URL result should return error."""
        with patch("app.api.torznab.settings") as mock_settings:
            mock_settings.API_KEY = "testkey"
            mock_settings.EBOOKELO_ENABLED = False
            mock_settings.EPUBLIBRE_ENABLED = False
            mock_settings.LECTULANDIA_ENABLED = False
            mock_settings.ESPAEBOOK_ENABLED = True
            mock_settings.HOLAEBOOK_ENABLED = False
            mock_settings.ANNASARCHIVE_ENABLED = False
            mock_settings.MEJORTORRENT_ENABLED = False
            mock_settings.DONTORRENT_ENABLED = False
            mock_settings.ELEJANDRIA_ENABLED = False
            mock_settings.GUTENBERG_ENABLED = False
            mock_settings.EPUBFLIX1_ENABLED = False
            mock_settings.LIBGEN_ENABLED = False
            mock_settings.BOOOBOOK_ENABLED = False
            mock_settings.LECTUEPUBLIBRE5_ENABLED = False
            mock_settings.MUNDOEPUBLIBRE1_ENABLED = False
            mock_settings.ZLIBRARY_ENABLED = False
            mock_settings.RATE_LIMIT_PER_SECOND = 100.0
            mock_settings.MAX_RETRIES = 1
            mock_settings.REQUEST_TIMEOUT = 5
            mock_settings.HTTP_PROXY = ""
            mock_settings.CACHE_ENABLED = False
            mock_settings.CACHE_TTL_SECONDS = 300

            with patch("app.api.torznab.HttpClient") as mock_http_cls:
                mock_http = MagicMock()
                mock_http_cls.return_value = mock_http

                app = _make_test_app()
                client = TestClient(app)

                _init_providers_sync(None, app.state.http_client)
                response = client.get("/api/download?provider=ebookelo&id=999&fmt=epub&apikey=testkey")
                assert response.status_code == 200
                assert "error" in response.text.lower()

# ── search with cache ───────────────────────────────────────────────


class TestSearchWithCache:
    """Tests for search_with_cache internal logic (cache hit, timeout, error)."""

    @pytest.mark.asyncio
    async def test_search_cache_hit(self):
        """Should return cached results when cache hit occurs (lines 159-160)."""
        with patch("app.api.torznab.settings") as mock_settings:
            mock_settings.API_KEY = "testkey"
            mock_settings.EBOOKELO_ENABLED = True
            mock_settings.EPUBLIBRE_ENABLED = False
            mock_settings.LECTULANDIA_ENABLED = False
            mock_settings.ESPAEBOOK_ENABLED = False
            mock_settings.HOLAEBOOK_ENABLED = False
            mock_settings.ANNASARCHIVE_ENABLED = False
            mock_settings.MEJORTORRENT_ENABLED = False
            mock_settings.DONTORRENT_ENABLED = False
            mock_settings.ELEJANDRIA_ENABLED = False
            mock_settings.GUTENBERG_ENABLED = False
            mock_settings.EPUBFLIX1_ENABLED = False
            mock_settings.LIBGEN_ENABLED = False
            mock_settings.BOOOBOOK_ENABLED = False
            mock_settings.LECTUEPUBLIBRE5_ENABLED = False
            mock_settings.MUNDOEPUBLIBRE1_ENABLED = False
            mock_settings.ZLIBRARY_ENABLED = False
            mock_settings.RATE_LIMIT_PER_SECOND = 100.0
            mock_settings.MAX_RETRIES = 1
            mock_settings.REQUEST_TIMEOUT = 5
            mock_settings.HTTP_PROXY = ""
            mock_settings.CACHE_ENABLED = True
            mock_settings.CACHE_TTL_SECONDS = 300

            with patch("app.api.torznab.HttpClient") as mock_http_cls:
                mock_http = MagicMock()
                mock_http_cls.return_value = mock_http

                app = _make_test_app()
                client = TestClient(app)

                _init_providers_sync(None, app.state.http_client)

                # Pre-populate cache for ebookelo / query "test" / cat 8000
                from app.core.models import SearchResult
                cached = [
                    SearchResult(
                        title="Cached Book",
                        guid="ebookelo-cached-id",
                        link="http://example.com/book",
                        download_url="http://example.com/download",
                        categories=[8000],
                    )
                ]
                await torznab.search_cache.set("ebookelo", "test", cached, [8000], offset=0, limit=50)

                response = client.get(
                    "/api?t=search&q=test&apikey=testkey&cat=8000"
                )
                assert response.status_code == 200
                assert "<?xml" in response.text

    @pytest.mark.asyncio
    async def test_search_provider_timeout(self):
        """Should return empty list when provider times out (lines 171-173)."""
        with patch("app.api.torznab.settings") as mock_settings:
            mock_settings.API_KEY = "testkey"
            mock_settings.EBOOKELO_ENABLED = True
            mock_settings.EPUBLIBRE_ENABLED = False
            mock_settings.LECTULANDIA_ENABLED = False
            mock_settings.ESPAEBOOK_ENABLED = False
            mock_settings.HOLAEBOOK_ENABLED = False
            mock_settings.ANNASARCHIVE_ENABLED = False
            mock_settings.MEJORTORRENT_ENABLED = False
            mock_settings.DONTORRENT_ENABLED = False
            mock_settings.ELEJANDRIA_ENABLED = False
            mock_settings.GUTENBERG_ENABLED = False
            mock_settings.EPUBFLIX1_ENABLED = False
            mock_settings.LIBGEN_ENABLED = False
            mock_settings.BOOOBOOK_ENABLED = False
            mock_settings.LECTUEPUBLIBRE5_ENABLED = False
            mock_settings.MUNDOEPUBLIBRE1_ENABLED = False
            mock_settings.ZLIBRARY_ENABLED = False
            mock_settings.RATE_LIMIT_PER_SECOND = 100.0
            mock_settings.MAX_RETRIES = 1
            mock_settings.REQUEST_TIMEOUT = 5
            mock_settings.HTTP_PROXY = ""
            mock_settings.CACHE_ENABLED = False
            mock_settings.CACHE_TTL_SECONDS = 300

            with patch("app.api.torznab.HttpClient") as mock_http_cls:
                mock_http = MagicMock()
                mock_http_cls.return_value = mock_http

                app = _make_test_app()
                client = TestClient(app)

                _init_providers_sync(None, app.state.http_client)

                # Patch asyncio.wait_for to raise TimeoutError
                with patch("app.api.torznab.asyncio.wait_for",
                           new=AsyncMock(side_effect=asyncio.TimeoutError())):
                    response = client.get(
                        "/api?t=search&q=test&apikey=testkey&cat=8000"
                    )
                assert response.status_code == 200
                assert "<?xml" in response.text

    @pytest.mark.asyncio
    async def test_search_provider_exception(self):
        """Should return empty list when provider raises generic exception (lines 174-176)."""
        with patch("app.api.torznab.settings") as mock_settings:
            mock_settings.API_KEY = "testkey"
            mock_settings.EBOOKELO_ENABLED = True
            mock_settings.EPUBLIBRE_ENABLED = False
            mock_settings.LECTULANDIA_ENABLED = False
            mock_settings.ESPAEBOOK_ENABLED = False
            mock_settings.HOLAEBOOK_ENABLED = False
            mock_settings.ANNASARCHIVE_ENABLED = False
            mock_settings.MEJORTORRENT_ENABLED = False
            mock_settings.DONTORRENT_ENABLED = False
            mock_settings.ELEJANDRIA_ENABLED = False
            mock_settings.GUTENBERG_ENABLED = False
            mock_settings.EPUBFLIX1_ENABLED = False
            mock_settings.LIBGEN_ENABLED = False
            mock_settings.BOOOBOOK_ENABLED = False
            mock_settings.LECTUEPUBLIBRE5_ENABLED = False
            mock_settings.MUNDOEPUBLIBRE1_ENABLED = False
            mock_settings.ZLIBRARY_ENABLED = False
            mock_settings.RATE_LIMIT_PER_SECOND = 100.0
            mock_settings.MAX_RETRIES = 1
            mock_settings.REQUEST_TIMEOUT = 5
            mock_settings.HTTP_PROXY = ""
            mock_settings.CACHE_ENABLED = False
            mock_settings.CACHE_TTL_SECONDS = 300

            with patch("app.api.torznab.HttpClient") as mock_http_cls:
                mock_http = MagicMock()
                mock_http_cls.return_value = mock_http

                app = _make_test_app()
                client = TestClient(app)

                _init_providers_sync(None, app.state.http_client)

                # Patch asyncio.wait_for to raise generic Exception
                with patch("app.api.torznab.asyncio.wait_for",
                           new=AsyncMock(side_effect=Exception("Unexpected error"))):
                    response = client.get(
                        "/api?t=search&q=test&apikey=testkey&cat=8000"
                    )
                assert response.status_code == 200
                assert "<?xml" in response.text


# ── utility functions ──────────────────────────────────────────────


class TestUtilityFunctions:
    """Tests for internal utility functions in torznab.py."""

    def test_init_providers_with_enabled(self):
        """_init_providers should register enabled providers."""
        torznab.registry.clear()
        with patch("app.api.torznab.settings") as mock_settings:
            mock_settings.EBOOKELO_ENABLED = True
            mock_settings.EPUBLIBRE_ENABLED = True
            mock_settings.LECTULANDIA_ENABLED = True
            mock_settings.ESPAEBOOK_ENABLED = True
            mock_settings.HOLAEBOOK_ENABLED = True
            mock_settings.ANNASARCHIVE_ENABLED = True
            mock_settings.MEJORTORRENT_ENABLED = True
            mock_settings.DONTORRENT_ENABLED = True
            mock_settings.ELEJANDRIA_ENABLED = True
            mock_settings.GUTENBERG_ENABLED = True
            mock_settings.EPUBFLIX1_ENABLED = True
            mock_settings.LIBGEN_ENABLED = True
            mock_settings.BOOOBOOK_ENABLED = True
            mock_settings.LECTUEPUBLIBRE5_ENABLED = True
            mock_settings.MUNDOEPUBLIBRE1_ENABLED = True
            mock_settings.ZLIBRARY_ENABLED = True
            mock_settings.RATE_LIMIT_PER_SECOND = 100.0
            mock_settings.MAX_RETRIES = 1
            mock_settings.REQUEST_TIMEOUT = 5
            mock_settings.HTTP_PROXY = ""
            mock_settings.CACHE_ENABLED = False
            mock_settings.CACHE_TTL_SECONDS = 300

            with patch("app.api.torznab.HttpClient"):
                _init_providers_sync(None, _mock_http_client())
                providers = torznab.registry.get_all()
                # Eligible providers: ebookelo, epublibre, lectulandia, espaebook,
                # holaebook, annasarchive, mejortorrent, dontorrent = 8
                # There are also elejandria and gutenberg but they just log warnings
                assert len(providers) >= 8

    def test_parse_cats_empty(self):
        """_parse_cats should return empty list for empty string."""
        assert torznab._parse_cats("") == []

    def test_parse_cats_valid(self):
        """_parse_cats should parse comma-separated categories."""
        result = torznab._parse_cats("2000,8000,5000")
        assert result == [2000, 8000, 5000]

    def test_parse_cats_with_invalid(self):
        """_parse_cats should skip non-digit values."""
        result = torznab._parse_cats("2000,abc,5000")
        assert result == [2000, 5000]

    def test_validate_apikey_correct(self):
        """validate_apikey should return True for correct key."""
        from app.api.auth import validate_apikey
        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.API_KEY = "secret"
            assert validate_apikey("secret") is True

    def test_validate_apikey_wrong(self):
        """validate_apikey should return False for wrong key."""
        from app.api.auth import validate_apikey
        with patch("app.api.auth.settings") as mock_settings:
            mock_settings.API_KEY = "secret"
            assert validate_apikey("wrong") is False


# ── single-provider endpoint (/api/{provider_id}) ──────────────────


class TestSingleProviderEndpoint:
    """Tests for the /api/{provider_id} multi-indexer endpoint."""

    def test_caps_without_apikey_returns_provider_caps(self):
        """t=caps without API key should return caps for a valid provider."""
        with patch("app.api.torznab.settings") as mock_settings:
            mock_settings.API_KEY = "testkey"
            mock_settings.EBOOKELO_ENABLED = True
            mock_settings.EPUBLIBRE_ENABLED = False
            mock_settings.LECTULANDIA_ENABLED = False
            mock_settings.ESPAEBOOK_ENABLED = False
            mock_settings.HOLAEBOOK_ENABLED = False
            mock_settings.ANNASARCHIVE_ENABLED = False
            mock_settings.MEJORTORRENT_ENABLED = False
            mock_settings.DONTORRENT_ENABLED = False
            mock_settings.ELEJANDRIA_ENABLED = False
            mock_settings.GUTENBERG_ENABLED = False
            mock_settings.EPUBFLIX1_ENABLED = False
            mock_settings.LIBGEN_ENABLED = False
            mock_settings.BOOOBOOK_ENABLED = False
            mock_settings.LECTUEPUBLIBRE5_ENABLED = False
            mock_settings.MUNDOEPUBLIBRE1_ENABLED = False
            mock_settings.ZLIBRARY_ENABLED = False
            mock_settings.RATE_LIMIT_PER_SECOND = 100.0
            mock_settings.MAX_RETRIES = 1
            mock_settings.REQUEST_TIMEOUT = 5
            mock_settings.HTTP_PROXY = ""
            mock_settings.CACHE_ENABLED = False
            mock_settings.CACHE_TTL_SECONDS = 300
            mock_settings.EXTERNAL_URL = "http://localhost:9811"

            with patch("app.api.torznab.HttpClient") as mock_http_cls:
                mock_http = MagicMock()
                mock_http_cls.return_value = mock_http

                app = _make_test_app()
                client = TestClient(app)

                _init_providers_sync(None, app.state.http_client)
                response = client.get("/api/ebookelo?t=caps&apikey=wrong")
                assert response.status_code == 200
                assert "<?xml" in response.text
                assert "caps" in response.text.lower()
                assert "book-search" in response.text
                # Should include provider display name in title
                assert "WebTranslatorr - Ebookelo" in response.text

    def test_caps_with_valid_key_has_provider_name(self):
        """t=caps with valid key should include display_name and provider URL."""
        with patch("app.api.torznab.settings") as mock_settings:
            mock_settings.API_KEY = "testkey"
            mock_settings.EBOOKELO_ENABLED = True
            mock_settings.EPUBLIBRE_ENABLED = False
            mock_settings.LECTULANDIA_ENABLED = False
            mock_settings.ESPAEBOOK_ENABLED = False
            mock_settings.HOLAEBOOK_ENABLED = False
            mock_settings.ANNASARCHIVE_ENABLED = False
            mock_settings.MEJORTORRENT_ENABLED = False
            mock_settings.DONTORRENT_ENABLED = False
            mock_settings.ELEJANDRIA_ENABLED = False
            mock_settings.GUTENBERG_ENABLED = False
            mock_settings.EPUBFLIX1_ENABLED = False
            mock_settings.LIBGEN_ENABLED = False
            mock_settings.BOOOBOOK_ENABLED = False
            mock_settings.LECTUEPUBLIBRE5_ENABLED = False
            mock_settings.MUNDOEPUBLIBRE1_ENABLED = False
            mock_settings.ZLIBRARY_ENABLED = False
            mock_settings.RATE_LIMIT_PER_SECOND = 100.0
            mock_settings.MAX_RETRIES = 1
            mock_settings.REQUEST_TIMEOUT = 5
            mock_settings.HTTP_PROXY = ""
            mock_settings.CACHE_ENABLED = False
            mock_settings.CACHE_TTL_SECONDS = 300
            mock_settings.EXTERNAL_URL = "http://localhost:9811"

            with patch("app.api.torznab.HttpClient") as mock_http_cls:
                mock_http = MagicMock()
                mock_http_cls.return_value = mock_http

                app = _make_test_app()
                client = TestClient(app)

                _init_providers_sync(None, app.state.http_client)
                response = client.get("/api/ebookelo?t=caps&apikey=testkey")
                assert response.status_code == 200
                assert "WebTranslatorr - Ebookelo" in response.text
                # Server URL should point to provider-specific path
                assert "/api/ebookelo" in response.text

    def test_caps_unknown_provider_returns_error(self):
        """t=caps without valid key on unknown provider should return error 100."""
        with patch("app.api.torznab.settings") as mock_settings:
            mock_settings.API_KEY = "testkey"
            mock_settings.EBOOKELO_ENABLED = False
            mock_settings.EPUBLIBRE_ENABLED = False
            mock_settings.LECTULANDIA_ENABLED = False
            mock_settings.ESPAEBOOK_ENABLED = False
            mock_settings.HOLAEBOOK_ENABLED = False
            mock_settings.ANNASARCHIVE_ENABLED = False
            mock_settings.MEJORTORRENT_ENABLED = False
            mock_settings.DONTORRENT_ENABLED = False
            mock_settings.ELEJANDRIA_ENABLED = False
            mock_settings.GUTENBERG_ENABLED = False
            mock_settings.EPUBFLIX1_ENABLED = False
            mock_settings.LIBGEN_ENABLED = False
            mock_settings.BOOOBOOK_ENABLED = False
            mock_settings.LECTUEPUBLIBRE5_ENABLED = False
            mock_settings.MUNDOEPUBLIBRE1_ENABLED = False
            mock_settings.ZLIBRARY_ENABLED = False
            mock_settings.RATE_LIMIT_PER_SECOND = 100.0
            mock_settings.MAX_RETRIES = 1
            mock_settings.REQUEST_TIMEOUT = 5
            mock_settings.HTTP_PROXY = ""

            app = _make_test_app()
            client = TestClient(app)

            _init_providers_sync(None, app.state.http_client)
            response = client.get("/api/nonexistent?t=caps&apikey=wrong")
            assert response.status_code == 200
            assert "error" in response.text.lower()

    def test_search_returns_error_with_wrong_key(self):
        """Search on single provider with wrong API key should return error."""
        with patch("app.api.torznab.settings") as mock_settings:
            mock_settings.API_KEY = "testkey"
            mock_settings.EBOOKELO_ENABLED = True
            mock_settings.EPUBLIBRE_ENABLED = False
            mock_settings.LECTULANDIA_ENABLED = False
            mock_settings.ESPAEBOOK_ENABLED = False
            mock_settings.HOLAEBOOK_ENABLED = False
            mock_settings.ANNASARCHIVE_ENABLED = False
            mock_settings.MEJORTORRENT_ENABLED = False
            mock_settings.DONTORRENT_ENABLED = False
            mock_settings.ELEJANDRIA_ENABLED = False
            mock_settings.GUTENBERG_ENABLED = False
            mock_settings.EPUBFLIX1_ENABLED = False
            mock_settings.LIBGEN_ENABLED = False
            mock_settings.BOOOBOOK_ENABLED = False
            mock_settings.LECTUEPUBLIBRE5_ENABLED = False
            mock_settings.MUNDOEPUBLIBRE1_ENABLED = False
            mock_settings.ZLIBRARY_ENABLED = False
            mock_settings.RATE_LIMIT_PER_SECOND = 100.0
            mock_settings.MAX_RETRIES = 1
            mock_settings.REQUEST_TIMEOUT = 5
            mock_settings.HTTP_PROXY = ""
            mock_settings.CACHE_ENABLED = False
            mock_settings.CACHE_TTL_SECONDS = 300

            with patch("app.api.torznab.HttpClient") as mock_http_cls:
                mock_http = MagicMock()
                mock_http_cls.return_value = mock_http

                app = _make_test_app()
                client = TestClient(app)

                _init_providers_sync(None, app.state.http_client)
                response = client.get(
                    "/api/ebookelo?t=search&q=test&apikey=wrong"
                )
                assert response.status_code == 200
                assert "error" in response.text.lower()

    def test_search_unknown_provider_returns_error(self):
        """Search on unknown provider should return error XML."""
        with patch("app.api.torznab.settings") as mock_settings:
            mock_settings.API_KEY = "testkey"
            mock_settings.EBOOKELO_ENABLED = False
            mock_settings.EPUBLIBRE_ENABLED = False
            mock_settings.LECTULANDIA_ENABLED = False
            mock_settings.ESPAEBOOK_ENABLED = False
            mock_settings.HOLAEBOOK_ENABLED = False
            mock_settings.ANNASARCHIVE_ENABLED = False
            mock_settings.MEJORTORRENT_ENABLED = False
            mock_settings.DONTORRENT_ENABLED = False
            mock_settings.ELEJANDRIA_ENABLED = False
            mock_settings.GUTENBERG_ENABLED = False
            mock_settings.EPUBFLIX1_ENABLED = False
            mock_settings.LIBGEN_ENABLED = False
            mock_settings.BOOOBOOK_ENABLED = False
            mock_settings.LECTUEPUBLIBRE5_ENABLED = False
            mock_settings.MUNDOEPUBLIBRE1_ENABLED = False
            mock_settings.ZLIBRARY_ENABLED = False
            mock_settings.RATE_LIMIT_PER_SECOND = 100.0
            mock_settings.MAX_RETRIES = 1
            mock_settings.REQUEST_TIMEOUT = 5
            mock_settings.HTTP_PROXY = ""

            app = _make_test_app()
            client = TestClient(app)

            _init_providers_sync(None, app.state.http_client)
            response = client.get(
                "/api/nonexistent?t=search&q=test&apikey=testkey"
            )
            assert response.status_code == 200
            assert "error" in response.text.lower()

    def test_aggregate_caps_title_is_generic(self):
        """Aggregate /api?t=caps should still show 'WebTranslatorr' without provider name."""
        with patch("app.api.torznab.settings") as mock_settings:
            mock_settings.API_KEY = "testkey"
            mock_settings.EBOOKELO_ENABLED = True
            mock_settings.EPUBLIBRE_ENABLED = False
            mock_settings.LECTULANDIA_ENABLED = False
            mock_settings.ESPAEBOOK_ENABLED = False
            mock_settings.HOLAEBOOK_ENABLED = False
            mock_settings.ANNASARCHIVE_ENABLED = False
            mock_settings.MEJORTORRENT_ENABLED = False
            mock_settings.DONTORRENT_ENABLED = False
            mock_settings.ELEJANDRIA_ENABLED = False
            mock_settings.GUTENBERG_ENABLED = False
            mock_settings.EPUBFLIX1_ENABLED = False
            mock_settings.LIBGEN_ENABLED = False
            mock_settings.BOOOBOOK_ENABLED = False
            mock_settings.LECTUEPUBLIBRE5_ENABLED = False
            mock_settings.MUNDOEPUBLIBRE1_ENABLED = False
            mock_settings.ZLIBRARY_ENABLED = False
            mock_settings.RATE_LIMIT_PER_SECOND = 100.0
            mock_settings.MAX_RETRIES = 1
            mock_settings.REQUEST_TIMEOUT = 5
            mock_settings.HTTP_PROXY = ""
            mock_settings.CACHE_ENABLED = False
            mock_settings.CACHE_TTL_SECONDS = 300
            mock_settings.EXTERNAL_URL = "http://localhost:9811"

            with patch("app.api.torznab.HttpClient") as mock_http_cls:
                mock_http = MagicMock()
                mock_http_cls.return_value = mock_http

                app = _make_test_app()
                client = TestClient(app)

                _init_providers_sync(None, app.state.http_client)
                response = client.get("/api?t=caps&apikey=testkey")
                assert response.status_code == 200
                assert "WebTranslatorr" in response.text
                # Aggregate caps should NOT include provider name
                assert "WebTranslatorr -" not in response.text


class TestVideoDownload:
    @pytest.mark.asyncio
    async def test_video_download_accepts_fmt_kwarg(self):
        with patch("app.api.torznab.settings") as mock_settings:
            mock_settings.API_KEY = "testkey"
            mock_settings.EBOOKELO_ENABLED = False
            mock_settings.EPUBLIBRE_ENABLED = False
            mock_settings.LECTULANDIA_ENABLED = False
            mock_settings.ESPAEBOOK_ENABLED = False
            mock_settings.HOLAEBOOK_ENABLED = False
            mock_settings.ANNASARCHIVE_ENABLED = False
            mock_settings.MEJORTORRENT_ENABLED = True
            mock_settings.DONTORRENT_ENABLED = False
            mock_settings.ELEJANDRIA_ENABLED = False
            mock_settings.GUTENBERG_ENABLED = False
            mock_settings.EPUBFLIX1_ENABLED = False
            mock_settings.LIBGEN_ENABLED = False
            mock_settings.BOOOBOOK_ENABLED = False
            mock_settings.LECTUEPUBLIBRE5_ENABLED = False
            mock_settings.MUNDOEPUBLIBRE1_ENABLED = False
            mock_settings.ZLIBRARY_ENABLED = False
            mock_settings.RATE_LIMIT_PER_SECOND = 100.0
            mock_settings.MAX_RETRIES = 1
            mock_settings.REQUEST_TIMEOUT = 5
            mock_settings.HTTP_PROXY = ""
            mock_settings.CACHE_ENABLED = False
            mock_settings.CACHE_TTL_SECONDS = 300
            mock_settings.MAX_DOWNLOAD_BYTES = 524288000
            mock_settings.MAX_VIDEO_DOWNLOAD_BYTES = 2147483648

            mock_http = _mock_http_client()
            app = _make_test_app(mock_http)
            client = TestClient(app)
            _init_providers_sync(None, app.state.http_client)

            provider = torznab.registry.get("mejortorrent")
            provider.get_download_url = AsyncMock(return_value="https://example.com/movie.torrent")

            response = client.get(
                "/api/download?provider=mejortorrent&id=https://example.com/movie.torrent"
                "&fmt=torrent&apikey=testkey"
            )
            assert response.status_code == 200
            provider.get_download_url.assert_awaited_once_with(
                "https://example.com/movie.torrent", fmt="torrent"
            )
