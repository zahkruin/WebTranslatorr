# 17 — Guía para Añadir Nuevos Providers

## Propósito

Guía completa paso a paso para añadir un nuevo provider de contenido a WebTranslatorr. Cubre desde la creación del archivo hasta el registro, configuración, domain resolution, y tests.

Cuándo consultar: al implementar un nuevo sitio fuente de libros o video.

---

## Paso 1: Crear el Archivo del Provider

Crear en `app/providers/books/` (libros) o `app/providers/video/` (películas/series):

```python
"""
Provider para NUEVO_SITIO - Descripción.
"""
import re
import logging
from typing import Optional
from datetime import datetime

from bs4 import BeautifulSoup

from app.providers.base import BaseProvider
from app.core.models import SearchResult, ProviderCapabilities
from config import settings

logger = logging.getLogger("provider.NUEVO_ID")


class NuevoProvider(BaseProvider):
    def __init__(self, http_client, domain_resolver=None):
        domain = settings.NUEVO_DOMAIN
        if domain_resolver:
            active_domain = domain_resolver.get_current("NUEVO_ID")
            if active_domain:
                domain = active_domain

        super().__init__(
            provider_id="NUEVO_ID",
            display_name="Nombre Legible",
            base_url=domain,
            http_client=http_client,
            categories=[7000, 7020, 8000, 8010]  # Para libros
            # categories=[2000, 2030, 2040, 2045, 5000, 5030, 5040]  # Para video
        )
```

### Flags especiales

- **`self.is_zipped = True`** — Si el sitio sirve archivos ZIP (se extraen on-the-fly). Ver `HolaEbookProvider`.

---

## Paso 2: Implementar Capacidades

```python
def get_capabilities(self) -> ProviderCapabilities:
    return ProviderCapabilities(
        provider_id=self.provider_id,
        display_name=self.display_name,
        supported_categories=self.categories,
        supported_search_params=["q"],  # Añadir "author", "imdbid", etc. si se soportan
        supports_book_search=True,       # True para libros
        # supports_movie_search=True,    # True para películas
        # supports_tv_search=True,       # True para series
    )
```

---

## Paso 3: Implementar Búsqueda

### Template para WordPress u otros sitios con búsqueda GET:

```python
async def search(
    self,
    query: str,
    categories: list[int] = None,
    *,
    offset: int = 0,
    limit: int = 50,
    **kwargs
) -> list[SearchResult]:
    combined_query = self._combine_query(
        query,
        kwargs.get("author"),
        kwargs.get("title")
    )
    query_to_use = self.normalize_query(combined_query)
    self.logger.info(f"Buscando en NUEVO: '{query_to_use}'")
    if not query_to_use:
        return []

    results = []
    search_url = f"{self.base_url}/?s={query_to_use}"

    try:
        resp = await self.http_client.get(
            search_url,
            use_scraper=True  # Si el sitio tiene Cloudflare
        )
        soup = BeautifulSoup(resp.text, 'lxml')

        seen_urls = set()
        # Ajustar selectores según la estructura del sitio
        for a in soup.select('a[href*="/book/"], h2.entry-title a'):
            href = a.get('href')
            title_text = a.get_text(strip=True)

            if not href or not title_text or href in seen_urls:
                continue
            seen_urls.add(href)

            # Extraer ID interno
            match = re.search(r'/book/([^/]+)/', href)
            internal_id = match.group(1) if match else None
            if not internal_id:
                continue

            result = SearchResult(
                title=title_text,
                guid=f"NUEVO_ID-{internal_id}",
                link=href if href.startswith('http') else f"{self.base_url}{href}",
                download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={internal_id}&fmt=epub",
                size_bytes=1000000,
                pub_date=datetime.now(),
                categories=[7020],
                description=f"Libro: {title_text}",
            )
            results.append(result)

            if len(results) >= limit:
                break

    except Exception as e:
        self.logger.error(f"Error parseando NUEVO: {e}")

    return results[offset:]
```

### Reglas importantes:
- **Nunca propagar excepciones** — Devolver `[]` en caso de error.
- **Usar `self.http_client.get()`** — No usar `httpx` o `requests` directamente.
- **Usar `use_scraper=True`** si el sitio tiene Cloudflare.
- **Usar `seen_urls` o `seen_ids`** para deduplicar.
- **GUID único** — Formato: `"{provider_id}-{internal_id}"`.
- **download_url** — Apuntar al proxy: `f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={internal_id}&fmt=epub"`.

---

## Paso 4: Implementar Descarga

