"""
Tests for the Admin REST API endpoints (/api/admin/*).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin import router as admin_router
from app.services.config_manager import ConfigManager


# ────────────────────────────────────────────────────────────────────────
# Fixtures
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
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS readarr_instances (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT,
            url     TEXT,
            api_key TEXT,
            enabled INTEGER DEFAULT 0,
            external_url TEXT DEFAULT ''
        )
    """)
    await conn.commit()
    yield conn
    await conn.close()


@pytest.fixture
def patched_app(memory_connection):
    """Create a minimal FastAPI app with the admin router and mocked dependencies.

    The config_manager on app.state uses an in-memory DB so tests do not
    touch the filesystem.
    """
    app = FastAPI()
    app.include_router(admin_router)

    async def _get_memory_db():
        return memory_connection

    # Keep patches active for the whole test: admin endpoints import get_db
    # lazily inside handlers, and ConfigManager also calls get_db at runtime.
    with patch("app.persistence.database.get_db", side_effect=_get_memory_db), patch(
        "app.services.config_manager.get_db", side_effect=_get_memory_db
    ):
        app.state.config_manager = ConfigManager()
        app.state.domain_resolver = MagicMock()
        app.state.http_client = MagicMock()
        yield app


@pytest.fixture
def client(patched_app):
    """TestClient wrapping the admin app fixture."""
    return TestClient(patched_app)


# ────────────────────────────────────────────────────────────────────────
# Provider endpoints
# ────────────────────────────────────────────────────────────────────────


