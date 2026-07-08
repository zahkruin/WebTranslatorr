"""
Service for synchronising enabled book providers to Readarr as Torznab indexers.

This module emulates Prowlarr's behaviour — it takes every enabled book provider
from WebTranslatorr's configuration and creates (or updates) a corresponding
Torznab indexer in a remote Readarr instance.

Typical usage::

    from app.services.readarr_syncer import ReadarrSyncer

    syncer = ReadarrSyncer(config_manager)
    result = await syncer.sync_all(
        readarr_url="http://readarr:8787",
        api_key="abc123",
        external_url="http://webtranslatorr:9811",
        wtr_api_key="xyz789",
    )
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.config_manager import ConfigManager

logger = logging.getLogger(__name__)

# Provider IDs that belong to video content — these are NEVER synchronised to
# Readarr because Readarr only handles books.
VIDEO_PROVIDERS: set[str] = {"mejortorrent", "dontorrent", "divxtotal", "elitetorrent"}

# Newznab categories that Readarr uses for book queries.
# 7000  = Books / Other
# 7020  = Books / EBook
# 8000  = Books / Other (alt range)
# 8010  = Books / EBook (alt range)
BOOK_CATEGORIES: list[int] = [7000, 7020, 8000, 8010]


class ReadarrSyncer:
    """Syncs enabled book providers to Readarr as Torznab indexers.

    Each enabled book provider is represented as a separate Torznab
    indexer in Readarr.  Video providers (MejorTorrent, DonTorrent,
    DivxTotal, EliteTorrent) are excluded.

    Attributes:
        _config_manager: Reference to the application's ``ConfigManager``
            instance, used to enumerate enabled providers and read
            runtime settings.
    """

    def __init__(self, config_manager: ConfigManager) -> None:
        """Initialise the syncer.

        Args:
            config_manager: The application's configuration manager.
        """
        self._config_manager = config_manager

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def test_connection(self, readarr_url: str, api_key: str) -> dict[str, Any]:
        """Test connectivity with a Readarr instance.

        Performs a ``GET /api/v1/system/status`` against the remote
        Readarr and returns the server version on success.

        Args:
            readarr_url: Base URL of the Readarr instance (e.g.
                ``"http://readarr:8787"``).
            api_key: Readarr's API key.

        Returns:
            A dictionary with the following keys:

            * ``success`` (:class:`bool`) — ``True`` if the instance
              is reachable.
            * ``message`` (:class:`str`) — Human-readable description
              of the result.
            * ``version`` (:class:`str` | ``None``) — Readarr's version
              string, or ``None`` on failure.
        """
        url = f"{readarr_url.rstrip('/')}/api/v1/system/status"
        headers = {"X-Api-Key": api_key}

        try:
            # Quick sanity-check: URL and API key must be ASCII-safe
            readarr_url.encode("ascii")
            api_key.encode("ascii")
        except UnicodeEncodeError as exc:
            logger.warning("Readarr connection test: %s", exc)
            return {"success": False, "message": f"Invalid characters in URL or API key: {exc}", "version": None}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
            version = data.get("version")
            logger.info("Readarr connection test succeeded (version=%s)", version)
            return {"success": True, "message": "Connected", "version": version}
        except httpx.TimeoutException:
            logger.warning("Readarr connection test timed out: %s", readarr_url)
            return {
                "success": False,
                "message": "Connection timed out after 10 seconds",
                "version": None,
            }
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Readarr returned HTTP %d on connection test: %s",
                exc.response.status_code,
                readarr_url,
            )
            return {
                "success": False,
                "message": f"Readarr returned HTTP {exc.response.status_code}",
                "version": None,
            }
        except Exception as exc:
            logger.error("Unexpected error testing Readarr connection: %s", exc)
            return {
                "success": False,
                "message": f"Connection failed: {exc}",
                "version": None,
            }

    async def sync_all(
        self,
        readarr_url: str,
        api_key: str,
        external_url: str,
        wtr_api_key: str,
        delete_orphans: bool = False,
    ) -> dict[str, Any]:
        """Sync all enabled book providers to Readarr.

        Args:
            readarr_url: Base URL of the Readarr instance.
            api_key: Readarr's API key.
            external_url: Publicly-reachable URL of WebTranslatorr,
                used as the base URL in the Torznab indexer payloads.
            wtr_api_key: WebTranslatorr's API key, required so Readarr
                can authenticate when querying the proxy.
            delete_orphans: When ``True``, remove any indexer on the
                Readarr side whose name starts with ``"WebTranslatorr -"``
                but which no longer corresponds to an enabled provider.

        Returns:
            A dictionary with summary information:

            * ``success`` (:class:`bool`)
            * ``created`` (:class:`int`) — number of new indexers created.
            * ``updated`` (:class:`int`) — number of existing indexers
              updated.
            * ``failed`` (:class:`int`) — providers that could not be
              synchronised.
            * ``deleted`` (:class:`int`) — orphaned indexers removed
              (only when ``delete_orphans`` is ``True``).
            * ``details`` (:class:`list` of :class:`dict`) — per-provider
              operation details.
        """
        # Validate required parameters
        if not external_url:
            logger.error("sync_all: external_url not configured")
            return {
                "success": False,
                "created": 0,
                "updated": 0,
                "failed": 0,
                "deleted": 0,
                "details": [],
                "error": "external_url not configured",
            }

        if not wtr_api_key:
            logger.error("sync_all: wtr_api_key not configured")
            return {
                "success": False,
                "created": 0,
                "updated": 0,
                "failed": 0,
                "deleted": 0,
                "details": [],
                "error": "api_key not configured",
            }

        # 1. Get enabled book providers
        all_providers = await self._config_manager.get_all_enabled_providers()
        book_providers = [
            p for p in all_providers if p["provider_id"] not in VIDEO_PROVIDERS
        ]

        if not book_providers:
            logger.info("sync_all: no enabled book providers found")
            return {
                "success": True,
                "created": 0,
                "updated": 0,
                "failed": 0,
                "deleted": 0,
                "details": [],
            }

        readarr_url = readarr_url.rstrip("/")

        created = 0
        updated = 0
        failed = 0
        download_client_ok = False
        details: list[dict[str, Any]] = []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # 2. Fetch existing indexers from Readarr
                existing_indexers = await self._fetch_existing_indexers(
                    client, readarr_url, api_key
                )
                if existing_indexers is None:
                    return {
                        "success": False,
                        "created": 0,
                        "updated": 0,
                        "failed": 0,
                        "deleted": 0,
                        "details": [],
                        "error": "Could not fetch existing indexers from Readarr",
                    }

                # Build a lookup keyed by name for O(1) lookups
                existing_by_name: dict[str, dict[str, Any]] = {}
                for idx in existing_indexers:
                    existing_by_name[idx.get("name", "")] = idx

                # 3. Create or update each provider
                for provider in book_providers:
                    provider_id = provider["provider_id"]
                    payload = self._build_indexer_payload(
                        provider, external_url, wtr_api_key
                    )

                    result = await self._sync_one_indexer(
                        client,
                        readarr_url,
                        api_key,
                        provider_id,
                        payload,
                        existing_by_name,
                    )

                    details.append(result)
                    if result["action"] in ("created", "updated"):
                        if result["action"] == "created":
                            created += 1
                        else:
                            updated += 1
                    else:
                        failed += 1

                # 4. Optionally delete orphans
                synced_names: set[str] = {
                    f"WebTranslatorr - {p['display_name']}" for p in book_providers
                }
                deleted = 0
                if delete_orphans:
                    deleted = await self._delete_orphan_indexers(
                        client,
                        readarr_url,
                        api_key,
                        existing_by_name,
                        synced_names,
                    )

                # 5. Verify download client (does NOT create one)
                download_client_ok = await self._check_download_client(
                    client, readarr_url, api_key
                )

        except Exception as exc:
            logger.exception("Unexpected error during sync_all: %s", exc)
            return {
                "success": False,
                "created": created,
                "updated": updated,
                "failed": failed,
                "deleted": 0,
                "details": details,
                "error": str(exc),
            }

        overall_success = failed == 0
        return {
            "success": overall_success,
            "created": created,
            "updated": updated,
            "failed": failed,
            "deleted": deleted,
            "details": details,
            "download_client_ok": download_client_ok,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_indexer_payload(
        self, provider: dict[str, Any], external_url: str, wtr_api_key: str
    ) -> dict[str, Any]:
        """Build a Torznab-compatible indexer payload for one book provider.

        Args:
            provider: Provider dictionary from ``ConfigManager``.
            external_url: WebTranslatorr's public base URL.
            wtr_api_key: WebTranslatorr's API key.

        Returns:
            A dictionary suitable for ``POST /api/v1/indexer`` on Readarr.
        """
        base_url = external_url.rstrip("/")
        return {
            "enableRss": True,
            "enableAutomaticSearch": True,
            "enableInteractiveSearch": True,
            "name": f"WebTranslatorr - {provider['display_name']}",
            "implementation": "Torznab",
            "implementationName": "Torznab",
            "configContract": "TorznabSettings",
            "protocol": "torrent",
            "priority": 25,
            "tags": [],
            "fields": [
                {
                    "name": "baseUrl",
                    "value": f"{base_url}/{provider['provider_id']}",
                },
                {"name": "apiKey", "value": wtr_api_key},
                {"name": "multiLanguages", "value": []},
                {"name": "categories", "value": list(BOOK_CATEGORIES)},
                {"name": "animeCategories", "value": []},
                {"name": "minimumSeeders", "value": 1},
            ],
        }

    async def _check_download_client(
        self, client: httpx.AsyncClient, readarr_url: str, api_key: str
    ) -> bool:
        """Check if a Torrent Blackhole download client exists in Readarr.

        Does NOT create one — the user must configure it manually.
        Logs a warning if no compatible client is found so the user
        knows downloads will not work without one.

        Returns ``True`` if a client named ``"WebTranslatorr"`` exists.
        """
        headers = {"X-Api-Key": api_key}

        try:
            resp = await client.get(
                f"{readarr_url}/api/v1/downloadclient", headers=headers
            )
            resp.raise_for_status()
            existing = resp.json()
        except Exception as exc:
            logger.warning("Could not check download clients in Readarr: %s", exc)
            return False

        for dc in existing:
            if dc.get("name") == "WebTranslatorr" and dc.get("implementation") == "TorrentBlackhole":
                logger.info("Torrent Blackhole 'WebTranslatorr' found in Readarr (id=%s)", dc.get("id"))
                return True

        logger.warning(
            "No 'WebTranslatorr' Torrent Blackhole download client found in Readarr. "
            "Downloads will fail until one is created manually. "
            "In Readarr: Settings → Download Clients → + → Torrent Blackhole → "
            "Name: WebTranslatorr, Torrent Folder: /downloads/blackhole"
        )
        return False

    async def _fetch_existing_indexers(
        self, client: httpx.AsyncClient, readarr_url: str, api_key: str
    ) -> list[dict[str, Any]] | None:
        """Retrieve the list of indexers currently configured in Readarr.

        Args:
            client: Shared :class:`httpx.AsyncClient`.
            readarr_url: Base URL of the Readarr instance.
            api_key: Readarr's API key.

        Returns:
            A list of indexer dictionaries, or ``None`` on error.
        """
        # Sanitise inputs — HTTP headers and URLs must be ASCII-safe
        try:
            readarr_url.encode("ascii")
        except UnicodeEncodeError:
            logger.error(
                "Readarr URL contains non-ASCII characters: %r", readarr_url
            )
            return None
        try:
            api_key.encode("ascii")
        except UnicodeEncodeError:
            logger.error(
                "Readarr API key contains non-ASCII characters (input encoding issue)"
            )
            return None

        url = f"{readarr_url}/api/v1/indexer"
        headers = {"X-Api-Key": api_key}

        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            logger.error("Timeout fetching indexers from Readarr at %s", readarr_url)
            return None
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Readarr returned HTTP %d when fetching indexers from %s",
                exc.response.status_code,
                readarr_url,
            )
            return None
        except (UnicodeEncodeError, UnicodeDecodeError) as exc:
            logger.error(
                "Encoding error fetching indexers from Readarr at %s: %s",
                readarr_url, exc,
            )
            return None
        except Exception as exc:
            logger.error(
                "Error fetching indexers from Readarr at %s: %s",
                readarr_url, exc,
            )
            return None

    async def _sync_one_indexer(
        self,
        client: httpx.AsyncClient,
        readarr_url: str,
        api_key: str,
        provider_id: str,
        payload: dict[str, Any],
        existing_by_name: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Create or update a single Torznab indexer in Readarr.

        Args:
            client: Shared :class:`httpx.AsyncClient`.
            readarr_url: Base URL of the Readarr instance.
            api_key: Readarr's API key.
            provider_id: WebTranslatorr's internal provider identifier.
            payload: The indexer payload dictionary.
            existing_by_name: Lookup of existing indexers keyed by name.

        Returns:
            A result dictionary with ``provider_id``, ``indexer_name``,
            ``action`` (``"created"``, ``"updated"``, or ``"error"``),
            and ``message``.
        """
        indexer_name: str = payload["name"]
        url = f"{readarr_url}/api/v1/indexer"
        headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}

        existing = existing_by_name.get(indexer_name)

        try:
            if existing is not None:
                # Update existing indexer — preserve its ID
                payload["id"] = existing["id"]
                response = await client.put(
                    f"{url}/{existing['id']}",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                logger.info(
                    "Updated indexer '%s' (id=%d) in Readarr",
                    indexer_name,
                    existing["id"],
                )
                return {
                    "provider_id": provider_id,
                    "indexer_name": indexer_name,
                    "action": "updated",
                    "message": "Indexer updated successfully",
                }
            else:
                # Create new indexer
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                logger.info("Created indexer '%s' in Readarr", indexer_name)
                return {
                    "provider_id": provider_id,
                    "indexer_name": indexer_name,
                    "action": "created",
                    "message": "Indexer created successfully",
                }
        except httpx.TimeoutException:
            logger.error("Timeout syncing indexer '%s'", indexer_name)
            return {
                "provider_id": provider_id,
                "indexer_name": indexer_name,
                "action": "error",
                "message": "Request timed out",
            }
        except httpx.HTTPStatusError as exc:
            # Capture Readarr's validation error details from response body
            error_detail = ""
            try:
                error_detail = exc.response.text[:500]
            except Exception:
                pass
            logger.error(
                "HTTP %d syncing indexer '%s': %s  body=%s",
                exc.response.status_code,
                indexer_name,
                exc,
                error_detail,
            )
            return {
                "provider_id": provider_id,
                "indexer_name": indexer_name,
                "action": "error",
                "message": f"Readarr returned HTTP {exc.response.status_code}: {error_detail[:200]}",
            }
        except Exception as exc:
            logger.error("Error syncing indexer '%s': %s", indexer_name, exc)
            return {
                "provider_id": provider_id,
                "indexer_name": indexer_name,
                "action": "error",
                "message": str(exc),
            }

    async def _delete_orphan_indexers(
        self,
        client: httpx.AsyncClient,
        readarr_url: str,
        api_key: str,
        existing_by_name: dict[str, dict[str, Any]],
        synced_names: set[str],
    ) -> int:
        """Remove Readarr indexers that no longer correspond to any provider.

        Only indexers whose name starts with ``"WebTranslatorr -"`` are
        candidates for deletion.

        Args:
            client: Shared :class:`httpx.AsyncClient`.
            readarr_url: Base URL of the Readarr instance.
            api_key: Readarr's API key.
            existing_by_name: All existing indexers keyed by name.
            synced_names: Set of indexer names that are current.

        Returns:
            The number of orphan indexers deleted.
        """
        prefix = "WebTranslatorr -"
        headers = {"X-Api-Key": api_key}

        deleted = 0
        for name, idx_data in existing_by_name.items():
            if not name.startswith(prefix):
                continue
            if name in synced_names:
                continue

            idx_id = idx_data["id"]
            url = f"{readarr_url}/api/v1/indexer/{idx_id}"
            try:
                response = await client.delete(url, headers=headers)
                response.raise_for_status()
                logger.info("Deleted orphan indexer '%s' (id=%d)", name, idx_id)
                deleted += 1
            except Exception as exc:
                logger.error("Failed to delete orphan indexer '%s': %s", name, exc)

        return deleted
