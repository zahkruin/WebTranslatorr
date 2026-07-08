"""
One-shot migration that seeds the SQLite database from environment variables.

This module is called automatically by :func:`app.persistence.database.init_db`
the first time the database file is created and the ``provider_config`` table
is empty.  Subsequent runs are no-ops — the database becomes the source of
truth once populated.

The migration is **unidirectional** (env vars → DB) and will re-run only if
the ``webtranslatorr.db`` file is deleted.
"""

from __future__ import annotations

import logging
from typing import Any

from app.persistence.database import get_db, write_lock

# We import the global settings object *only* here so that the migration can
# read the current environment-variable values at startup time.
from config import settings  # noqa: E402

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider catalogue — one entry per provider registered in _init_providers().
# ---------------------------------------------------------------------------

_KNOWN_PROVIDERS: list[dict[str, str]] = [
    # Books
    {"id": "ebookelo",          "display_name": "Ebookelo"},
    {"id": "epublibre",         "display_name": "EpubLibre"},
    {"id": "lectulandia",       "display_name": "Lectulandia"},
    {"id": "espaebook",         "display_name": "Espaebook"},
    {"id": "holaebook",         "display_name": "HolaEbook"},
    {"id": "annasarchive",      "display_name": "Anna's Archive"},
    {"id": "epubflix1",         "display_name": "Epubflix1"},
    {"id": "libgen",            "display_name": "Library Genesis"},
    {"id": "booobook",          "display_name": "B00k.Bond"},
    {"id": "lectuepublibre5",   "display_name": "LectuEpubLibre5"},
    {"id": "mundoepublibre1",   "display_name": "MundoEpubLibre1"},
    {"id": "zlibrary",          "display_name": "Z-Library"},
    {"id": "lelibros",          "display_name": "LeLibros"},
    {"id": "bajaebooks",        "display_name": "Bajaebooks"},
    {"id": "ebiblioteca",       "display_name": "Ebiblioteca"},
    {"id": "epubgratis",        "display_name": "Epubgratis"},
    {"id": "booksee",           "display_name": "BookSee"},
    {"id": "oceanofpdf",        "display_name": "OceanOfPDF"},
    # Video / torrent
    {"id": "mejortorrent",      "display_name": "MejorTorrent"},
    {"id": "dontorrent",        "display_name": "DonTorrent"},
    {"id": "divxtotal",         "display_name": "DivxTotal"},
    {"id": "elitetorrent",      "display_name": "EliteTorrent"},
]


def _build_provider_rows() -> list[dict[str, Any]]:
    """Extract enable/domain values from ``config.settings`` for each provider.

    The convention is::

        settings.{UPPERCASE_ID}_ENABLED  →  bool
        settings.{UPPERCASE_ID}_DOMAIN   →  str | None
    """
    rows: list[dict[str, Any]] = []
    for entry in _KNOWN_PROVIDERS:
        provider_id = entry["id"]
        env_prefix = provider_id.upper()

        enabled = bool(getattr(settings, f"{env_prefix}_ENABLED", False))
        domain = getattr(settings, f"{env_prefix}_DOMAIN", "") or ""

        rows.append({
            "provider_id": provider_id,
            "enabled": int(enabled),
            "domain": domain,
            "display_name": entry["display_name"],
        })
    return rows


def _build_provider_rows_for(entries: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Same as _build_provider_rows but for a specific subset of providers."""
    rows: list[dict[str, Any]] = []
    for entry in entries:
        provider_id = entry["id"]
        env_prefix = provider_id.upper()

        enabled = bool(getattr(settings, f"{env_prefix}_ENABLED", False))
        domain = getattr(settings, f"{env_prefix}_DOMAIN", "") or ""

        rows.append({
            "provider_id": provider_id,
            "enabled": int(enabled),
            "domain": domain,
            "display_name": entry["display_name"],
        })
    return rows


def _build_settings_rows() -> dict[str, str]:
    """Build the initial key-value pairs for the ``settings`` table.

    All values are converted to strings (SQLite text affinity).
    """
    return {
        "api_key":                 settings.API_KEY,
        "external_url":            settings.EXTERNAL_URL,
        "tmdb_api_key":            settings.TMDB_API_KEY,
        "google_books_api_key":    settings.GOOGLE_BOOKS_API_KEY,
        "http_proxy":              settings.HTTP_PROXY,
        "rate_limit_per_second":   str(settings.RATE_LIMIT_PER_SECOND),
        "cache_enabled":           str(int(settings.CACHE_ENABLED)),
        "cache_ttl_seconds":       str(settings.CACHE_TTL_SECONDS),
        "default_search_language": settings.DEFAULT_SEARCH_LANGUAGE,
        "domain_check_interval":   str(settings.DOMAIN_CHECK_INTERVAL),
        "log_level":               settings.LOG_LEVEL,
    }


async def migrate_from_env() -> None:
    """Populate the database from environment variables if it is empty.

    This function checks whether the ``provider_config`` table contains any
    rows.  If it is empty, the database is seeded with:

    - One row per known provider (enabled flag + domain + display name).
    - Global application settings (API keys, proxy, cache TTL, …).

    The write is performed under ``write_lock`` to serialise concurrent
    access to the single SQLite connection.

    If the table already has data the function is a safe no-op.
    """
    db = await get_db()

    async with write_lock:
        cursor = await db.execute("SELECT COUNT(*) FROM provider_config")
        row = await cursor.fetchone()
        count = row[0] if row else 0

        if count > 0:
            # DB already populated — but check for new providers not yet seeded
            existing_ids = set()
            cursor = await db.execute("SELECT provider_id FROM provider_config")
            rows = await cursor.fetchall()
            for r in rows:
                existing_ids.add(r[0])

            missing = [p for p in _KNOWN_PROVIDERS if p["id"] not in existing_ids]
            if missing:
                logger.info(
                    "Adding %d new provider(s) to existing database: %s",
                    len(missing),
                    ", ".join(p["id"] for p in missing),
                )
                new_rows = _build_provider_rows_for(missing)
                await db.executemany(
                    "INSERT INTO provider_config (provider_id, enabled, domain, display_name)"
                    " VALUES (?, ?, ?, ?)",
                    [
                        (p["provider_id"], p["enabled"], p["domain"], p["display_name"])
                        for p in new_rows
                    ],
                )
                await db.commit()
                logger.info("Migration update completed — added %d provider(s)", len(missing))
            else:
                logger.info(
                    "Migration skipped — database already contains %d provider(s)",
                    count,
                )
            return

        logger.info("Running initial migration from environment variables …")

        # --- Provider configs -------------------------------------------------
        provider_rows = _build_provider_rows()
        await db.executemany(
            "INSERT INTO provider_config (provider_id, enabled, domain, display_name)"
            " VALUES (?, ?, ?, ?)",
            [
                (p["provider_id"], p["enabled"], p["domain"], p["display_name"])
                for p in provider_rows
            ],
        )

        # --- Global settings --------------------------------------------------
        settings_rows = _build_settings_rows()
        await db.executemany(
            "INSERT INTO settings (key, value) VALUES (?, ?)",
            list(settings_rows.items()),
        )

        await db.commit()

        logger.info(
            "Migration completed — seeded %d providers and %d settings",
            len(provider_rows),
            len(settings_rows),
        )
