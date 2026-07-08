"""
Database CRUD helpers for the persistence layer.

Every public function in this module is async and receives an
:class:`aiosqlite.Connection` as its first parameter.  Write operations
acquire ``write_lock`` from ``app.persistence.database`` to avoid
concurrent-write contention on the single shared connection.

Return values are plain Python ``dict`` instances (or ``None``), never raw
``aiosqlite.Row`` objects — callers never need to worry about row factories.
"""

from __future__ import annotations

import logging
from typing import Any

import aiosqlite

from app.persistence.database import write_lock

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# provider_config
# ---------------------------------------------------------------------------


async def get_all_provider_configs(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    """Return all rows from the ``provider_config`` table.

    Args:
        db: An open :class:`aiosqlite.Connection`.

    Returns:
        A list of dictionaries, one per provider row.  May be empty.
    """
    cursor = await db.execute("SELECT * FROM provider_config")
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_provider_config(db: aiosqlite.Connection, provider_id: str) -> dict[str, Any] | None:
    """Look up a single provider by its ``provider_id``.

    Args:
        db: An open :class:`aiosqlite.Connection`.
        provider_id: The provider's unique identifier (e.g. ``"mejortorrent"``).

    Returns:
        A dictionary representing the row, or ``None`` if not found.
    """
    cursor = await db.execute(
        "SELECT * FROM provider_config WHERE provider_id = ?", (provider_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def set_provider_enabled(db: aiosqlite.Connection, provider_id: str, enabled: bool) -> None:
    """Enable or disable a provider, upserting the row if needed.

    Args:
        db: An open :class:`aiosqlite.Connection`.
        provider_id: The provider's unique identifier.
        enabled: ``True`` to enable, ``False`` to disable.
    """
    async with write_lock:
        await db.execute(
            "INSERT INTO provider_config (provider_id, enabled) VALUES (?, ?)"
            " ON CONFLICT(provider_id) DO UPDATE SET enabled = excluded.enabled",
            (provider_id, int(enabled)),
        )
        await db.commit()
    logger.debug("Provider %r enabled=%s", provider_id, enabled)


async def set_provider_domain(db: aiosqlite.Connection, provider_id: str, domain: str) -> None:
    """Set (or update) the domain for a provider, upserting the row.

    Args:
        db: An open :class:`aiosqlite.Connection`.
        provider_id: The provider's unique identifier.
        domain: The base URL for the provider (e.g. ``"https://example.com"``).
    """
    async with write_lock:
        await db.execute(
            "INSERT INTO provider_config (provider_id, domain) VALUES (?, ?)"
            " ON CONFLICT(provider_id) DO UPDATE SET domain = excluded.domain",
            (provider_id, domain),
        )
        await db.commit()
    logger.debug("Provider %r domain set to %r", provider_id, domain)


async def save_test_result(
    db: aiosqlite.Connection,
    provider_id: str,
    status: str,
    http_status: int | None,
    latency_ms: int | None,
    error_message: str | None,
    tested_at: str,
    url_tested: str | None = None,
) -> None:
    """Persist the result of a provider connectivity test.

    Uses INSERT … ON CONFLICT to create or update the test columns for an
    existing provider row.  If the provider row does not exist yet (should
    not happen in practice), a new row is created with enabled=0.

    Args:
        db: An open :class:`aiosqlite.Connection`.
        provider_id: The provider's unique identifier.
        status: One of ``"ok"``, ``"error"``, ``"timeout"``, ``"auth_required"``.
        http_status: The HTTP status code returned, if any.
        latency_ms: Round-trip latency in milliseconds, if measured.
        error_message: Human-readable error description, if any.
        tested_at: ISO-8601 timestamp of the test.
        url_tested: The URL that was tested.
    """
    async with write_lock:
        await db.execute(
            "INSERT INTO provider_config"
            " (provider_id, last_test_status, last_test_http_status,"
            "  last_test_latency_ms, last_test_error, last_test_at, last_test_url)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(provider_id) DO UPDATE SET"
            "  last_test_status = excluded.last_test_status,"
            "  last_test_http_status = excluded.last_test_http_status,"
            "  last_test_latency_ms = excluded.last_test_latency_ms,"
            "  last_test_error = excluded.last_test_error,"
            "  last_test_at = excluded.last_test_at,"
            "  last_test_url = excluded.last_test_url",
            (provider_id, status, http_status, latency_ms, error_message,
             tested_at, url_tested),
        )
        await db.commit()
    logger.debug("Test result saved for %r: %s", provider_id, status)


async def get_test_results(
    db: aiosqlite.Connection,
) -> dict[str, dict[str, any]]:
    """Return a mapping of ``provider_id`` → last-test-result dict for all rows.

    Only providers that have a non-null ``last_test_status`` are included.
    Each value dict contains ``status``, ``http_status``, ``latency_ms``,
    ``error_message``, ``tested_at``, and ``url_tested``.
    """
    cursor = await db.execute(
        "SELECT provider_id, last_test_status, last_test_http_status,"
        "       last_test_latency_ms, last_test_error, last_test_at, last_test_url"
        " FROM provider_config WHERE last_test_status IS NOT NULL"
    )
    rows = await cursor.fetchall()
    return {
        row["provider_id"]: {
            "status": row["last_test_status"],
            "http_status": row["last_test_http_status"],
            "latency_ms": row["last_test_latency_ms"],
            "error_message": row["last_test_error"],
            "tested_at": row["last_test_at"],
            "url_tested": row["last_test_url"],
        }
        for row in rows
    }


# ---------------------------------------------------------------------------
# settings (key-value store)
# ---------------------------------------------------------------------------


async def get_setting(db: aiosqlite.Connection, key: str) -> str | None:
    """Read a single application setting.

    Args:
        db: An open :class:`aiosqlite.Connection`.
        key: The setting key (e.g. ``"default_search_language"``).

    Returns:
        The stored value as a string, or ``None`` when the key does not
        exist.
    """
    cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = await cursor.fetchone()
    return row["value"] if row else None


async def set_setting(db: aiosqlite.Connection, key: str, value: str) -> None:
    """Store (or overwrite) a single application setting.

    Args:
        db: An open :class:`aiosqlite.Connection`.
        key: The setting key.
        value: The value to store.  Stored as-is (string).
    """
    async with write_lock:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await db.commit()
    logger.debug("Setting %r = %r", key, value)


async def get_all_settings(db: aiosqlite.Connection) -> dict[str, str]:
    """Return the entire ``settings`` table as a flat ``{key: value}`` dict.

    Args:
        db: An open :class:`aiosqlite.Connection`.

    Returns:
        A dictionary mapping every stored key to its value.  May be empty if
        no settings have been saved yet.
    """
    cursor = await db.execute("SELECT key, value FROM settings")
    rows = await cursor.fetchall()
    return {row["key"]: row["value"] for row in rows}


# ---------------------------------------------------------------------------
# readarr_instances
# ---------------------------------------------------------------------------


async def get_readarr_instances(db: aiosqlite.Connection) -> list[dict[str, Any]]:
    """Return all configured Readarr instances.

    Args:
        db: An open :class:`aiosqlite.Connection`.

    Returns:
        A list of dictionaries, one per Readarr instance row.  May be empty.
    """
    cursor = await db.execute("SELECT * FROM readarr_instances")
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def add_readarr_instance(
    db: aiosqlite.Connection, name: str, url: str, api_key: str, external_url: str = ""
) -> int:
    """Insert a new Readarr instance and return its auto-generated ``id``.

    Args:
        db: An open :class:`aiosqlite.Connection`.
        name: Human-readable name for the instance (e.g. ``"Main Readarr"``).
        url:  Base URL of the Readarr instance.
        api_key: API key for authenticating against the instance.
        external_url: URL that Readarr should use to reach WebTranslatorr
                      (e.g. ``"http://192.168.0.10:9811"``).  When empty,
                      the global ``EXTERNAL_URL`` setting is used as fallback.

    Returns:
        The integer primary key assigned to the new row.
    """
    async with write_lock:
        cursor = await db.execute(
            "INSERT INTO readarr_instances (name, url, api_key, external_url) VALUES (?, ?, ?, ?)",
            (name, url, api_key, external_url),
        )
        await db.commit()
    new_id: int = cursor.lastrowid  # type: ignore[assignment]
    logger.info("Added Readarr instance %r (id=%d)", name, new_id)
    return new_id


async def update_readarr_instance(db: aiosqlite.Connection, id: int, **kwargs: Any) -> None:
    """Update one or more columns of an existing Readarr instance.

    Only recognised column names are allowed; unknown keys are silently
    ignored.  Valid keys: ``name``, ``url``, ``api_key``, ``enabled``.

    Args:
        db: An open :class:`aiosqlite.Connection`.
        id: The primary key of the row to update.
        **kwargs: Column names and their new values.
    """
    allowed_fields = {"name", "url", "api_key", "enabled", "external_url"}
    updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
    if not updates:
        logger.debug("update_readarr_instance(id=%d): no valid fields to update", id)
        return

    set_clause = ", ".join(f"{col} = ?" for col in updates)
    values = list(updates.values()) + [id]

    async with write_lock:
        await db.execute(
            f"UPDATE readarr_instances SET {set_clause} WHERE id = ?", values
        )
        await db.commit()
    logger.info("Updated Readarr instance id=%d with fields: %s", id, list(updates.keys()))


async def delete_readarr_instance(db: aiosqlite.Connection, id: int) -> None:
    """Permanently remove a Readarr instance row.

    Args:
        db: An open :class:`aiosqlite.Connection`.
        id: The primary key of the row to delete.
    """
    async with write_lock:
        await db.execute("DELETE FROM readarr_instances WHERE id = ?", (id,))
        await db.commit()
    logger.info("Deleted Readarr instance id=%d", id)
