# Guía: Añadir Nuevos Providers

## Paso 1: Crear el Provider

Crea un archivo en `app/providers/<tipo>/mi_provider.py`:

```python
from app.providers.base import BaseProvider
from app.core.models import SearchResult, ProviderCapabilities

class MiProvider(BaseProvider):
    provider_id = "miprovider"
    display_name = "Mi Provider"
    
    @property
    def base_url(self) -> str:
        return "https://ejemplo.com"
    
    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_id=self.provider_id,
            display_name=self.display_name,
            supported_categories=[7000, 7020],
            supported_search_params=["q"],
            supports_book_search=True,
        )
    
    async def search(self, query, categories, **kwargs):
        url = self._build_search_url(query)
        response = await self.http_client.get(url)
        return self._parse_results(response.text)
    
    def _build_search_url(self, query: str, page: int = 1) -> str:
        from urllib.parse import quote_plus
        return f"{self.base_url}/buscar/{quote_plus(query)}"
    
    def _parse_results(self, html: str) -> list[SearchResult]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        results = []
        # ... implementar parsing
        return results
    
    async def get_download_url(self, internal_id: str) -> str:
        return f"{self.base_url}/download/{internal_id}"
```

## Paso 2: Registrar el Provider

Edita `app/api/torznab.py` y añade en `_init_providers()`:

```python
if settings.MIPROVIDER_ENABLED:
    from app.providers.books.miprovider import MiProvider
    registry.register(MiProvider(http_client, settings.MIPROVIDER_DOMAIN))
```

## Paso 3: Añadir Configuración

Edita `config.py`:

```python
MIPROVIDER_ENABLED: bool = True
MIPROVIDER_DOMAIN: str = "https://ejemplo.com"
```

Y `.env.example`:

```bash
WTR_MIPROVIDER_ENABLED=true
WTR_MIPROVIDER_DOMAIN=https://ejemplo.com
```

## Paso 4: Añadir Tests

Crea `tests/test_miprovider_provider.py`:

```python
def test_parse_results():
    html = """<html>...</html>"""
    # ... tests
```

## Paso 5: Documentar

Actualiza `.gemini/context/providers.md` con la nueva estrategia.
