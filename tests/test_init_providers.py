"""
Tests for _init_providers() — provider registration from ConfigManager vs env vars.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.providers.registry import registry
from app.api import torznab


# ────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────


def _make_config_manager(providers):
    """Build a mock ConfigManager returning specific enabled providers."""
    mgr = MagicMock()
    mgr.get_all_enabled_providers = AsyncMock(return_value=providers)
    return mgr


# ────────────────────────────────────────────────────────────────────────
# Fixture: auto-reset registry
# ────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def reset_torznab_globals():
    """Reset provider registry before each test."""
    registry.clear()
    yield
    registry.clear()


# ────────────────────────────────────────────────────────────────────────
# Tests: _init_providers with ConfigManager (DB-driven)
# ────────────────────────────────────────────────────────────────────────


class TestInitProvidersWithConfigManager:
    """Tests for _init_providers() when config_manager is provided (DB mode)."""

    @pytest.mark.asyncio
    async def test_registers_only_enabled_providers_from_db(self):
        """_init_providers with ConfigManager should only register enabled DB providers."""
        providers = [
            {
                "provider_id": "ebookelo",
                "enabled": True,
                "domain": "",
                "display_name": "Ebookelo",
            },
            {
                "provider_id": "lectulandia",
                "enabled": False,
                "domain": "",
                "display_name": "Lectulandia",
            },
            {
                "provider_id": "epublibre",
                "enabled": True,
                "domain": "",
                "display_name": "EpubLibre",
            },
        ]
        config_manager = _make_config_manager(providers)
        http_client = MagicMock()

        await torznab._init_providers(
            http_client=http_client, config_manager=config_manager
        )

        registered_ids = [p.provider_id for p in registry.get_all()]
        assert "ebookelo" in registered_ids
        assert "epublibre" in registered_ids
        # Lectulandia is disabled in DB
        assert "lectulandia" not in registered_ids

    @pytest.mark.asyncio
    async def test_skips_unknown_provider_id_in_db(self):
        """_init_providers should skip provider IDs not in _PROVIDER_CLASSES."""
        providers = [
            {
                "provider_id": "unknown_provider_xyz",
                "enabled": True,
                "domain": "",
                "display_name": "Unknown",
            },
            {
                "provider_id": "ebookelo",
                "enabled": True,
                "domain": "",
                "display_name": "Ebookelo",
            },
        ]
        config_manager = _make_config_manager(providers)
        http_client = MagicMock()

        await torznab._init_providers(
            http_client=http_client, config_manager=config_manager
        )

        registered_ids = [p.provider_id for p in registry.get_all()]
        assert "ebookelo" in registered_ids
        assert "unknown_provider_xyz" not in registered_ids

    @pytest.mark.asyncio
    async def test_disabled_provider_not_in_registry(self):
        """A disabled provider should not appear in the registry after _init_providers()."""
        providers = [
            {
                "provider_id": "ebookelo",
                "enabled": False,
                "domain": "",
                "display_name": "Ebookelo",
            },
        ]
        config_manager = _make_config_manager(providers)
        http_client = MagicMock()

        await torznab._init_providers(
            http_client=http_client, config_manager=config_manager
        )

        assert len(registry.get_all()) == 0


# ────────────────────────────────────────────────────────────────────────
# Tests: _init_providers without ConfigManager (env-var fallback)
# ────────────────────────────────────────────────────────────────────────


class TestInitProvidersFallbackToEnv:
    """Tests for _init_providers() when config_manager is None (env var fallback)."""

    @pytest.mark.asyncio
    async def test_fallback_registers_from_env_vars(self):
        """When config_manager is None, _init_providers should use env vars."""
        http_client = MagicMock()
        with patch("app.api.torznab.settings") as mock_settings:
            # Enable only one provider via env vars
            mock_settings.EBOOKELO_ENABLED = True
            mock_settings.EPUBLIBRE_ENABLED = False
            mock_settings.LECTULANDIA_ENABLED = False
            mock_settings.ESPAEBOOK_ENABLED = False
            mock_settings.HOLAEBOOK_ENABLED = False
            mock_settings.ANNASARCHIVE_ENABLED = False
            mock_settings.MEJORTORRENT_ENABLED = False
            mock_settings.DONTORRENT_ENABLED = False
            mock_settings.EPUBFLIX1_ENABLED = False
            mock_settings.LIBGEN_ENABLED = False
            mock_settings.BOOOBOOK_ENABLED = False
            mock_settings.LECTUEPUBLIBRE5_ENABLED = False
            mock_settings.MUNDOEPUBLIBRE1_ENABLED = False
            mock_settings.ZLIBRARY_ENABLED = False
            mock_settings.LELIBROS_ENABLED = False
            mock_settings.BAJAEEBOOKS_ENABLED = False
            mock_settings.EBIBLIOTECA_ENABLED = False
            mock_settings.EPUBGRATIS_ENABLED = False
            mock_settings.DIVXTOTAL_ENABLED = False
            mock_settings.ELITETORRENT_ENABLED = False
            mock_settings.BOOKSEE_ENABLED = False
            mock_settings.OCEANOFPDF_ENABLED = False
            mock_settings.ELEJANDRIA_ENABLED = False
            mock_settings.GUTENBERG_ENABLED = False

            # Call with None config_manager triggers env fallback
            await torznab._init_providers(
                http_client=http_client, config_manager=None
            )

            registered_ids = [p.provider_id for p in registry.get_all()]
            assert "ebookelo" in registered_ids
            assert "epublibre" not in registered_ids

    @pytest.mark.asyncio
    async def test_fallback_called_when_config_manager_is_none(self):
        """Explicitly passing None should use the env var fallback path."""
        http_client = MagicMock()
        with patch("app.api.torznab._init_providers_from_env") as mock_fallback:
            await torznab._init_providers(
                http_client=http_client, config_manager=None
            )
            mock_fallback.assert_called_once_with(None, http_client)

    @pytest.mark.asyncio
    async def test_requires_http_client(self):
        """_init_providers must reject missing http_client."""
        with pytest.raises(ValueError, match="http_client is required"):
            await torznab._init_providers(config_manager=None)
