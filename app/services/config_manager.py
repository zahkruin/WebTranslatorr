"""
Runtime configuration facade over the SQLite persistence layer.

:class:`ConfigManager` is a thread-safe, async singleton that the application
uses to read and write provider configuration and global settings without
needing to know about the underlying ``aiosqlite`` connection or schema.

Typical usage::

    from app.services.config_manager import ConfigManager

    config = ConfigManager()
    providers = await config.get_all_enabled_providers()
    key_ok   = await config.validate_api_key("supersecret")

The instance is stored on the FastAPI application state during startup::

    app.state.config_manager = ConfigManager()
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from config import settings as app_settings

from app.persistence.database import get_db
from app.persistence.models import (
    get_all_provider_configs,
    get_all_settings as db_get_all_settings,
    get_provider_config,
    get_setting as db_get_setting,
    set_provider_domain as db_set_provider_domain,
    set_provider_enabled as db_set_provider_enabled,
    set_setting as db_set_setting,
)

logger = logging.getLogger(__name__)


def _row_to_provider_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Normalise a raw ``provider_config`` row into the public shape.

    Args:
        row: Raw dictionary from a ``SELECT *`` on ``provider_config``.

    Returns:
        A dictionary with ``enabled`` coerced to ``bool``.
    """
    return {
        "provider_id": row["provider_id"],
        "enabled": bool(row.get("enabled", 0)),
        "domain": row.get("domain", ""),
        "display_name": row.get("display_name", ""),
    }


class ConfigManager:
    """Singleton facade for reading/writing runtime configuration.

    Every public method is async and queries the SQLite database directly
    (no in-memory cache).  Write operations that require a read-modify-write
    cycle are serialised through an internal :class:`asyncio.Lock` to avoid
    TOCTOU races on top of the lower-level ``write_lock`` exported by the
    persistence module.

    Attributes:
        _write_lock: Serialises compound read-then-write operations.
    """

    def __init__(self) -> None:
        """Initialise the configuration manager.

        The instance is designed to be used as a singleton — typically created
        once during ``lifespan()`` and stored in ``app.state.config_manager``.
        """
        self._write_lock: asyncio.Lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Provider helpers
    # ------------------------------------------------------------------

    async def get_provider_config(self, provider_id: str) -> dict[str, Any] | None:
        """Return configuration for a single provider.

        Args:
            provider_id: The provider's unique identifier (e.g. ``"mejortorrent"``).

        Returns:
            A dictionary with keys ``provider_id``, ``enabled``, ``domain``,
            ``display_name``, or ``None`` if the provider is not registered.
        """
        db = await get_db()
        row = await get_provider_config(db, provider_id)
        if row is None:
            logger.debug("get_provider_config(%r): not found", provider_id)
            return None
        return _row_to_provider_dict(row)

    async def get_all_enabled_providers(self) -> list[dict[str, Any]]:
        """Return every provider whose ``enabled`` flag is set.

        Returns:
            A list of provider dictionaries.  May be empty.
        """
        db = await get_db()
        rows = await get_all_provider_configs(db)
        return [_row_to_provider_dict(r) for r in rows if r.get("enabled")]

    async def get_all_providers(self) -> list[dict[str, Any]]:
        """Return *all* registered providers, including disabled ones.

        Returns:
            A list of provider dictionaries.  May be empty.
        """
        db = await get_db()
        rows = await get_all_provider_configs(db)
        return [_row_to_provider_dict(r) for r in rows]

    async def set_provider_enabled(self, provider_id: str, enabled: bool) -> None:
        """Enable or disable a provider.

        Args:
            provider_id: The provider's unique identifier.
            enabled: ``True`` to enable, ``False`` to disable.
        """
        db = await get_db()
        await db_set_provider_enabled(db, provider_id, enabled)
        logger.info("Provider %r enabled=%s", provider_id, enabled)

    async def set_provider_domain(self, provider_id: str, domain: str) -> None:
        """Set (or update) the domain for a provider.

        Args:
            provider_id: The provider's unique identifier.
            domain: The base URL for the provider (e.g. ``"https://example.com"``).
        """
        db = await get_db()
        await db_set_provider_domain(db, provider_id, domain)
        logger.info("Provider %r domain set to %r", provider_id, domain)

    # ------------------------------------------------------------------
    # Settings (key-value store)
    # ------------------------------------------------------------------

    async def get_setting(self, key: str) -> str | None:
        """Read a single application setting.

        Args:
            key: The setting key (e.g. ``"api_key"``, ``"cache_ttl_seconds"``).

        Returns:
            The stored value as a string, or ``None`` when the key does not
            exist in the database.
        """
        db = await get_db()
        return await db_get_setting(db, key)

    async def set_setting(self, key: str, value: str) -> None:
        """Store (or overwrite) a single application setting.

        Args:
            key: The setting key.
            value: The value to store.  Stored as-is (string).
        """
        db = await get_db()
        await db_set_setting(db, key, value)

    async def get_all_settings(self) -> dict[str, str]:
        """Return the entire ``settings`` table as a ``{key: value}`` flat dict.

        Returns:
            A dictionary mapping every stored key to its value.  May be empty
            if no settings have been persisted yet.
        """
        db = await get_db()
        return await db_get_all_settings(db)

    # ------------------------------------------------------------------
    # API key validation
    # ------------------------------------------------------------------

    async def validate_api_key(self, key: str) -> bool:
        """Check whether *key* matches the application's configured API key.

        The lookup order is:
        1. The ``api_key`` row in the ``settings`` database table.
        2. ``config.settings.API_KEY`` as a file/env-var fallback.

        Args:
            key: The API key to validate (as received in a request).

        Returns:
            ``True`` when the key matches, ``False`` otherwise.
        """
        if not key:
            return False

        db_key = await self.get_setting("api_key")
        expected = db_key if db_key is not None else app_settings.API_KEY
        return key == expected
