"""
Tests para el sistema de resolución dinámica de dominios.

Cubre:
- Estrategias individuales (privtree, telegram, healthcheck)
- DomainResolver con fallback entre estrategias
- Persistencia en JSON
- Health checks
"""

import json
import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from app.services.domain_strategies import (
    DomainConfig,
    PrivtreeStrategy,
    TelegramPublicStrategy,
    HealthCheckStrategy,
)
from app.services.domain_resolver import DomainResolver, ResolvedDomain


# --- Fixtures ---

@pytest.fixture
def mejortorrent_config():
    return DomainConfig(
        provider_id="mejortorrent",
        default_domain="https://www42.mejortorrent.eu",
        privtree_path="@mejortorrent",
        telegram_channel="MejorTorrentAp",
        known_domain_pattern=r"mejortorrent\.\w+",
    )


@pytest.fixture
def dontorrent_config():
    return DomainConfig(
        provider_id="dontorrent",
        default_domain="https://dontorrent.reisen",
        privtree_path="@dontorrent",
        telegram_channel="DonTorrent",
        known_domain_pattern=r"dontorrent\.\w+",
    )


@pytest.fixture
def mock_http_client():
    client = AsyncMock()
    return client


@pytest.fixture
def tmp_persistence(tmp_path):
    return str(tmp_path / "domains.json")


# --- Privtree Strategy Tests ---

class TestPrivtreeStrategy:
    """Tests para la estrategia de scraping de privtr.ee."""

    PRIVTREE_MT_HTML = """
    <html><body>
        <h1>MejorTorrent</h1>
        <p>Añade esta web a favoritos</p>
        <a href="https://www42.mejortorrent.eu/inicio">www42.mejortorrent.eu</a>
        <a href="https://t.me/s/MejorTorrentAp">MejorTorrent (Oficial)</a>
    </body></html>
    """

    PRIVTREE_DT_HTML = """
    <html><body>
        <h1>DonTorrent</h1>
        <a href="https://dontorrent.reisen">Dominio Actual</a>
        <a href="https://donproxies.com/">Proxy de DonTorrent</a>
    </body></html>
    """

    @pytest.mark.asyncio
    async def test_resolves_mejortorrent(self, mejortorrent_config, mock_http_client):
        mock_http_client.get.return_value = MagicMock(text=self.PRIVTREE_MT_HTML)
        strategy = PrivtreeStrategy()

        result = await strategy.resolve(mejortorrent_config, mock_http_client)

        assert result == "https://www42.mejortorrent.eu"
        mock_http_client.get.assert_called_once_with("https://privtr.ee/@mejortorrent")

    @pytest.mark.asyncio
    async def test_resolves_dontorrent(self, dontorrent_config, mock_http_client):
        mock_http_client.get.return_value = MagicMock(text=self.PRIVTREE_DT_HTML)
        strategy = PrivtreeStrategy()

        result = await strategy.resolve(dontorrent_config, mock_http_client)

        assert result == "https://dontorrent.reisen"

    @pytest.mark.asyncio
    async def test_returns_none_on_no_match(self, mejortorrent_config, mock_http_client):
        mock_http_client.get.return_value = MagicMock(text="<html><body>Nothing here</body></html>")
        strategy = PrivtreeStrategy()

        result = await strategy.resolve(mejortorrent_config, mock_http_client)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self, mejortorrent_config, mock_http_client):
        mock_http_client.get.side_effect = Exception("Connection refused")
        strategy = PrivtreeStrategy()

        result = await strategy.resolve(mejortorrent_config, mock_http_client)

        assert result is None

    @pytest.mark.asyncio
    async def test_skips_when_no_privtree_path(self, mock_http_client):
        config = DomainConfig(
            provider_id="test",
            default_domain="https://example.com",
            privtree_path=None,
        )
        strategy = PrivtreeStrategy()

        result = await strategy.resolve(config, mock_http_client)

        assert result is None
        mock_http_client.get.assert_not_called()


# --- Telegram Strategy Tests ---

