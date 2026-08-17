# Sistema de Providers

## BaseProvider (Clase Abstracta)

Todo provider debe heredar de `BaseProvider` e implementar:

```python
@property
def provider_id(self) -> str
@property
def display_name(self) -> str
@property
def base_url(self) -> str

def get_capabilities(self) -> ProviderCapabilities
async def search(self, query, categories, **kwargs) -> list[SearchResult]
async def get_download_url(self, internal_id: str) -> str
```

## ProviderRegistry

Registro central (patrón Service Locator):

```python
from app.providers.registry import registry

# Registrar
registry.register(MyProvider(http_client))

# Obtener
provider = registry.get("provider_id")

# Filtrar por categorías
providers = registry.get_by_categories([7000, 7020])
```

## Cómo Crear un Nuevo Provider

1. Crear archivo en `app/providers/<tipo>/mi_provider.py`
2. Heredar de `BaseProvider`
3. Implementar métodos abstractos
4. Registrar en `app/api/torznab.py` en `_init_providers()`

Ejemplo mínimo:

```python
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
        # Implementar lógica de búsqueda
        url = self._build_search_url(query)
        response = await self.http_client.get(url)
        return self._parse_results(response.text)
    
    def _build_search_url(self, query: str, page: int = 1) -> str:
        return f"{self.base_url}/buscar/{quote_plus(query)}"
    
    def _parse_results(self, html: str) -> list[SearchResult]:
        # Parsear HTML y devolver SearchResults
        pass
    
    async def get_download_url(self, internal_id: str) -> str:
        # Resolver URL final de descarga
        pass
```

## Ciclo de Vida

1. **Inicialización**: HTTP client se pasa en constructor
2. **Búsqueda**: `search()` retorna lista de `SearchResult` (sin resolver URLs finales)
3. **Enriquecimiento**: Opcional, visitar páginas de detalle para más metadata
4. **Descarga**: `get_download_url()` resuelve URL final cuando el usuario selecciona

## Capabilities

Cada provider declara qué soporta:

- `supported_categories`: lista de IDs Newznab
- `supported_search_params`: parámetros que entiende (q, author, imdbid, etc.)
- `supports_book_search`, `supports_tv_search`, `supports_movie_search`: booleanos
