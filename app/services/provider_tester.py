"""
Connectivity tester for individual provider base URLs.

Mirrors the "Test" button behaviour found in Jackett / Prowlarr:
  1. Sends an HTTP HEAD to the provider's base URL (fast, no body).
  2. Falls back to HTTP GET if HEAD is rejected.
  3. Classifies the result (ok, timeout, auth_required, dns_error, …).
  4. Persists the last result to the ``provider_config`` table so the
     admin UI can render it on next page load without re-testing.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

from app.providers.registry import registry as provider_registry
from app.scraping.http_client import HttpClient
from app.services.config_manager import ConfigManager
from app.core.exceptions import ProviderNotFoundError

logger = logging.getLogger(__name__)

TEST_TIMEOUT = 10  # seconds per provider


@dataclass
class ProviderTestResult:
    provider_id: str
    status: str
    http_status: int | None = None
    latency_ms: int | None = None
    error_message: str | None = None
    tested_at: str | None = None
    url_tested: str | None = None


class ProviderTester:
    """Runs a lightweight HTTP connectivity check against a provider's base URL."""

    def __init__(self, http_client: HttpClient, config_manager: ConfigManager) -> None:
        self.http_client = http_client
        self.config_manager = config_manager

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def test_provider(self, provider_id: str) -> ProviderTestResult:
        """Test connectivity for a single provider and persist the result."""
        start = time.perf_counter()
        url: str | None = None

        try:
            provider = provider_registry.get(provider_id)
            url = provider.base_url

            if not url:
                return self._build_result(
                    provider_id, "error",
                    latency_from=start,
                    error_message="No URL configured",
                    url_tested=None,
                )

            # Phase 1 — HEAD (fast, no body download)
            status_code: int | None = None
            head_error: str | None = None

            try:
                head_resp = await asyncio.wait_for(
                    self.http_client.head(url, timeout=TEST_TIMEOUT),
                    timeout=TEST_TIMEOUT,
                )
                status_code = head_resp.status_code
            except asyncio.TimeoutError:
                head_error = "timeout"
            except Exception as exc:
                head_error = str(exc)

            # Phase 2 — GET fallback if HEAD failed
            if head_error is not None:
                try:
                    get_resp = await asyncio.wait_for(
                        self.http_client.get(url, timeout=TEST_TIMEOUT),
                        timeout=TEST_TIMEOUT,
                    )
                    status_code = get_resp.status_code
                    head_error = None  # GET succeeded — clear the error
                except asyncio.TimeoutError:
                    result = self._build_result(
                        provider_id, "timeout",
                        latency_from=start,
                        error_message=f"Timeout after {TEST_TIMEOUT}s",
                        url_tested=url,
                    )
                    await self._save_result(result)
                    return result
                except Exception as exc:
                    result = self._build_result(
                        provider_id, "error",
                        latency_from=start,
                        error_message=self._classify_error(exc),
                        url_tested=url,
                    )
                    await self._save_result(result)
                    return result

            # Both phases failed — should not reach here normally, but guard
            if head_error is not None or status_code is None:
                result = self._build_result(
                    provider_id, "error",
                    latency_from=start,
                    error_message=head_error or "Unknown error",
                    url_tested=url,
                )
                await self._save_result(result)
                return result

            # --- Success path: we have a status_code ---
            latency_ms = int((time.perf_counter() - start) * 1000)

            result = ProviderTestResult(
                provider_id=provider_id,
                http_status=status_code,
                latency_ms=latency_ms,
                tested_at=datetime.now(timezone.utc).isoformat(),
                url_tested=url,
            )

            result.status = self._classify_status(status_code, result)

            await self._save_result(result)
            return result

        except ProviderNotFoundError:
            return self._build_result(
                provider_id, "error",
                latency_from=start,
                error_message="Provider not found in registry",
                url_tested=None,
            )
        except Exception as exc:
            return self._build_result(
                provider_id, "error",
                latency_from=start,
                error_message=self._classify_error(exc),
                url_tested=url,
            )

    async def test_all_providers(self) -> list[ProviderTestResult]:
        """Test every enabled provider in parallel.

        Individual providers that raise exceptions are captured and returned
        as failed ``ProviderTestResult`` entries — one slow provider never
        blocks the others.
        """
        enabled = await self.config_manager.get_all_enabled_providers()
        provider_ids = [p["provider_id"] for p in enabled if p.get("enabled")]

        if not provider_ids:
            return []

        tasks = [self.test_provider(pid) for pid in provider_ids]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[ProviderTestResult] = []
        for pid, item in zip(provider_ids, gathered):
            if isinstance(item, BaseException):
                results.append(
                    self._build_result(
                        pid, "error",
                        error_message=self._classify_error(item),
                    )
                )
            else:
                results.append(item)

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _classify_status(
        self, status_code: int, result: ProviderTestResult
    ) -> str:
        """Map an HTTP status code to a human-readable status label."""
        if 200 <= status_code < 300:
            return "ok"
        if status_code in (401, 403):
            result.error_message = f"HTTP {status_code} — authentication required"
            return "auth_required"
        if status_code in (301, 302, 307, 308):
            result.error_message = f"HTTP {status_code} — unexpected redirect"
            return "error"
        if 400 <= status_code < 500:
            result.error_message = f"HTTP {status_code} — client error"
            return "error"
        if 500 <= status_code < 600:
            result.error_message = f"HTTP {status_code} — server error"
            return "error"
        result.error_message = f"HTTP {status_code}"
        return "error"

    @staticmethod
    def _classify_error(error: BaseException) -> str:
        """Translate low-level network exceptions into user-facing messages."""
        msg = str(error)
        lower = msg.lower()

        if "name or service not known" in lower or "getaddrinfo" in lower:
            return f"DNS error: {msg}"
        if "connection refused" in lower:
            return f"Connection refused: {msg}"
        if "connection reset" in lower:
            return f"Connection reset: {msg}"
        if "ssl" in lower or "certificate" in lower:
            return f"SSL error: {msg}"
        if "timeout" in lower:
            return f"Timeout: {msg}"

        return msg[:200]

    @staticmethod
    def _build_result(
        provider_id: str,
        status: str,
        *,
        latency_from: float | None = None,
        latency_ms: int | None = None,
        error_message: str | None = None,
        url_tested: str | None = None,
    ) -> ProviderTestResult:
        if latency_ms is None and latency_from is not None:
            latency_ms = int((time.perf_counter() - latency_from) * 1000)
        return ProviderTestResult(
            provider_id=provider_id,
            status=status,
            latency_ms=latency_ms,
            error_message=error_message,
            tested_at=datetime.now(timezone.utc).isoformat(),
            url_tested=url_tested,
        )

    async def _save_result(self, result: ProviderTestResult) -> None:
        """Persist the test outcome to the ``provider_config`` table."""
        from app.persistence.database import get_db
        from app.persistence.models import save_test_result

        try:
            db = await get_db()
            await save_test_result(
                db,
                provider_id=result.provider_id,
                status=result.status,
                http_status=result.http_status,
                latency_ms=result.latency_ms,
                error_message=result.error_message,
                tested_at=result.tested_at or "",
                url_tested=result.url_tested,
            )
        except Exception:
            logger.exception(
                "Failed to persist test result for %s", result.provider_id
            )
