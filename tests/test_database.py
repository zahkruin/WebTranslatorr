"""
Tests for SQLite database initialisation, migration, and CRUD models.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite

from app.persistence import database as db_module
from app.persistence import models as db_models
from app.persistence import migration as db_migration


# ────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────


@pytest.fixture
def reset_database_singleton():
    """Ensure the database singleton is cleaned between tests."""
    # Save original state
    original_db = db_module._db
    yield
    # Restore and close any test connection
    if db_module._db is not None and db_module._db is not original_db:
        try:
            import asyncio
            asyncio.get_event_loop().run_until_complete(db_module._db.close())
        except Exception:
            pass
    db_module._db = original_db


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
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS readarr_instances (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT,
            url     TEXT,
            api_key TEXT,
            enabled INTEGER DEFAULT 0
        )
    """)
    await conn.commit()

    yield conn
    await conn.close()


# ────────────────────────────────────────────────────────────────────────
# Tests: database.py — init_db / get_db
# ────────────────────────────────────────────────────────────────────────


class TestInitDb:
    """Tests for database module init_db() and get_db()."""

    @pytest.mark.asyncio
    async def test_init_db_creates_three_tables(self, reset_database_singleton):
        """init_db() should create provider_config, settings, and readarr_instances tables."""
        import aiosqlite as aiosqlite_mod

        db_module._db = None
        mem_conn = await aiosqlite_mod.connect(":memory:")

        with patch(
            "app.persistence.database.aiosqlite.connect",
            return_value=mem_conn,
        ):
            with patch("app.persistence.database.migrate_from_env", new=AsyncMock()):
                await db_module.init_db()

        # Verify singleton is set
        assert db_module._db is not None
        assert db_module._db is mem_conn

        # Verify 3 tables exist
        cursor = await mem_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        rows = await cursor.fetchall()
        tables = [row[0] for row in rows]
        assert "provider_config" in tables
        assert "settings" in tables
        assert "readarr_instances" in tables

        await mem_conn.close()
        db_module._db = None

    @pytest.mark.asyncio
    async def test_init_db_is_idempotent(self, reset_database_singleton):
        """Second call to init_db() should be a no-op once singleton is set."""
        db_module._db = None
        first_conn = await aiosqlite.connect(":memory:")

        with patch(
            "app.persistence.database.aiosqlite.connect",
            return_value=first_conn,
        ):
            with patch("app.persistence.database.migrate_from_env", new=AsyncMock()):
                await db_module.init_db()

        # Second call: must not overwrite _db
        second_conn = await aiosqlite.connect(":memory:")
        connect_called = False

        async def tracked_connect(_):
            nonlocal connect_called
            connect_called = True
            return second_conn

        with patch(
            "app.persistence.database.aiosqlite.connect",
            side_effect=tracked_connect,
        ):
            await db_module.init_db()

        # connect should NOT have been called (idempotent guard)
        assert connect_called is False
        assert db_module._db is first_conn

        await first_conn.close()
        await second_conn.close()
        db_module._db = None

    @pytest.mark.asyncio
    async def test_get_db_returns_singleton(self, reset_database_singleton):
        """get_db() should return the same connection instance every call."""
        db_module._db = None
        mem_conn = await aiosqlite.connect(":memory:")

        with patch(
            "app.persistence.database.aiosqlite.connect",
            return_value=mem_conn,
        ):
            with patch("app.persistence.database.migrate_from_env", new=AsyncMock()):
                await db_module.init_db()

        conn1 = await db_module.get_db()
        conn2 = await db_module.get_db()
        assert conn1 is conn2
        assert conn1 is mem_conn

        await mem_conn.close()
        db_module._db = None

    @pytest.mark.asyncio
    async def test_get_db_auto_initialises(self, reset_database_singleton):
        """get_db() should call init_db() when _db is None."""
        db_module._db = None
        mem_conn = await aiosqlite.connect(":memory:")

        with patch(
            "app.persistence.database.aiosqlite.connect",
            return_value=mem_conn,
        ):
            with patch("app.persistence.database.migrate_from_env", new=AsyncMock()):
                conn = await db_module.get_db()

        assert conn is not None
        assert db_module._db is not None

        await mem_conn.close()
        db_module._db = None


# ────────────────────────────────────────────────────────────────────────
# Tests: migration.py — migrate_from_env
# ────────────────────────────────────────────────────────────────────────


