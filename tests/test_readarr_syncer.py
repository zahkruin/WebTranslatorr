"""
Tests for ReadarrSyncer — the service that syncs book providers to Readarr.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.services.readarr_syncer import ReadarrSyncer, VIDEO_PROVIDERS


# ────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────


def _make_mock_response(status_code=200, json_data=None, text=""):
    """Build a mock httpx.Response with async-compatible .json()/.raise_for_status()."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=json_data or {})
    resp.text = text
    return resp


def _build_book_providers():
    """Return a list of enabled book provider dicts as ConfigManager would."""
    return [
        {
            "provider_id": "ebookelo",
            "enabled": True,
            "domain": "",
            "display_name": "Ebookelo",
        },
        {
            "provider_id": "epublibre",
            "enabled": True,
            "domain": "",
            "display_name": "EpubLibre",
        },
        {
            "provider_id": "lectulandia",
            "enabled": True,
            "domain": "",
            "display_name": "Lectulandia",
        },
    ]


def _make_config_manager(providers=None):
    """Build a mock ConfigManager returning the given enabled providers."""
    mgr = MagicMock()
    mgr.get_all_enabled_providers = AsyncMock(
        return_value=providers or _build_book_providers()
    )
    return mgr


# ────────────────────────────────────────────────────────────────────────
# test_connection
# ────────────────────────────────────────────────────────────────────────


class TestConnection:
    """Tests for ReadarrSyncer.test_connection()."""

    @pytest.mark.asyncio
    async def test_connection_success_returns_version(self):
        """test_connection() with HTTP 200 should return success and version."""
        config_manager = MagicMock()
        syncer = ReadarrSyncer(config_manager)

        mock_response = _make_mock_response(
            status_code=200, json_data={"version": "0.4.9.2756"}
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        # httpx.AsyncClient is used as async context manager
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_client
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_ctx):
            result = await syncer.test_connection(
                readarr_url="http://readarr:8787", api_key="abc123"
            )

        assert result["success"] is True
        assert result["message"] == "Connected"
        assert result["version"] == "0.4.9.2756"

    @pytest.mark.asyncio
    async def test_connection_timeout_returns_failure(self):
        """test_connection() on TimeoutException should return success=False."""
        config_manager = MagicMock()
        syncer = ReadarrSyncer(config_manager)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_client
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_ctx):
            result = await syncer.test_connection(
                readarr_url="http://readarr:8787", api_key="abc123"
            )

        assert result["success"] is False
        assert "timed out" in result["message"]
        assert result["version"] is None

    @pytest.mark.asyncio
    async def test_connection_http_error_401_returns_failure(self):
        """test_connection() on HTTP 401 should return success=False."""
        config_manager = MagicMock()
        syncer = ReadarrSyncer(config_manager)

        # Simulate raise_for_status triggering HTTPStatusError
        error_response = MagicMock()
        error_response.status_code = 401
        exc = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=error_response
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=exc)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_client
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_ctx):
            result = await syncer.test_connection(
                readarr_url="http://readarr:8787", api_key="abc123"
            )

        assert result["success"] is False
        assert "401" in result["message"]

    @pytest.mark.asyncio
    async def test_connection_unexpected_error_returns_failure(self):
        """test_connection() on generic Exception should return failure."""
        config_manager = MagicMock()
        syncer = ReadarrSyncer(config_manager)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=RuntimeError("boom"))

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_client
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_ctx):
            result = await syncer.test_connection(
                readarr_url="http://readarr:8787", api_key="abc123"
            )

        assert result["success"] is False
        assert "boom" in result["message"]


# ────────────────────────────────────────────────────────────────────────
# sync_all
# ────────────────────────────────────────────────────────────────────────