class TestTelegramStrategy:
    """Tests para la estrategia de scraping del canal público de Telegram."""

    TELEGRAM_DT_HTML = """
    <html><body>
        <div class="tgme_widget_message_wrap">
            <div class="tgme_widget_message_text">
                <a href="https://dontorrent.pink/">https://dontorrent.pink</a>
            </div>
        </div>
        <div class="tgme_widget_message_wrap">
            <div class="tgme_widget_message_text">
                <a href="https://dontorrent.reisen/">https://dontorrent.reisen</a>
            </div>
        </div>
    </body></html>
    """

    TELEGRAM_MT_HTML = """
    <html><body>
        <div class="tgme_widget_message_wrap">
            <div class="tgme_widget_message_text">
                <a href="https://www42.mejortorrent.eu/inicio">https://www42.mejortorrent.eu/inicio</a>
            </div>
        </div>
    </body></html>
    """

    @pytest.mark.asyncio
    async def test_resolves_last_message_dontorrent(self, dontorrent_config, mock_http_client):
        mock_http_client.get.return_value = MagicMock(text=self.TELEGRAM_DT_HTML)
        strategy = TelegramPublicStrategy()

        result = await strategy.resolve(dontorrent_config, mock_http_client)

        # Should pick the LAST message (dontorrent.reisen)
        assert result == "https://dontorrent.reisen"

    @pytest.mark.asyncio
    async def test_resolves_mejortorrent(self, mejortorrent_config, mock_http_client):
        mock_http_client.get.return_value = MagicMock(text=self.TELEGRAM_MT_HTML)
        strategy = TelegramPublicStrategy()

        result = await strategy.resolve(mejortorrent_config, mock_http_client)

        assert result == "https://www42.mejortorrent.eu"

    @pytest.mark.asyncio
    async def test_fallback_parse_when_no_message_wrap(self, dontorrent_config, mock_http_client):
        """Si la estructura de Telegram cambia, debería buscar en todo el HTML."""
        html_no_wraps = """
        <html><body>
            <a href="https://dontorrent.club/">https://dontorrent.club</a>
            <a href="https://dontorrent.reisen/">https://dontorrent.reisen</a>
        </body></html>
        """
        mock_http_client.get.return_value = MagicMock(text=html_no_wraps)
        strategy = TelegramPublicStrategy()

        result = await strategy.resolve(dontorrent_config, mock_http_client)

        # Fallback picks last match
        assert result == "https://dontorrent.reisen"

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self, dontorrent_config, mock_http_client):
        mock_http_client.get.side_effect = Exception("Network error")
        strategy = TelegramPublicStrategy()

        result = await strategy.resolve(dontorrent_config, mock_http_client)

        assert result is None

    @pytest.mark.asyncio
    async def test_skips_when_no_channel(self, mock_http_client):
        config = DomainConfig(
            provider_id="test",
            default_domain="https://example.com",
            telegram_channel=None,
        )
        strategy = TelegramPublicStrategy()

        result = await strategy.resolve(config, mock_http_client)

        assert result is None


# --- HealthCheck Strategy Tests ---

