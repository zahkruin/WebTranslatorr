"""
Tests for ConfigManager — the runtime configuration facade over SQLite.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite

from app.services.config_manager import ConfigManager


# ────────────────────────────────────────────────────────────────────────
# Fixture: in-memory DB with all tables pre-created
# ────────────────────────────────────────────────────────────────────────


@pytest.fixture
async def memory_connection():
    """Return an in-memory aiosqlite connection with all tables created."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS provider_config (
            provider_id TEXT PRIMARY KEY,
            enabled     INTEGER DEFAULT 1,
            domain      TEXT,
            display_name TEXT
        )
    """)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    await conn.commit()
    yield conn
    await conn.close()


@pytest.fixture
def config_manager(memory_connection):
    """Return a ConfigManager whose internal get_db() calls return the in-memory connection.

    We patch ``app.services.config_manager.get_db`` so every ConfigManager
    method transparently uses the in-memory aiosqlite connection.
    """
    with patch("app.services.config_manager.get_db", return_value=memory_connection):
        yield ConfigManager()


# ────────────────────────────────────────────────────────────────────────
# Provider helpers
# ────────────────────────────────────────────────────────────────────────


class TestProviderConfig:
    """Tests for ConfigManager provider configuration methods."""

    @pytest.mark.asyncio
    async def test_get_provider_config_returns_none_for_unknown(self, config_manager):
        """get_provider_config() should return None for non-existent providers."""
        result = await config_manager.get_provider_config("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_provider_enabled_persists_and_reflected(self, config_manager):
        """set_provider_enabled() should persist and be visible in get_provider_config()."""
        await config_manager.set_provider_enabled("test_prov", True)
        result = await config_manager.get_provider_config("test_prov")
        assert result is not None
        assert result["provider_id"] == "test_prov"
        assert result["enabled"] is True

    @pytest.mark.asyncio
    async def test_set_provider_domain_persists(self, config_manager):
        """set_provider_domain() should persist the domain."""
        await config_manager.set_provider_domain("test_prov", "https://domain.example.com")
        result = await config_manager.get_provider_config("test_prov")
        assert result["domain"] == "https://domain.example.com"

    @pytest.mark.asyncio
    async def test_get_all_enabled_providers_only_enabled(self, config_manager):
        """get_all_enabled_providers() should only return providers with enabled=True."""
        await config_manager.set_provider_enabled("prov_a", True)
        await config_manager.set_provider_enabled("prov_b", False)
        await config_manager.set_provider_enabled("prov_c", True)

        enabled = await config_manager.get_all_enabled_providers()
        enabled_ids = {p["provider_id"] for p in enabled}
        assert "prov_a" in enabled_ids
        assert "prov_b" not in enabled_ids
        assert "prov_c" in enabled_ids
        assert len(enabled) == 2

    @pytest.mark.asyncio
    async def test_get_all_providers_includes_disabled(self, config_manager):
        """get_all_providers() should return every provider, enabled or not."""
        await config_manager.set_provider_enabled("prov_a", True)
        await config_manager.set_provider_enabled("prov_b", False)

        all_providers = await config_manager.get_all_providers()
        ids = {p["provider_id"] for p in all_providers}
        assert ids == {"prov_a", "prov_b"}

    @pytest.mark.asyncio
    async def test_get_all_enabled_providers_empty(self, config_manager):
        """get_all_enabled_providers() should return empty list with no enabled providers."""
        enabled = await config_manager.get_all_enabled_providers()
        assert enabled == []

    @pytest.mark.asyncio
    async def test_toggle_enabled_is_reflected(self, config_manager):
        """Toggling enabled from True to False should be reflected in get_provider_config()."""
        await config_manager.set_provider_enabled("prov_a", True)
        result = await config_manager.get_provider_config("prov_a")
        assert result["enabled"] is True

        await config_manager.set_provider_enabled("prov_a", False)
        result = await config_manager.get_provider_config("prov_a")
        assert result["enabled"] is False


# ────────────────────────────────────────────────────────────────────────
# Settings (key-value store)
# ────────────────────────────────────────────────────────────────────────


class TestSettings:
    """Tests for ConfigManager settings methods."""

    @pytest.mark.asyncio
    async def test_set_and_get_setting(self, config_manager):
        """set_setting() and get_setting() should persist key-value pairs."""
        await config_manager.set_setting("my_key", "my_value")
        result = await config_manager.get_setting("my_key")
        assert result == "my_value"

    @pytest.mark.asyncio
    async def test_get_setting_nonexistent(self, config_manager):
        """get_setting() should return None for unknown keys."""
        result = await config_manager.get_setting("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_settings_returns_complete_dict(self, config_manager):
        """get_all_settings() should return a full dict of all stored settings."""
        await config_manager.set_setting("k1", "v1")
        await config_manager.set_setting("k2", "v2")

        all_settings = await config_manager.get_all_settings()
        assert all_settings == {"k1": "v1", "k2": "v2"}

    @pytest.mark.asyncio
    async def test_get_all_settings_empty(self, config_manager):
        """get_all_settings() should return an empty dict when nothing is stored."""
        all_settings = await config_manager.get_all_settings()
        assert all_settings == {}


# ────────────────────────────────────────────────────────────────────────
# API key validation
# ────────────────────────────────────────────────────────────────────────


class TestValidateApiKey:
    """Tests for ConfigManager.validate_api_key()."""

    @pytest.mark.asyncio
    async def test_validate_with_correct_key_from_db(self, config_manager):
        """validate_api_key() should return True when key matches DB-stored key."""
        await config_manager.set_setting("api_key", "super-secret")
        assert await config_manager.validate_api_key("super-secret") is True

    @pytest.mark.asyncio
    async def test_validate_with_incorrect_key(self, config_manager):
        """validate_api_key() should return False for mismatched key."""
        await config_manager.set_setting("api_key", "super-secret")
        assert await config_manager.validate_api_key("wrong-key") is False

    @pytest.mark.asyncio
    async def test_validate_with_empty_key(self, config_manager):
        """validate_api_key() should return False for empty/None key."""
        assert await config_manager.validate_api_key("") is False

    @pytest.mark.asyncio
    async def test_validate_falls_back_to_env_when_no_db_key(self, config_manager):
        """When 'api_key' setting is not in DB, validate_api_key() should fall back to config.settings.API_KEY."""
        with patch("app.services.config_manager.app_settings") as mock_settings:
            mock_settings.API_KEY = "env-fallback-key"
            assert await config_manager.validate_api_key("env-fallback-key") is True
            assert await config_manager.validate_api_key("wrong") is False
