"""
Tests for the FastAPI application factory (server.py).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.version import get_version
from app.server import create_app


class _CancellableTask:
    """Mock task that simulates asyncio.Task cancellation behavior.

    The lifespan shutdown at app/server.py:116-120 does:
        check_task.cancel()
        try:
            await check_task
        except asyncio.CancelledError:
            pass

    A plain AsyncMock() cannot be awaited after cancel() in Python 3.13,
    so this class provides the expected contract.
    """

    def __init__(self):
        self._cancelled = False
        self.cancel = MagicMock(side_effect=self._do_cancel)

    def _do_cancel(self):
        self._cancelled = True
        return True

    def __await__(self):
        return self._await_impl().__await__()

    async def _await_impl(self):
        if self._cancelled:
            raise asyncio.CancelledError()


class TestCreateApp:
    """Tests for the create_app factory function."""

    def test_returns_fastapi_app(self):
        """create_app should return a FastAPI instance."""
        app = create_app()
        assert app.title == "WebTranslatorr"
        assert app.version == get_version()

    def test_has_health_route(self):
        """The app should have the /health endpoint registered."""
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_has_torznab_route(self):
        """The app should have the /api endpoint registered."""
        app = create_app()
        client = TestClient(app)
        response = client.get("/api?t=caps&apikey=changeme")
        # Should respond (either caps XML or error XML)
        assert response.status_code == 200
        assert "<?xml" in response.text

    def test_cors_middleware_configured(self):
        """CORS middleware should allow all origins."""
        app = create_app()
        client = TestClient(app)
        response = client.options(
            "/health",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        # With allow_credentials=True and allow_origins=["*"],
        # the middleware reflects the request Origin back
        origin = response.headers.get("access-control-allow-origin")
        assert origin in ("*", "http://example.com")
        assert response.headers.get("access-control-allow-methods") is not None


class TestLifespan:
    """Tests for the lifespan startup/shutdown cycle."""

    def test_lifespan_startup_creates_http_client_and_resolver(self):
        """Lifespan startup should create HttpClient and DomainResolver."""
        mock_http = AsyncMock()
        mock_resolver = MagicMock()
        mock_resolver.resolve_all = AsyncMock(
            return_value={"mejortorrent": "https://domain.com"}
        )
        mock_task = _CancellableTask()
        mock_config = MagicMock()
        mock_config.get_all_enabled_providers = AsyncMock(
            return_value=[
                {
                    "provider_id": "mejortorrent",
                    "enabled": True,
                    "domain": "",
                    "display_name": "MejorTorrent",
                }
            ]
        )

        with (
            patch("app.server.init_db", new_callable=AsyncMock),
            patch("app.server.ConfigManager", return_value=mock_config),
            patch("app.server.HttpClient", return_value=mock_http) as mock_http_cls,
            patch("app.server.DomainResolver", return_value=mock_resolver) as mock_resolver_cls,
            patch("app.server.torznab._init_providers", new_callable=AsyncMock),
            patch("app.server.domain_check_loop", new=MagicMock()),
            patch("app.services.blackhole_watcher.start_blackhole_watcher", return_value=None),
            patch("app.server.asyncio.create_task", return_value=mock_task) as mock_create_task,
            patch("app.services.translation_pipeline.get_translation_pipeline", new_callable=AsyncMock, return_value=None),
            patch("app.services.translation_pipeline.shutdown_translation_pipeline", new_callable=AsyncMock),
        ):
            app = create_app()

            with TestClient(app) as client:
                response = client.get("/health")
                assert response.status_code == 200

            mock_http_cls.assert_called_once()
            mock_resolver_cls.assert_called_once()
            assert mock_resolver.register_provider.call_count > 0
            mock_resolver.resolve_all.assert_awaited_once()
            assert mock_create_task.call_count >= 1

            mock_task.cancel.assert_called()
            mock_http.close.assert_awaited_once()

    def test_lifespan_disabled_providers_not_registered(self):
        """Lifespan should only register enabled providers from ConfigManager."""
        mock_config = MagicMock()
        mock_config.get_all_enabled_providers = AsyncMock(return_value=[])

        with (
            patch("app.server.init_db", new_callable=AsyncMock),
            patch("app.server.ConfigManager", return_value=mock_config),
            patch("app.server.HttpClient") as mock_http_cls,
            patch("app.server.DomainResolver") as mock_resolver_cls,
            patch("app.server.torznab._init_providers", new_callable=AsyncMock),
            patch("app.server.domain_check_loop", new=MagicMock()),
            patch("app.server.asyncio.create_task") as mock_create_task,
            patch("app.services.blackhole_watcher.start_blackhole_watcher", return_value=None),
            patch("app.services.translation_pipeline.get_translation_pipeline", new_callable=AsyncMock, return_value=None),
            patch("app.services.translation_pipeline.shutdown_translation_pipeline", new_callable=AsyncMock),
            patch("app.server.settings") as mock_settings,
        ):
            mock_http = AsyncMock()
            mock_http_cls.return_value = mock_http

            mock_resolver = MagicMock()
            mock_resolver_cls.return_value = mock_resolver
            mock_resolver.resolve_all = AsyncMock(return_value={})

            mock_task = _CancellableTask()
            mock_create_task.return_value = mock_task

            mock_settings.LOG_LEVEL = "INFO"
            mock_settings.ENV = "development"
            mock_settings.ENABLE_DOCS = True
            mock_settings.CORS_ORIGINS = "*"
            mock_settings.EXTERNAL_URL = "http://localhost:9811"
            mock_settings.RATE_LIMIT_PER_SECOND = 2.0
            mock_settings.MAX_RETRIES = 3
            mock_settings.REQUEST_TIMEOUT = 30
            mock_settings.HTTP_PROXY = ""
            mock_settings.DOMAIN_VALIDATION_TIMEOUT = 10
            mock_settings.DOMAIN_CHECK_INTERVAL = 1800

            app = create_app()
            with TestClient(app) as client:
                response = client.get("/health")
                assert response.status_code == 200

            assert mock_resolver.register_provider.call_count == 0