class TestSyncAll:
    """Tests for ReadarrSyncer.sync_all()."""

    @pytest.mark.asyncio
    async def test_sync_all_creates_new_indexers(self):
        """sync_all() should create indexers for providers not already in Readarr."""
        config_manager = _make_config_manager(_build_book_providers())
        syncer = ReadarrSyncer(config_manager)

        mock_client = AsyncMock()
        # _fetch_existing_indexers returns empty list → all are new
        mock_client.get = AsyncMock(
            return_value=_make_mock_response(status_code=200, json_data=[])
        )
        # _sync_one_indexer → POST for new indexer
        mock_client.post = AsyncMock(
            return_value=_make_mock_response(status_code=201)
        )

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_client
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_ctx):
            result = await syncer.sync_all(
                readarr_url="http://readarr:8787",
                api_key="rdr-key",
                external_url="http://wtr:9811",
                wtr_api_key="wtr-key",
            )

        assert result["success"] is True
        assert result["created"] == 3
        assert result["updated"] == 0
        assert result["failed"] == 0
        assert len(result["details"]) == 3

    @pytest.mark.asyncio
    async def test_sync_all_updates_existing_indexers(self):
        """sync_all() should update indexers that already exist in Readarr."""
        config_manager = _make_config_manager(_build_book_providers())
        syncer = ReadarrSyncer(config_manager)

        # Readarr already has matching indexers
        existing = [
            {"id": 1, "name": "WebTranslatorr - Ebookelo"},
            {"id": 2, "name": "WebTranslatorr - EpubLibre"},
            {"id": 3, "name": "WebTranslatorr - Lectulandia"},
        ]

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            return_value=_make_mock_response(status_code=200, json_data=existing)
        )
        mock_client.put = AsyncMock(
            return_value=_make_mock_response(status_code=200)
        )

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_client
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_ctx):
            result = await syncer.sync_all(
                readarr_url="http://readarr:8787",
                api_key="rdr-key",
                external_url="http://wtr:9811",
                wtr_api_key="wtr-key",
            )

        assert result["success"] is True
        assert result["created"] == 0
        assert result["updated"] == 3
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_sync_all_with_delete_orphans(self):
        """sync_all() with delete_orphans=True should remove orphaned indexers."""
        config_manager = _make_config_manager(
            [
                {
                    "provider_id": "ebookelo",
                    "enabled": True,
                    "domain": "",
                    "display_name": "Ebookelo",
                }
            ]
        )
        syncer = ReadarrSyncer(config_manager)

        # Readarr has Ebookelo AND an orphan from a removed provider
        existing = [
            {"id": 1, "name": "WebTranslatorr - Ebookelo"},
            {"id": 2, "name": "WebTranslatorr - OldProvider"},
        ]

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            return_value=_make_mock_response(status_code=200, json_data=existing)
        )
        mock_client.put = AsyncMock(
            return_value=_make_mock_response(status_code=200)
        )
        mock_client.delete = AsyncMock(
            return_value=_make_mock_response(status_code=200)
        )

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_client
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_ctx):
            result = await syncer.sync_all(
                readarr_url="http://readarr:8787",
                api_key="rdr-key",
                external_url="http://wtr:9811",
                wtr_api_key="wtr-key",
                delete_orphans=True,
            )

        assert result["deleted"] == 1

    @pytest.mark.asyncio
    async def test_sync_all_without_external_url_returns_error(self):
        """sync_all() with empty external_url should return an error."""
        config_manager = _make_config_manager()
        syncer = ReadarrSyncer(config_manager)

        result = await syncer.sync_all(
            readarr_url="http://readarr:8787",
            api_key="rdr-key",
            external_url="",  # empty
            wtr_api_key="wtr-key",
        )

        assert result["success"] is False
        assert result["error"] == "external_url not configured"

    @pytest.mark.asyncio
    async def test_sync_all_without_wtr_api_key_returns_error(self):
        """sync_all() with empty wtr_api_key should return an error."""
        config_manager = _make_config_manager()
        syncer = ReadarrSyncer(config_manager)

        result = await syncer.sync_all(
            readarr_url="http://readarr:8787",
            api_key="rdr-key",
            external_url="http://wtr:9811",
            wtr_api_key="",  # empty
        )

        assert result["success"] is False
        assert result["error"] == "api_key not configured"

    @pytest.mark.asyncio
    async def test_sync_all_filters_video_providers(self):
        """sync_all() should not sync video providers (MejorTorrent, DonTorrent, etc.)."""
        providers = [
            {
                "provider_id": "ebookelo",
                "enabled": True,
                "domain": "",
                "display_name": "Ebookelo",
            },
            {
                "provider_id": "mejortorrent",
                "enabled": True,
                "domain": "",
                "display_name": "MejorTorrent",
            },
            {
                "provider_id": "dontorrent",
                "enabled": True,
                "domain": "",
                "display_name": "DonTorrent",
            },
        ]
        config_manager = _make_config_manager(providers)
        syncer = ReadarrSyncer(config_manager)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            return_value=_make_mock_response(status_code=200, json_data=[])
        )
        mock_client.post = AsyncMock(
            return_value=_make_mock_response(status_code=201)
        )

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_client
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_ctx):
            result = await syncer.sync_all(
                readarr_url="http://readarr:8787",
                api_key="rdr-key",
                external_url="http://wtr:9811",
                wtr_api_key="wtr-key",
            )

        # Only ebookelo should be synced (video providers filtered out)
        assert result["created"] == 1
        synced_ids = {d["provider_id"] for d in result["details"]}
        assert "ebookelo" in synced_ids
        assert "mejortorrent" not in synced_ids
        assert "dontorrent" not in synced_ids

    @pytest.mark.asyncio
    async def test_sync_all_no_enabled_book_providers(self):
        """sync_all() with no enabled book providers should return empty success."""
        # Only video providers enabled
        config_manager = _make_config_manager([])
        syncer = ReadarrSyncer(config_manager)

        result = await syncer.sync_all(
            readarr_url="http://readarr:8787",
            api_key="rdr-key",
            external_url="http://wtr:9811",
            wtr_api_key="wtr-key",
        )

        assert result["success"] is True
        assert result["created"] == 0
        assert result["updated"] == 0

    @pytest.mark.asyncio
    async def test_sync_all_unexpected_error_returns_partial(self):
        """sync_all() wrapping an unexpected exception should return partial results."""
        config_manager = _make_config_manager(_build_book_providers())
        syncer = ReadarrSyncer(config_manager)

        mock_client = AsyncMock()
        # GET existing indexers raises an unexpected error
        mock_client.get = AsyncMock(side_effect=RuntimeError("connection refused"))

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_client
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_ctx):
            result = await syncer.sync_all(
                readarr_url="http://readarr:8787",
                api_key="rdr-key",
                external_url="http://wtr:9811",
                wtr_api_key="wtr-key",
            )

        assert result["success"] is False
        assert "connection refused" in result.get("error", "")