class TestMigrateFromEnv:
    """Tests for populate-from-environment migration."""

    @pytest.mark.asyncio
    async def test_migrate_from_env_seeds_empty_database(self, reset_database_singleton):
        """migrate_from_env() should populate provider_config and settings when empty."""
        db_module._db = None
        mem_conn = await aiosqlite.connect(":memory:")
        mem_conn.row_factory = aiosqlite.Row

        # Create the tables first (as init_db would)
        await mem_conn.execute("""
            CREATE TABLE IF NOT EXISTS provider_config (
                provider_id TEXT PRIMARY KEY, enabled INTEGER DEFAULT 1,
                domain TEXT, display_name TEXT
            )
        """)
        await mem_conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value TEXT
            )
        """)
        await mem_conn.commit()

        # Set the singleton connection
        db_module._db = mem_conn

        with patch("app.persistence.migration.settings") as mock_settings:
            # Configure mock settings with known values
            mock_settings.API_KEY = "test-api-key"
            mock_settings.EXTERNAL_URL = "http://test:9811"
            mock_settings.TMDB_API_KEY = ""
            mock_settings.GOOGLE_BOOKS_API_KEY = ""
            mock_settings.HTTP_PROXY = ""
            mock_settings.RATE_LIMIT_PER_SECOND = 5.0
            mock_settings.CACHE_ENABLED = True
            mock_settings.CACHE_TTL_SECONDS = 300
            mock_settings.DEFAULT_SEARCH_LANGUAGE = "es"
            mock_settings.DOMAIN_CHECK_INTERVAL = 1800
            mock_settings.LOG_LEVEL = "INFO"

            # Default all provider ENABLED to False and DOMAIN to "" (the migration
            # uses getattr(settings, ..., False) for enabled and getattr(..., "") for domain)
            for entry in db_migration._KNOWN_PROVIDERS:
                pid = entry["id"]
                env_enabled = f"{pid.upper()}_ENABLED"
                env_domain = f"{pid.upper()}_DOMAIN"
                setattr(mock_settings, env_enabled, False)
                setattr(mock_settings, env_domain, "")

            await db_migration.migrate_from_env()

        # Verify providers were seeded
        cursor = await mem_conn.execute("SELECT COUNT(*) FROM provider_config")
        row = await cursor.fetchone()
        assert row[0] == len(db_migration._KNOWN_PROVIDERS)

        # Verify settings were seeded
        cursor = await mem_conn.execute("SELECT key, value FROM settings WHERE key='api_key'")
        row = await cursor.fetchone()
        assert row["value"] == "test-api-key"

        await mem_conn.close()
        db_module._db = None

    @pytest.mark.asyncio
    async def test_migrate_from_env_skips_when_data_exists(self, reset_database_singleton):
        """migrate_from_env() should be a no-op when provider_config already has rows."""
        db_module._db = None
        mem_conn = await aiosqlite.connect(":memory:")
        mem_conn.row_factory = aiosqlite.Row

        await mem_conn.execute("""
            CREATE TABLE IF NOT EXISTS provider_config (
                provider_id TEXT PRIMARY KEY, enabled INTEGER DEFAULT 1,
                domain TEXT, display_name TEXT
            )
        """)
        await mem_conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value TEXT
            )
        """)
        # Pre-populate with one row
        await mem_conn.execute(
            "INSERT INTO provider_config (provider_id, enabled, display_name) VALUES (?, ?, ?)",
            ("test_prov", 1, "Test Provider"),
        )
        await mem_conn.commit()

        db_module._db = mem_conn

        with patch("app.persistence.migration.settings") as mock_settings:
            await db_migration.migrate_from_env()

        # The row count should still be 1 (not re-seeded with _KNOWN_PROVIDERS)
        cursor = await mem_conn.execute("SELECT COUNT(*) FROM provider_config")
        row = await cursor.fetchone()
        assert row[0] == 1

        await mem_conn.close()
        db_module._db = None


# ────────────────────────────────────────────────────────────────────────
# Tests: models.py — CRUD operations
# ────────────────────────────────────────────────────────────────────────


