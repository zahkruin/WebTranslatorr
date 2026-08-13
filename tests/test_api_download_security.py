"""
Security tests for download endpoints.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import torznab
from app.scraping.http_client import HttpClient


@pytest.fixture
def mock_http_client():
    client = MagicMock(spec=HttpClient)
    async def _download_file(*args, **kwargs):
        return b"torrent-bytes"
    client.download_file = _download_file
    return client


@pytest.fixture
def test_app(mock_http_client):
    app = FastAPI()
    app.state.http_client = mock_http_client
    app.include_router(torznab.router)
    return app


def _enable_minimal_providers(mock_settings):
    mock_settings.API_KEY = "testkey"
    mock_settings.EBOOKELO_ENABLED = False
    mock_settings.EPUBLIBRE_ENABLED = False
    mock_settings.LECTULANDIA_ENABLED = False
    mock_settings.ESPAEBOOK_ENABLED = True
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
    mock_settings.BOOKSEE_ENABLED = False
    mock_settings.OCEANOFPDF_ENABLED = False
    mock_settings.LELIBROS_ENABLED = False
    mock_settings.BAJAEEBOOKS_ENABLED = False
    mock_settings.EBIBLIOTECA_ENABLED = False
    mock_settings.EPUBGRATIS_ENABLED = False
    mock_settings.DIVXTOTAL_ENABLED = False
    mock_settings.ELITETORRENT_ENABLED = False
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


class TestDownloadSecurity:
    def test_download_without_apikey_returns_401(self, test_app, mock_http_client):
        with patch("app.api.torznab.settings") as mock_settings:
            _enable_minimal_providers(mock_settings)
            _init_providers_sync(None, mock_http_client)
            client = TestClient(test_app)
            response = client.get("/api/download?provider=mejortorrent&id=http://x.torrent")
            assert response.status_code == 200
            assert "error" in response.text.lower()

    def test_download_content_without_token_returns_401(self, test_app, mock_http_client):
        with patch("app.api.torznab.settings") as mock_settings:
            _enable_minimal_providers(mock_settings)
            _init_providers_sync(None, mock_http_client)
            client = TestClient(test_app)
            response = client.get("/api/download-content?provider=espaebook&id=123&fmt=epub")
            assert response.status_code == 200
            assert "error" in response.text.lower()

    def test_download_content_with_valid_token(self, test_app, mock_http_client):
        with patch("app.api.torznab.settings") as mock_settings:
            _enable_minimal_providers(mock_settings)
            _init_providers_sync(None, mock_http_client)

            espaebook = torznab.registry.get("espaebook")
            async def _get_download_url(*args, **kwargs):
                return "https://example.com/book.epub"
            espaebook.get_download_url = _get_download_url

            from app.services.download_tokens import build_download_content_url
            url = build_download_content_url("espaebook", "123", "epub")
            token = url.split("token=")[1]

            client = TestClient(test_app)
            response = client.get(
                f"/api/download-content?provider=espaebook&id=123&fmt=epub&token={token}"
            )
            assert response.status_code == 200
            assert response.content == b"torrent-bytes"
