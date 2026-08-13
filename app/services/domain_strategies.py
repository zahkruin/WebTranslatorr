"""
Estrategias de resolución de dominios para providers con URLs inestables.

Cada estrategia intenta descubrir el dominio funcional actual de un provider
usando una fuente de información diferente. Se ejecutan en orden de prioridad
con fallback automático.
"""

import re
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup

from urllib.parse import urlparse


logger = logging.getLogger("domain.strategies")


@dataclass
class DomainConfig:
    """Configuración de resolución de un provider."""
    provider_id: str
    default_domain: str
    privtree_path: Optional[str] = None         # ej: "@mejortorrent"
    telegram_channel: Optional[str] = None       # ej: "MejorTorrentAp"
    shadowlibraries_path: Optional[str] = None   # ej: "DirectDownloads/AnnasArchive/"
    known_domain_pattern: str = ""               # regex: r"mejortorrent\.\w+"
    current_domain: Optional[str] = None
    mirrors: list[str] = field(default_factory=list)


class DomainStrategy(ABC):
    """Interfaz base para estrategias de resolución de dominio."""

    @staticmethod
    def _extract_hostname(url: str) -> str:
        from urllib.parse import urlparse
        return (urlparse(url).hostname or "").lower()

    @staticmethod
    def _hostname_matches(hostname: str, pattern: str) -> bool:
        if not hostname or not pattern:
            return False
        if pattern.startswith("^"):
            anchored = pattern
        else:
            anchored = rf"^[\w.-]*(?:{pattern})$"
        return bool(re.match(anchored, hostname, re.IGNORECASE))

    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre legible de la estrategia."""
        ...

    @abstractmethod
    async def resolve(self, config: DomainConfig, http_client) -> Optional[str]:
        """
        Intenta resolver el dominio actual del provider.

        Returns:
            URL base completa (ej: "https://dontorrent.reisen") o None si falla.
        """
        ...


class PrivtreeStrategy(DomainStrategy):
    """
    Estrategia primaria: scraping de privtr.ee.

    Ambos sitios mantienen una landing page en privtr.ee con el dominio actual.
    Es la fuente más fiable y con HTML más simple de parsear.

    - MejorTorrent: privtr.ee/@mejortorrent → enlace directo al dominio
    - DonTorrent: privtr.ee/@dontorrent → enlace con texto "Dominio Actual"
    """

    @property
    def name(self) -> str:
        return "privtree"

    async def resolve(self, config: DomainConfig, http_client) -> Optional[str]:
        if not config.privtree_path:
            return None

        url = f"https://privtr.ee/{config.privtree_path}"
        logger.debug(f"[privtree] Fetching {url}")

        try:
            response = await http_client.get(url)
            soup = BeautifulSoup(response.text, "lxml")

            # Buscar enlaces que matcheen el patrón del dominio del provider
            for link in soup.find_all("a", href=True):
                href = link["href"]
                hostname = self._extract_hostname(href)
                if self._hostname_matches(hostname, config.known_domain_pattern):
                    domain = self._normalize_url(href)
                    logger.info(f"[privtree] Resolved {config.provider_id} → {domain}")
                    return domain

            logger.warning(f"[privtree] No matching domain found for {config.provider_id}")
            return None

        except Exception as e:
            logger.warning(f"[privtree] Failed for {config.provider_id}: {e}")
            return None

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Normaliza la URL: esquema + dominio, sin path."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"


class TelegramPublicStrategy(DomainStrategy):
    """
    Estrategia secundaria: scraping del canal público de Telegram.

    Los canales públicos de Telegram tienen una vista web en t.me/s/{channel}
    accesible sin cuenta ni API key. El último mensaje generalmente contiene
    el dominio más reciente.

    - @MejorTorrentAp: publica el dominio como enlace
    - @DonTorrent: cada mensaje es simplemente una URL del nuevo dominio
    """

    @property
    def name(self) -> str:
        return "telegram"

    async def resolve(self, config: DomainConfig, http_client) -> Optional[str]:
        if not config.telegram_channel:
            return None

        url = f"https://t.me/s/{config.telegram_channel}"
        logger.debug(f"[telegram] Fetching {url}")

        try:
            response = await http_client.get(url)
            soup = BeautifulSoup(response.text, "lxml")

            messages = soup.find_all("div", class_="tgme_widget_message_wrap")

            for message in reversed(messages):
                for link in message.find_all("a", href=True):
                    href = link["href"]
                    hostname = self._extract_hostname(href)
                    if self._hostname_matches(hostname, config.known_domain_pattern):
                        domain = self._normalize_url(href)
                        logger.info(
                            f"[telegram] Resolved {config.provider_id} → {domain}"
                        )
                        return domain

            all_links = soup.find_all("a", href=True)
            matching = []
            for link in all_links:
                href = link["href"]
                hostname = self._extract_hostname(href)
                if self._hostname_matches(hostname, config.known_domain_pattern):
                    matching.append(href)

            if matching:
                # El último match suele ser el más reciente
                domain = self._normalize_url(matching[-1])
                logger.info(
                    f"[telegram] Resolved {config.provider_id} → {domain} (fallback parse)"
                )
                return domain

            logger.warning(
                f"[telegram] No matching domain found for {config.provider_id}"
            )
            return None

        except Exception as e:
            logger.warning(f"[telegram] Failed for {config.provider_id}: {e}")
            return None

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Normaliza la URL: esquema + dominio, sin path."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"


class ShadowLibrariesStrategy(DomainStrategy):
    """
    Estrategia de resolución vía scraping de shadowlibraries.github.io.

    ShadowLibraries mantiene una lista estática de mirrors para ciertos
    providers en GitHub Pages. Escrapea la página de GitHub Pages,
    extrae los enlaces que coincidan con el patrón del dominio y los valida.
    Prioridad máxima para providers que usan este método (ej: annasarchive).
    """

    BASE_URL = "https://shadowlibraries.github.io"

    @property
    def name(self) -> str:
        return "shadowlibraries"

    async def resolve(self, config: DomainConfig, http_client) -> Optional[str]:
        if not config.shadowlibraries_path:
            return None

        url = f"{self.BASE_URL}/{config.shadowlibraries_path}"
        logger.debug(f"[shadowlibraries] Fetching {url}")

        try:
            response = await http_client.get(url)
            soup = BeautifulSoup(response.text, "lxml")

            pattern = re.compile(config.known_domain_pattern, re.IGNORECASE)
            candidates = []

            for link in soup.select('a[href*="annas-archive"]'):
                href = link.get("href", "")
                if pattern.search(href):
                    parsed = urlparse(href)
                    domain = f"{parsed.scheme}://{parsed.netloc}"
                    if domain not in candidates:
                        candidates.append(domain)

            for domain in candidates:
                logger.debug(f"[shadowlibraries] Validating candidate: {domain}")
                try:
                    resp = await http_client.head(domain, follow_redirects=True, timeout=10)
                    if resp.status_code < 400:
                        logger.info(f"[shadowlibraries] Resolved {config.provider_id} → {domain}")
                        return domain
                except Exception as e:
                    logger.debug(f"[shadowlibraries] Candidate {domain} failed: {e}")

            logger.warning(f"[shadowlibraries] No valid domain found for {config.provider_id}")
            return None

        except Exception as e:
            logger.warning(f"[shadowlibraries] Failed for {config.provider_id}: {e}")
            return None


class HealthCheckStrategy(DomainStrategy):
    """
    Estrategia de último recurso: verificar que el dominio conocido sigue vivo.

    Hace un HTTP HEAD al dominio actual. Si responde (200, 301, 302),
    sigue el redirect si lo hay y devuelve el dominio final.
    Si no responde, devuelve None.
    """

    @property
    def name(self) -> str:
        return "healthcheck"

    async def resolve(self, config: DomainConfig, http_client) -> Optional[str]:
        domain = config.current_domain or config.default_domain
        logger.debug(f"[healthcheck] Checking {domain}")

        try:
            response = await http_client.head(
                domain, follow_redirects=True, timeout=10
            )
            if response.status_code < 400:
                # Si hubo redirects, usar el dominio final
                final_url = str(response.url)
                from urllib.parse import urlparse
                parsed = urlparse(final_url)
                resolved = f"{parsed.scheme}://{parsed.netloc}"
                logger.info(
                    f"[healthcheck] {config.provider_id} alive at {resolved}"
                )
                return resolved

            logger.warning(
                f"[healthcheck] {config.provider_id} returned {response.status_code}"
            )
            return None

        except Exception as e:
            logger.warning(
                f"[healthcheck] {config.provider_id} unreachable: {e}"
            )
            return None


# Orden predeterminado de estrategias (de mayor a menor fiabilidad)
DEFAULT_STRATEGIES: list[DomainStrategy] = [
    ShadowLibrariesStrategy(),
    PrivtreeStrategy(),
    TelegramPublicStrategy(),
    HealthCheckStrategy(),
]