class TestProviderConfigCrud:
    """Tests for provider_config CRUD operations."""

    @pytest.mark.asyncio
    async def test_insert_and_read_provider(self, memory_connection):
        """Insert a provider then read it back via get_provider_config."""
        await db_models.set_provider_enabled(memory_connection, "test_prov", True)
        await db_models.set_provider_domain(memory_connection, "test_prov", "https://example.com")

        row = await db_models.get_provider_config(memory_connection, "test_prov")
        assert row is not None
        assert row["provider_id"] == "test_prov"
        assert row["enabled"] == 1
        assert row["domain"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_get_nonexistent_provider(self, memory_connection):
        """get_provider_config should return None for unknown provider."""
        row = await db_models.get_provider_config(memory_connection, "nonexistent")
        assert row is None

    @pytest.mark.asyncio
    async def test_set_provider_enabled_toggles(self, memory_connection):
        """set_provider_enabled should persist the enabled flag."""
        # Insert disabled
        await db_models.set_provider_enabled(memory_connection, "prov_a", False)
        row = await db_models.get_provider_config(memory_connection, "prov_a")
        assert row["enabled"] == 0

        # Toggle to enabled
        await db_models.set_provider_enabled(memory_connection, "prov_a", True)
        row = await db_models.get_provider_config(memory_connection, "prov_a")
        assert row["enabled"] == 1

    @pytest.mark.asyncio
    async def test_set_provider_domain_updates(self, memory_connection):
        """set_provider_domain should update an existing domain."""
        await db_models.set_provider_domain(memory_connection, "prov_a", "https://old.example.com")
        await db_models.set_provider_domain(memory_connection, "prov_a", "https://new.example.com")

        row = await db_models.get_provider_config(memory_connection, "prov_a")
        assert row["domain"] == "https://new.example.com"

    @pytest.mark.asyncio
    async def test_get_all_provider_configs(self, memory_connection):
        """get_all_provider_configs should return all rows."""
        await db_models.set_provider_enabled(memory_connection, "prov_a", True)
        await db_models.set_provider_enabled(memory_connection, "prov_b", False)

        rows = await db_models.get_all_provider_configs(memory_connection)
        assert len(rows) == 2
        ids = {r["provider_id"] for r in rows}
        assert ids == {"prov_a", "prov_b"}


class TestSettingsCrud:
    """Tests for settings key-value CRUD operations."""

    @pytest.mark.asyncio
    async def test_set_and_get_setting(self, memory_connection):
        """set_setting and get_setting should persist key-value pairs."""
        await db_models.set_setting(memory_connection, "test_key", "test_value")
        value = await db_models.get_setting(memory_connection, "test_key")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_get_nonexistent_setting(self, memory_connection):
        """get_setting should return None for unknown key."""
        value = await db_models.get_setting(memory_connection, "no_such_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_set_setting_overwrites(self, memory_connection):
        """set_setting should overwrite an existing key."""
        await db_models.set_setting(memory_connection, "key1", "original")
        await db_models.set_setting(memory_connection, "key1", "updated")
        value = await db_models.get_setting(memory_connection, "key1")
        assert value == "updated"

    @pytest.mark.asyncio
    async def test_get_all_settings(self, memory_connection):
        """get_all_settings should return a full dict."""
        await db_models.set_setting(memory_connection, "k1", "v1")
        await db_models.set_setting(memory_connection, "k2", "v2")

        all_settings = await db_models.get_all_settings(memory_connection)
        assert all_settings == {"k1": "v1", "k2": "v2"}

    @pytest.mark.asyncio
    async def test_get_all_settings_empty(self, memory_connection):
        """get_all_settings should return empty dict when no settings exist."""
        all_settings = await db_models.get_all_settings(memory_connection)
        assert all_settings == {}


class TestReadarrInstancesCrud:
    """Tests for readarr_instances CRUD operations."""

    @pytest.mark.asyncio
    async def test_add_and_list_readarr_instances(self, memory_connection):
        """add_readarr_instance and get_readarr_instances should work together."""
        new_id = await db_models.add_readarr_instance(
            memory_connection, "Main Readarr", "http://readarr:8787", "abc123"
        )
        assert isinstance(new_id, int)

        instances = await db_models.get_readarr_instances(memory_connection)
        assert len(instances) == 1
        assert instances[0]["id"] == new_id
        assert instances[0]["name"] == "Main Readarr"
        assert instances[0]["url"] == "http://readarr:8787"
        assert instances[0]["api_key"] == "abc123"
        assert instances[0]["enabled"] == 0  # default

    @pytest.mark.asyncio
    async def test_update_readarr_instance(self, memory_connection):
        """update_readarr_instance should update existing fields."""
        new_id = await db_models.add_readarr_instance(
            memory_connection, "Old Name", "http://old:8787", "key123"
        )
        await db_models.update_readarr_instance(
            memory_connection, new_id, name="New Name", enabled=True
        )

        instances = await db_models.get_readarr_instances(memory_connection)
        assert instances[0]["name"] == "New Name"
        assert instances[0]["enabled"] == 1

    @pytest.mark.asyncio
    async def test_delete_readarr_instance(self, memory_connection):
        """delete_readarr_instance should remove the row."""
        new_id = await db_models.add_readarr_instance(
            memory_connection, "To Delete", "http://del:8787", "del123"
        )
        await db_models.delete_readarr_instance(memory_connection, new_id)

        instances = await db_models.get_readarr_instances(memory_connection)
        assert len(instances) == 0

    @pytest.mark.asyncio
    async def test_update_readarr_instance_ignores_unknown_fields(self, memory_connection):
        """update_readarr_instance should ignore keys not in allowed_fields."""
        new_id = await db_models.add_readarr_instance(
            memory_connection, "Test", "http://test:8787", "key123"
        )
        # This should not raise but should log a debug message
        await db_models.update_readarr_instance(
            memory_connection, new_id, name="Still Test", unknown_field="bad"
        )

        instances = await db_models.get_readarr_instances(memory_connection)
        assert instances[0]["name"] == "Still Test"

    @pytest.mark.asyncio
    async def test_readarr_auto_increment_ids(self, memory_connection):
        """add_readarr_instance should return distinct auto-incremented IDs."""
        id1 = await db_models.add_readarr_instance(
            memory_connection, "Instance 1", "http://r1:8787", "key1"
        )
        id2 = await db_models.add_readarr_instance(
            memory_connection, "Instance 2", "http://r2:8787", "key2"
        )
        assert id1 != id2
        assert id2 == id1 + 1
