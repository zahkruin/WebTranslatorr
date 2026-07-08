"""
Cliente HTTP asíncrono para FlareSolverr.

FlareSolverr es un proxy inverso headless que resuelve challenges de Cloudflare
(incluyendo Turnstile) usando un navegador real. Se despliega como servicio
externo (Docker) y expone una API JSON en /v1.
"""
import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger("scraping.flaresolverr")


class FlareSolverrClient:
    """Cliente asíncrono para la API de FlareSolverr."""

    def __init__(self, base_url: str = None, timeout: int = 60):
        self._base_url = (base_url or settings.FLARESOLVERR_URL).rstrip("/")
        self._timeout = timeout
        self._enabled = bool(self._base_url)
        if self._enabled:
            logger.info(f"FlareSolverr enabled at {self._base_url}")

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def get(self, url: str, session: str = None, max_timeout: int = 60000) -> Optional[dict]:
        """
        Realiza una petición GET a través de FlareSolverr.

        Args:
            url: URL objetivo
            session: ID de sesión para persistencia de cookies (opcional)
            max_timeout: Timeout máximo en ms para FlareSolverr

        Returns:
            dict con 'status_code', 'text', 'headers', 'url' o None si falla
        """
        if not self._enabled:
            return None

        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": max_timeout,
        }
        if session:
            payload["session"] = session

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/v1",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("status") == "ok" and "solution" in data:
                    solution = data["solution"]
                    return {
                        "status_code": solution.get("status", 200),
                        "text": solution.get("response", ""),
                        "headers": dict(solution.get("headers", {})),
                        "url": solution.get("url", url),
                        "cookies": solution.get("cookies", []),
                    }
                else:
                    logger.warning(f"FlareSolverr error for {url}: {data.get('message', 'unknown')}")
                    return None

        except httpx.TimeoutException:
            logger.warning(f"FlareSolverr timeout for {url} (>{self._timeout}s)")
            return None
        except Exception as e:
            logger.warning(f"FlareSolverr request failed for {url}: {e}")
            return None

    async def destroy_session(self, session: str) -> bool:
        """Destruye una sesión de FlareSolverr."""
        if not self._enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{self._base_url}/v1",
                    json={"cmd": "sessions.destroy", "session": session},
                )
                return True
        except Exception:
            return False


# Singleton
_flaresolverr_client: Optional[FlareSolverrClient] = None


def get_flaresolverr_client() -> FlareSolverrClient:
    global _flaresolverr_client
    if _flaresolverr_client is None:
        _flaresolverr_client = FlareSolverrClient()
    return _flaresolverr_client