class TestProviderEndpoints:
    """Tests for GET /api/admin/providers and PUT /api/admin/providers/{id}."""

    @pytest.mark.asyncio
    async def test_list_providers_returns_json(self, client):
        """GET /api/admin/providers should return JSON with a providers key."""
        response = client.get("/api/admin/providers")
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert isinstance(data["providers"], list)

    @pytest.mark.asyncio
    async def test_list_providers_includes_enabled_flag(self, client, patched_app):
        """Providers returned should include the enabled flag from the DB."""
        # Arrange: seed a provider
        await patched_app.state.config_manager.set_provider_enabled("test_prov", True)

        # Act
        response = client.get("/api/admin/providers")
        data = response.json()

        # Assert
        providers = data["providers"]
        assert len(providers) >= 1
        test_prov = next(p for p in providers if p["provider_id"] == "test_prov")
        assert test_prov["enabled"] is True

    @pytest.mark.asyncio
    async def test_update_provider_disable(self, client, patched_app):
        """PUT /api/admin/providers/{id} with enabled=False should persist."""
        # Arrange: seed a provider
        await patched_app.state.config_manager.set_provider_enabled("test_prov", True)

        # Act
        response = client.put(
            "/api/admin/providers/test_prov",
            json={"enabled": False},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

        # Verify it persisted
        result = await patched_app.state.config_manager.get_provider_config("test_prov")
        assert result["enabled"] is False

    @pytest.mark.asyncio
    async def test_update_provider_domain(self, client, patched_app):
        """PUT /api/admin/providers/{id} with domain should persist."""
        await patched_app.state.config_manager.set_provider_enabled("test_prov", True)

        response = client.put(
            "/api/admin/providers/test_prov",
            json={"domain": "https://new.domain.com"},
        )

        assert response.status_code == 200
        result = await patched_app.state.config_manager.get_provider_config("test_prov")
        assert result["domain"] == "https://new.domain.com"

    @pytest.mark.asyncio
    async def test_update_nonexistent_provider_returns_404(self, client):
        """PUT /api/admin/providers/{nonexistent} should return 404."""
        response = client.put(
            "/api/admin/providers/nonexistent",
            json={"enabled": True},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_reload_providers(self, client):
        """POST /api/admin/providers/reload should call _init_providers and report count."""
        with patch(
            "app.api.torznab._init_providers", new_callable=AsyncMock
        ) as mock_init:
            # Need at least one provider in the registry for count
            from app.providers.registry import registry
            registry.clear()
            mock_prov = MagicMock()
            mock_prov.provider_id = "dummy"
            mock_prov.display_name = "Dummy"
            registry.register(mock_prov)

            response = client.post("/api/admin/providers/reload")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "reloaded"
            assert "provider_count" in data
            mock_init.assert_awaited()

    @pytest.mark.asyncio
    async def test_update_provider_not_found_before_seeding(self, client):
        """PUT on a provider that hasn't been inserted yet should return 404."""
        response = client.put(
            "/api/admin/providers/never_seeded",
            json={"enabled": True},
        )
        assert response.status_code == 404


# ────────────────────────────────────────────────────────────────────────
# Settings endpoints
# ────────────────────────────────────────────────────────────────────────


class TestSettingsEndpoints:
    """Tests for GET /api/admin/settings and PUT /api/admin/settings/{key}."""

    @pytest.mark.asyncio
    async def test_get_settings_returns_dict(self, client, patched_app):
        """GET /api/admin/settings should return a settings dict."""
        await patched_app.state.config_manager.set_setting("key1", "val1")

        response = client.get("/api/admin/settings")
        assert response.status_code == 200
        data = response.json()
        assert "settings" in data
        assert data["settings"]["key1"] == "val1"

    @pytest.mark.asyncio
    async def test_get_settings_empty(self, client):
        """GET /api/admin/settings should return empty dict when no settings exist."""
        response = client.get("/api/admin/settings")
        assert response.status_code == 200
        data = response.json()
        assert data["settings"] == {}

    @pytest.mark.asyncio
    async def test_update_setting_persists(self, client, patched_app):
        """PUT /api/admin/settings/{key} should update the setting value."""
        response = client.put(
            "/api/admin/settings/my_setting",
            json={"value": "new_value"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["key"] == "my_setting"

        # Verify persistence
        value = await patched_app.state.config_manager.get_setting("my_setting")
        assert value == "new_value"


# ────────────────────────────────────────────────────────────────────────
# Readarr instance endpoints (CRUD)
# ────────────────────────────────────────────────────────────────────────


class TestReadarrCrud:
    """Tests for /api/admin/readarr CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_readarr_instance(self, client):
        """POST /api/admin/readarr should create an instance and return 201."""
        response = client.post(
            "/api/admin/readarr",
            json={
                "name": "Main Readarr",
                "url": "http://readarr:8787",
                "api_key": "secret123",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "created"
        assert isinstance(data["id"], int)

    @pytest.mark.asyncio
    async def test_list_readarr_instances(self, client):
        """GET /api/admin/readarr should return all instances."""
        # Create two instances
        client.post(
            "/api/admin/readarr",
            json={"name": "R1", "url": "http://r1:8787", "api_key": "k1"},
        )
        client.post(
            "/api/admin/readarr",
            json={"name": "R2", "url": "http://r2:8787", "api_key": "k2"},
        )

        response = client.get("/api/admin/readarr")
        assert response.status_code == 200
        data = response.json()
        assert len(data["instances"]) == 2

    @pytest.mark.asyncio
    async def test_update_readarr_instance(self, client):
        """PUT /api/admin/readarr/{id} should update an instance."""
        # Create first
        create_resp = client.post(
            "/api/admin/readarr",
            json={"name": "Old Name", "url": "http://old:8787", "api_key": "old"},
        )
        instance_id = create_resp.json()["id"]

        # Update
        response = client.put(
            f"/api/admin/readarr/{instance_id}",
            json={"name": "New Name", "enabled": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"

        # Verify via list
        list_resp = client.get("/api/admin/readarr")
        instances = list_resp.json()["instances"]
        updated = next(i for i in instances if i["id"] == instance_id)
        assert updated["name"] == "New Name"
        assert updated["enabled"] == 1

    @pytest.mark.asyncio
    async def test_delete_readarr_instance(self, client):
        """DELETE /api/admin/readarr/{id} should remove an instance."""
        create_resp = client.post(
            "/api/admin/readarr",
            json={"name": "To Delete", "url": "http://del:8787", "api_key": "del"},
        )
        instance_id = create_resp.json()["id"]

        response = client.delete(f"/api/admin/readarr/{instance_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # Verify deletion
        list_resp = client.get("/api/admin/readarr")
        assert len(list_resp.json()["instances"]) == 0

    @pytest.mark.asyncio
    async def test_update_readarr_instance_no_fields_returns_400(self, client):
        """PUT with empty body should return 400."""
        create_resp = client.post(
            "/api/admin/readarr",
            json={"name": "Test", "url": "http://t:8787", "api_key": "k"},
        )
        instance_id = create_resp.json()["id"]

        response = client.put(
            f"/api/admin/readarr/{instance_id}",
            json={},
        )
        assert response.status_code == 400
        assert "No fields to update" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_sync_nonexistent_instance_returns_404(self, client):
        """POST /api/admin/readarr/999/sync for non-existent instance returns 404."""
        response = client.post("/api/admin/readarr/999/sync")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_test_nonexistent_instance_returns_404(self, client):
        """POST /api/admin/readarr/999/test for non-existent instance returns 404."""
        response = client.post("/api/admin/readarr/999/test")
        assert response.status_code == 404


# ────────────────────────────────────────────────────────────────────────
# Sync and test endpoint (mocked ReadarrSyncer)
# ────────────────────────────────────────────────────────────────────────


class TestReadarrSyncAndTestEndpoint:
    """Tests for POST /api/admin/readarr/{id}/sync and /test."""

    @pytest.mark.asyncio
    async def test_sync_returns_syncer_result(self, client, patched_app):
        """sync endpoint should delegate to ReadarrSyncer.sync_all()."""
        # Create a Readarr instance
        create_resp = client.post(
            "/api/admin/readarr",
            json={"name": "SyncTest", "url": "http://readarr:8787", "api_key": "sync-key"},
        )
        instance_id = create_resp.json()["id"]

        mock_result = {
            "success": True,
            "created": 3,
            "updated": 0,
            "failed": 0,
            "deleted": 0,
            "details": [],
        }

        with patch(
            "app.services.readarr_syncer.ReadarrSyncer"
        ) as mock_syncer_cls:
            mock_syncer = AsyncMock()
            mock_syncer.sync_all = AsyncMock(return_value=mock_result)
            mock_syncer_cls.return_value = mock_syncer

            # Also need external_url and api_key settings in DB
            await patched_app.state.config_manager.set_setting(
                "external_url", "http://wtr:9811"
            )
            await patched_app.state.config_manager.set_setting(
                "api_key", "wtr-key"
            )

            response = client.post(f"/api/admin/readarr/{instance_id}/sync")
            assert response.status_code == 200
            assert response.json() == mock_result

    @pytest.mark.asyncio
    async def test_test_endpoint_returns_connection_result(self, client):
        """test endpoint should delegate to ReadarrSyncer.test_connection()."""
        create_resp = client.post(
            "/api/admin/readarr",
            json={"name": "TestConn", "url": "http://readarr:8787", "api_key": "conn-key"},
        )
        instance_id = create_resp.json()["id"]

        mock_result = {
            "success": True,
            "message": "Connected",
            "version": "0.1.2.1555",
        }

        with patch(
            "app.services.readarr_syncer.ReadarrSyncer"
        ) as mock_syncer_cls:
            mock_syncer = AsyncMock()
            mock_syncer.test_connection = AsyncMock(return_value=mock_result)
            mock_syncer_cls.return_value = mock_syncer

            response = client.post(f"/api/admin/readarr/{instance_id}/test")
            assert response.status_code == 200
            assert response.json() == mock_result
