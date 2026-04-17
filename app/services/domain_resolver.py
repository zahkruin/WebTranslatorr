"""
Servicio central de resolución dinámica de dominios.

Orquesta múltiples estrategias de resolución con fallback automático,
valida los dominios candidatos con HTTP HEAD, y persiste los resultados
en data/domains.json para sobrevivir reinicios.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable, Awaitable

from app.services.domain_strategies import (
    DomainConfig,
    DomainStrategy,
    DEFAULT_STRATEGIES,
)

logger = logging.getLogger("domain.resolver")


@dataclass
class ResolvedDomain:
    """Estado actual de un dominio resuelto."""
    url: str
    resolved_at: str            # ISO 8601 string para serialización JSON
    source: str                 # "privtree" | "telegram" | "healthcheck" | "config" | "persisted"
    healthy: bool = True
    last_health_check: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ResolvedDomain":
        return cls(**data)


class DomainResolver:
    """
    Resuelve dominios dinámicos para providers con URLs inestables.

    Utiliza una cadena de estrategias con fallback:
    1. privtr.ee (landing page oficial)
    2. Canal público de Telegram (t.me/s/)
    3. Health check del dominio conocido

    Los dominios resueltos se persisten en disco para sobrevivir reinicios.
    """

    def __init__(
        self,
        http_client,
        strategies: Optional[list[DomainStrategy]] = None,
        persistence_path: str = "data/domains.json",
        validation_timeout: int = 10,
    ):
        self._http_client = http_client
        self._strategies = strategies or DEFAULT_STRATEGIES
        self._persistence_path = Path(persistence_path)
        self._validation_timeout = validation_timeout
        self._configs: dict[str, DomainConfig] = {}
        self._resolved: dict[str, ResolvedDomain] = {}
        self._lock = asyncio.Lock()
        self._callbacks: list[Callable[[str, str], Awaitable[None]]] = []

        # Cargar dominios persistidos al iniciar
        self._load_persisted()

    def register_provider(self, config: DomainConfig) -> None:
        """Registra un provider para resolución dinámica de dominio."""
        self._configs[config.provider_id] = config
        logger.info(
            f"Registered domain config: {config.provider_id} "
            f"(default: {config.default_domain})"
        )

        # Si ya tenemos un dominio persistido, usarlo como resuelto
        if config.provider_id not in self._resolved:
            self._resolved[config.provider_id] = ResolvedDomain(
                url=config.default_domain,
                resolved_at=datetime.now(timezone.utc).isoformat(),
                source="config",
            )

    def on_domain_change(
        self, callback: Callable[[str, str], Awaitable[None]]
    ) -> None:
        """
        Registra un callback para cuando un dominio cambie.
        callback(provider_id, new_domain)
        """
        self._callbacks.append(callback)

    def get_current(self, provider_id: str) -> str:
        """
        Devuelve el dominio actual resuelto para un provider.
        Es síncrono para que los providers lo puedan usar fácilmente.
        """
        if provider_id in self._resolved:
            return self._resolved[provider_id].url

        if provider_id in self._configs:
            return self._configs[provider_id].default_domain

        raise ValueError(f"Provider '{provider_id}' not registered for domain resolution")

    def get_status(self, provider_id: Optional[str] = None) -> dict:
        """Devuelve el estado de resolución de uno o todos los providers."""
        if provider_id:
            if provider_id in self._resolved:
                return {provider_id: self._resolved[provider_id].to_dict()}
            return {provider_id: None}

        return {
            pid: rd.to_dict() for pid, rd in self._resolved.items()
        }

    async def resolve(self, provider_id: str) -> str:
        """
        Resuelve el dominio actual de un provider usando la cadena de estrategias.
        Valida cada candidato con HTTP HEAD antes de aceptarlo.
        """
        async with self._lock:
            config = self._configs.get(provider_id)
            if not config:
                raise ValueError(
                    f"Provider '{provider_id}' not registered for domain resolution"
                )

            old_domain = self.get_current(provider_id)

            # Intentar cada estrategia en orden
            for strategy in self._strategies:
                logger.debug(
                    f"Trying strategy '{strategy.name}' for {provider_id}"
                )
                candidate = await strategy.resolve(config, self._http_client)

                if not candidate:
                    continue

                # Validar el candidato si no viene del healthcheck
                # (el healthcheck ya valida internamente)
                if strategy.name != "healthcheck":
                    is_valid = await self._validate_domain(candidate)
                    if not is_valid:
                        logger.warning(
                            f"Candidate {candidate} from '{strategy.name}' "
                            f"failed validation, trying next strategy"
                        )
                        continue

                # Dominio válido encontrado
                now = datetime.now(timezone.utc).isoformat()
                self._resolved[provider_id] = ResolvedDomain(
                    url=candidate,
                    resolved_at=now,
                    source=strategy.name,
                    healthy=True,
                    last_health_check=now,
                )

                self._persist()

                # Notificar si el dominio cambió
                if candidate != old_domain:
                    logger.info(
                        f"Domain CHANGED for {provider_id}: "
                        f"{old_domain} → {candidate} (via {strategy.name})"
                    )
                    await self._notify_change(provider_id, candidate)
                else:
                    logger.debug(
                        f"Domain confirmed for {provider_id}: {candidate} "
                        f"(via {strategy.name})"
                    )

                return candidate

            # Ninguna estrategia funcionó: mantener el último conocido
            logger.warning(
                f"All strategies failed for {provider_id}. "
                f"Keeping last known domain: {old_domain}"
            )
            return old_domain

    async def resolve_all(self) -> dict[str, str]:
        """Resuelve los dominios de todos los providers registrados."""
        results = {}
        for provider_id in self._configs:
            try:
                domain = await self.resolve(provider_id)
                results[provider_id] = domain
            except Exception as e:
                logger.error(f"Failed to resolve {provider_id}: {e}")
                results[provider_id] = self.get_current(provider_id)
        return results

    async def health_check(self, provider_id: str) -> bool:
        """Comprueba si el dominio actual del provider sigue vivo."""
        domain = self.get_current(provider_id)
        is_healthy = await self._validate_domain(domain)

        if provider_id in self._resolved:
            self._resolved[provider_id].healthy = is_healthy
            self._resolved[provider_id].last_health_check = (
                datetime.now(timezone.utc).isoformat()
            )
            self._persist()

        if not is_healthy:
            logger.warning(
                f"Health check FAILED for {provider_id} at {domain}"
            )

        return is_healthy

    async def _validate_domain(self, url: str) -> bool:
        """Valida que un dominio responda correctamente con HTTP HEAD."""
        try:
            response = await self._http_client.head(
                url,
                follow_redirects=True,
                timeout=self._validation_timeout,
            )
            return response.status_code < 400
        except Exception as e:
            logger.debug(f"Validation failed for {url}: {e}")
            return False

    async def _notify_change(self, provider_id: str, new_domain: str) -> None:
        """Notifica a todos los callbacks registrados sobre el cambio."""
        for callback in self._callbacks:
            try:
                await callback(provider_id, new_domain)
            except Exception as e:
                logger.error(f"Domain change callback error: {e}")

    def _persist(self) -> None:
        """Guarda los dominios resueltos en disco."""
        try:
            self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                pid: rd.to_dict() for pid, rd in self._resolved.items()
            }
            self._persistence_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.debug(f"Persisted domains to {self._persistence_path}")
        except Exception as e:
            logger.error(f"Failed to persist domains: {e}")

    def _load_persisted(self) -> None:
        """Carga los dominios persistidos desde disco."""
        if not self._persistence_path.exists():
            logger.debug("No persisted domains file found")
            return

        try:
            data = json.loads(
                self._persistence_path.read_text(encoding="utf-8")
            )
            for pid, rd_data in data.items():
                self._resolved[pid] = ResolvedDomain.from_dict(rd_data)
            logger.info(
                f"Loaded {len(self._resolved)} persisted domains: "
                + ", ".join(
                    f"{pid}={rd.url}" for pid, rd in self._resolved.items()
                )
            )
        except Exception as e:
            logger.error(f"Failed to load persisted domains: {e}")


async def domain_check_loop(
    resolver: DomainResolver, interval: int = 1800
) -> None:
    """
    Loop de verificación periódica de dominios.
    Se ejecuta como tarea de background en el event loop de FastAPI.

    Args:
        resolver: Instancia del DomainResolver.
        interval: Segundos entre verificaciones (default: 30 min).
    """
    logger.info(f"Domain check loop started (interval: {interval}s)")
    while True:
        await asyncio.sleep(interval)
        try:
            logger.info("Running scheduled domain resolution...")
            results = await resolver.resolve_all()
            logger.info(
                f"Scheduled resolution complete: "
                + ", ".join(f"{k}={v}" for k, v in results.items())
            )
        except Exception as e:
            logger.error(f"Scheduled domain resolution failed: {e}")