```python
async def get_download_url(self, internal_id: str, **kwargs) -> str | None:
    fmt = kwargs.get('fmt', 'epub').lower()
    detail_url = f"{self.base_url}/book/{internal_id}/"

    try:
        resp = await self.http_client.get(detail_url, use_scraper=True)
        soup = BeautifulSoup(resp.text, 'lxml')

        # Buscar enlace de descarga
        target_text = f"EN {fmt.upper()}"
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True).upper()
            if target_text in text or 'DESCARGAR' in text or 'DOWNLOAD' in text:
                href = a['href']
                if href.startswith('/'):
                    return f"{self.base_url}{href}"
                return href

        # Fallback: enlaces directos a archivos
        for a in soup.find_all('a', href=True):
            if a['href'].endswith(f'.{fmt}'):
                # ...

        self.logger.warning(f"No se encontró enlace de descarga para {internal_id}")
    except Exception as e:
        self.logger.error(f"Error obteniendo download url: {e}")

    return None
```

### Para providers de torrent:

Si el sitio sirve archivos `.torrent` directamente (como MejorTorrent), `get_download_url()` puede devolver `internal_id` directamente:

```python
async def get_download_url(self, internal_id: str) -> str:
    return internal_id  # Ya es la URL del .torrent
```

---

## Paso 5: Añadir Configuración

### En `config.py`:

```python
# Provider enable/disable
NUEVO_ENABLED: bool = True

# Provider domain
NUEVO_DOMAIN: str = "https://nuevo-sitio.com"
```

### En `.env.example`:

```bash
WTR_NUEVO_ENABLED=true
WTR_NUEVO_DOMAIN=https://nuevo-sitio.com
```

---

## Paso 6: Registrar el Provider

### En `app/api/torznab.py` — `_init_providers()`:

```python
from app.providers.books.nuevo import NuevoProvider  # Al inicio del archivo

# En _init_providers():
if settings.NUEVO_ENABLED:
    registry.register(NuevoProvider(http_client, resolver))
```

---

## Paso 7: Registrar DomainConfig (si el dominio es inestable)

### En `app/server.py` — `lifespan()`:

```python
if settings.NUEVO_ENABLED:
    resolver.register_provider(DomainConfig(
        provider_id="NUEVO_ID",
        default_domain=settings.NUEVO_DOMAIN,
        privtree_path="@NUEVO_ID",        # Si existe en privtr.ee
        telegram_channel="CanalNuevo",    # Si existe canal de Telegram
        known_domain_pattern=r"NUEVO_ID\.\w+",
    ))
```

Si el dominio es estable (no cambia frecuentemente), se puede omitir el `DomainConfig`.

---

## Paso 8: Añadir Tests

Crear `tests/test_provider_nuevo.py`:

```python
import pytest
from unittest.mock import AsyncMock

class MockResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

@pytest.mark.asyncio
async def test_search_parses_results():
    provider = NuevoProvider(http_client=AsyncMock())
    mock_html = """<html>...</html>"""
    provider.http_client.get.return_value = MockResponse(mock_html)
    
    results = await provider.search("test", categories=[7020])
    
    assert len(results) > 0
    assert all(hasattr(r, 'title') for r in results)

@pytest.mark.asyncio
async def test_search_handles_errors():
    provider = NuevoProvider(http_client=AsyncMock())
    provider.http_client.get.side_effect = Exception("Error")
    
    results = await provider.search("test", categories=[7020])
    assert results == []

def test_get_capabilities():
    provider = NuevoProvider(http_client=AsyncMock())
    caps = provider.get_capabilities()
    assert caps.supports_book_search
```

---

## Checklist de Implementación

- [ ] Archivo del provider creado en `app/providers/books/` o `app/providers/video/`
- [ ] `get_capabilities()` implementado
- [ ] `search()` implementado (con manejo de errores)
- [ ] `get_download_url()` implementado
- [ ] Provider registrado en `_init_providers()` en `torznab.py`
- [ ] Configuración añadida en `config.py`
- [ ] Variables en `.env.example`
- [ ] DomainConfig en `app/server.py` (si el dominio es inestable)
- [ ] Tests en `tests/test_provider_nuevo.py`
- [ ] Documentación en `.gemini/context/06-provider-strategies/nuevo.md`
- [ ] Probado con `curl "http://localhost:9811/api?t=search&q=test&apikey=xxx"`

---

## Archivos Relevantes

| Archivo | Rol |
|---------|-----|
| `app/providers/base.py` | BaseProvider (ABC) |
| `app/core/models.py` | SearchResult, ProviderCapabilities |
| `app/api/torznab.py` | Registro de providers en `_init_providers()` |
| `app/server.py` | DomainConfig en `lifespan()` |
| `config.py` | Settings del provider |
| `.env.example` | Variables de entorno |
| `context/05-providers-base.md` | Documentación del sistema de providers |
| `context/06-provider-strategies/ebookelo.md` | Ejemplo de provider complejo |
| `context/06-provider-strategies/epublibre.md` | Ejemplo de provider simple |