# ────────────────────────────────────────────────────────────────────────
# _build_indexer_payload
# ────────────────────────────────────────────────────────────────────────


class TestBuildIndexerPayload:
    """Tests for ReadarrSyncer._build_indexer_payload()."""

    def test_payload_includes_provider_id_in_url(self):
        """The generated base URL should contain the provider-specific path."""
        config_manager = MagicMock()
        syncer = ReadarrSyncer(config_manager)

        provider = {
            "provider_id": "ebookelo",
            "display_name": "Ebookelo",
            "domain": "",
        }

        payload = syncer._build_indexer_payload(
            provider, "http://wtr:9811", "wtr-key"
        )

        base_url_field = next(
            f for f in payload["fields"] if f["name"] == "baseUrl"
        )
        assert "/ebookelo" in base_url_field["value"]
        assert payload["implementation"] == "Torznab"
        assert payload["protocol"] == "torrent"

    def test_payload_name_starts_with_prefix(self):
        """The indexer name should start with 'WebTranslatorr -'."""
        config_manager = MagicMock()
        syncer = ReadarrSyncer(config_manager)

        provider = {
            "provider_id": "lectulandia",
            "display_name": "Lectulandia",
            "domain": "",
        }

        payload = syncer._build_indexer_payload(
            provider, "http://wtr:9811", "wtr-key"
        )

        assert payload["name"] == "WebTranslatorr - Lectulandia"