class TestHealthCheckStrategy:
    """Tests para la estrategia de health check."""

    @pytest.mark.asyncio
    async def test_returns_domain_when_healthy(self, mejortorrent_config, mock_http_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://www42.mejortorrent.eu/"
        mock_http_client.head.return_value = mock_response
        strategy = HealthCheckStrategy()

        result = await strategy.resolve(mejortorrent_config, mock_http_client)

        assert result == "https://www42.mejortorrent.eu"

    @pytest.mark.asyncio
    async def test_follows_redirect(self, mejortorrent_config, mock_http_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://www43.mejortorrent.eu/inicio"
        mock_http_client.head.return_value = mock_response
        strategy = HealthCheckStrategy()

        result = await strategy.resolve(mejortorrent_config, mock_http_client)

        assert result == "https://www43.mejortorrent.eu"

    @pytest.mark.asyncio
    async def test_returns_none_on_4xx(self, mejortorrent_config, mock_http_client):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_http_client.head.return_value = mock_response
        strategy = HealthCheckStrategy()

        result = await strategy.resolve(mejortorrent_config, mock_http_client)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_connection_error(self, mejortorrent_config, mock_http_client):
        mock_http_client.head.side_effect = Exception("Connection refused")
        strategy = HealthCheckStrategy()

        result = await strategy.resolve(mejortorrent_config, mock_http_client)

        assert result is None


# --- DomainResolver Tests ---

class TestDomainResolver:
    """Tests para el orquestador central de resolución."""

    @pytest.mark.asyncio
    async def test_resolve_uses_first_successful_strategy(self, mock_http_client, mejortorrent_config, tmp_persistence):
        strategy1 = AsyncMock(spec=PrivtreeStrategy)
        strategy1.name = "strategy1"
        strategy1.resolve.return_value = "https://www42.mejortorrent.eu"

        strategy2 = AsyncMock(spec=TelegramPublicStrategy)
        strategy2.name = "strategy2"

        resolver = DomainResolver(
            http_client=mock_http_client,
            strategies=[strategy1, strategy2],
            persistence_path=tmp_persistence,
        )
        resolver.register_provider(mejortorrent_config)

        # Mock validation
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_http_client.head.return_value = mock_response

        result = await resolver.resolve("mejortorrent")

        assert result == "https://www42.mejortorrent.eu"
        strategy1.resolve.assert_called_once()
        strategy2.resolve.assert_not_called()  # Shouldn't be reached

    @pytest.mark.asyncio
    async def test_fallback_to_second_strategy(self, mock_http_client, mejortorrent_config, tmp_persistence):
        strategy1 = AsyncMock()
        strategy1.name = "strategy1"
        strategy1.resolve.return_value = None  # Fails

        strategy2 = AsyncMock()
        strategy2.name = "strategy2"
        strategy2.resolve.return_value = "https://www42.mejortorrent.eu"

        resolver = DomainResolver(
            http_client=mock_http_client,
            strategies=[strategy1, strategy2],
            persistence_path=tmp_persistence,
        )
        resolver.register_provider(mejortorrent_config)

        # Mock validation
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_http_client.head.return_value = mock_response

        result = await resolver.resolve("mejortorrent")

        assert result == "https://www42.mejortorrent.eu"
        strategy1.resolve.assert_called_once()
        strategy2.resolve.assert_called_once()

    @pytest.mark.asyncio
    async def test_keeps_last_known_when_all_fail(self, mock_http_client, mejortorrent_config, tmp_persistence):
        strategy1 = AsyncMock()
        strategy1.name = "strategy1"
        strategy1.resolve.return_value = None

        resolver = DomainResolver(
            http_client=mock_http_client,
            strategies=[strategy1],
            persistence_path=tmp_persistence,
        )
        resolver.register_provider(mejortorrent_config)

        result = await resolver.resolve("mejortorrent")

        # Should fall back to default config domain
        assert result == "https://www42.mejortorrent.eu"

    @pytest.mark.asyncio
    async def test_skips_invalid_candidate(self, mock_http_client, mejortorrent_config, tmp_persistence):
        """If a strategy returns a domain but validation fails, try next."""
        strategy1 = AsyncMock()
        strategy1.name = "strategy1"
        strategy1.resolve.return_value = "https://fake.mejortorrent.xyz"

        strategy2 = AsyncMock()
        strategy2.name = "healthcheck"  # Healthcheck skips validation
        strategy2.resolve.return_value = "https://www42.mejortorrent.eu"

        resolver = DomainResolver(
            http_client=mock_http_client,
            strategies=[strategy1, strategy2],
            persistence_path=tmp_persistence,
        )
        resolver.register_provider(mejortorrent_config)

        # Validation fails for strategy1's candidate
        mock_http_client.head.side_effect = Exception("Connection refused")

        result = await resolver.resolve("mejortorrent")

        assert result == "https://www42.mejortorrent.eu"

    @pytest.mark.asyncio
    async def test_notifies_on_domain_change(self, mock_http_client, mejortorrent_config, tmp_persistence):
        strategy = AsyncMock()
        strategy.name = "healthcheck"  # Skips validation
        strategy.resolve.return_value = "https://www43.mejortorrent.eu"

        resolver = DomainResolver(
            http_client=mock_http_client,
            strategies=[strategy],
            persistence_path=tmp_persistence,
        )
        resolver.register_provider(mejortorrent_config)

        callback = AsyncMock()
        resolver.on_domain_change(callback)

        await resolver.resolve("mejortorrent")

        callback.assert_called_once_with("mejortorrent", "https://www43.mejortorrent.eu")

    @pytest.mark.asyncio
    async def test_does_not_notify_when_same_domain(self, mock_http_client, mejortorrent_config, tmp_persistence):
        strategy = AsyncMock()
        strategy.name = "healthcheck"
        strategy.resolve.return_value = "https://www42.mejortorrent.eu"

        resolver = DomainResolver(
            http_client=mock_http_client,
            strategies=[strategy],
            persistence_path=tmp_persistence,
        )
        resolver.register_provider(mejortorrent_config)

        callback = AsyncMock()
        resolver.on_domain_change(callback)

        await resolver.resolve("mejortorrent")

        callback.assert_not_called()

    def test_get_current_returns_default(self, mock_http_client, mejortorrent_config, tmp_persistence):
        resolver = DomainResolver(
            http_client=mock_http_client,
            persistence_path=tmp_persistence,
        )
        resolver.register_provider(mejortorrent_config)

        assert resolver.get_current("mejortorrent") == "https://www42.mejortorrent.eu"

    def test_get_current_raises_for_unknown(self, mock_http_client, tmp_persistence):
        resolver = DomainResolver(
            http_client=mock_http_client,
            persistence_path=tmp_persistence,
        )

        with pytest.raises(ValueError, match="not registered"):
            resolver.get_current("unknown")


# --- Persistence Tests ---

class TestDomainPersistence:
    """Tests para la persistencia en JSON."""

    @pytest.mark.asyncio
    async def test_persists_after_resolve(self, mock_http_client, mejortorrent_config, tmp_persistence):
        strategy = AsyncMock()
        strategy.name = "healthcheck"
        strategy.resolve.return_value = "https://www42.mejortorrent.eu"

        resolver = DomainResolver(
            http_client=mock_http_client,
            strategies=[strategy],
            persistence_path=tmp_persistence,
        )
        resolver.register_provider(mejortorrent_config)

        await resolver.resolve("mejortorrent")

        # Check file exists and has correct data
        data = json.loads(Path(tmp_persistence).read_text())
        assert "mejortorrent" in data
        assert data["mejortorrent"]["url"] == "https://www42.mejortorrent.eu"
        assert data["mejortorrent"]["source"] == "healthcheck"

    def test_loads_persisted_on_init(self, mock_http_client, tmp_persistence):
        # Write persistence file
        persist_data = {
            "mejortorrent": {
                "url": "https://www99.mejortorrent.eu",
                "resolved_at": "2026-04-17T19:30:00Z",
                "source": "privtree",
                "healthy": True,
                "last_health_check": None,
            }
        }
        path = Path(tmp_persistence)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(persist_data))

        resolver = DomainResolver(
            http_client=mock_http_client,
            persistence_path=tmp_persistence,
        )

        # The persisted domain should be loaded
        assert resolver.get_current("mejortorrent") == "https://www99.mejortorrent.eu"

    def test_get_status_returns_all(self, mock_http_client, mejortorrent_config, dontorrent_config, tmp_persistence):
        resolver = DomainResolver(
            http_client=mock_http_client,
            persistence_path=tmp_persistence,
        )
        resolver.register_provider(mejortorrent_config)
        resolver.register_provider(dontorrent_config)

        status = resolver.get_status()

        assert "mejortorrent" in status
        assert "dontorrent" in status
        assert status["mejortorrent"]["url"] == "https://www42.mejortorrent.eu"
        assert status["dontorrent"]["url"] == "https://dontorrent.reisen"
