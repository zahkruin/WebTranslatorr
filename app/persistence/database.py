"""
SQLite database initialisation and connection management.

Exposes a singleton aiosqlite.Connection with WAL journal mode and write
serialisation via an asyncio.Lock.  Tables are created on first access
(``CREATE TABLE IF NOT EXISTS``) so the database file is self-bootstrapping.

Typical usage::

    from app.persistence.database import init_db, get_db

    await init_db()          # call once at startup
    db = await get_db()      # reuse across requests
"""

import asyncio
import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

# Absolute path to the SQLite file inside the project's data/ directory.
_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "webtranslatorr.db"

# Singleton connection — module-private, initialised by init_db().
_db: aiosqlite.Connection | None = None

# Lock that serialises initialisation (single-threaded init).
_init_lock: asyncio.Lock = asyncio.Lock()

# Lock that serialises all write operations to prevent concurrent write
# contention on the single SQLite connection.
write_lock: asyncio.Lock = asyncio.Lock()


async def init_db() -> None:
    """Create the database file and tables if they do not exist.

    Safe to call multiple times — subsequent calls are no-ops once the
    singleton connection has been established.

    The connection uses ``PRAGMA journal_mode=WAL`` for better read/write
    concurrency and ``PRAGMA foreign_keys=ON`` as a safety net.
    """
    global _db

    async with _init_lock:
        if _db is not None:
            return  # Already initialised by an earlier call.

        logger.debug("Opening SQLite database at %s", _DB_PATH)
        conn = await aiosqlite.connect(str(_DB_PATH))

        # Enable Write-Ahead Logging for better concurrent read performance.
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = aiosqlite.Row

        # ------------------------------------------------------------------
        # Schema: all tables use IF NOT EXISTS so the file bootstraps itself.
        # ------------------------------------------------------------------

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
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT,
                url           TEXT,
                api_key       TEXT,
                enabled       INTEGER DEFAULT 0,
                external_url  TEXT
            )
        """)

        await conn.commit()

        # ------------------------------------------------------------------
        # Schema migration for existing databases (new columns since v0.2.x)
        # These are safe no-ops if the column already exists.
        # ------------------------------------------------------------------
        try:
            await conn.execute(
                "ALTER TABLE readarr_instances ADD COLUMN external_url TEXT"
            )
            await conn.commit()
            logger.info("Migration: added external_url column to readarr_instances")
        except Exception:
            pass  # Column already exists

        # Migration: provider test result columns (v0.3.x)
        test_columns = [
            ("last_test_status", "TEXT"),
            ("last_test_http_status", "INTEGER"),
            ("last_test_latency_ms", "INTEGER"),
            ("last_test_error", "TEXT"),
            ("last_test_at", "TEXT"),
            ("last_test_url", "TEXT"),
        ]
        for col_name, col_type in test_columns:
            try:
                await conn.execute(
                    f"ALTER TABLE provider_config ADD COLUMN {col_name} {col_type}"
                )
                await conn.commit()
                logger.info("Migration: added %s column to provider_config", col_name)
            except Exception:
                pass  # Column already exists

        _db = conn
        logger.info("Database initialised successfully at %s", _DB_PATH)

        # Run initial migration from env vars (no-op if DB already populated).
        # Lazy import avoids circular dependencies — migration.py imports us.
        from app.persistence.migration import migrate_from_env

        await migrate_from_env()


async def get_db() -> aiosqlite.Connection:
    """Return the singleton :class:`aiosqlite.Connection`.

    If the database has not been initialised yet, ``init_db()`` is called
    transparently so callers do not need to worry about ordering.
    """
    if _db is None:
        await init_db()
    return _db
