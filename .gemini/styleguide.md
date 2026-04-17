# Guía de Estilo - WebTranslatarr

## Convenciones de Código

### Async/Await
- Todo I/O debe ser asíncrono
- Usar `async def` para métodos que hacen requests HTTP
- Usar `await asyncio.gather()` para paralelizar búsquedas

### Type Hints
- Todos los métodos públicos deben tener type hints
- Usar `Optional[T]` para valores que pueden ser None
- Importar desde `typing` (Python 3.9+ style compatible)

```python
from typing import Optional

def search(self, query: str, categories: list[int]) -> list[SearchResult]:
    ...
```

### Naming
- `snake_case` para variables, funciones, métodos
- `PascalCase` para clases
- `UPPER_CASE` para constantes
- Prefijos para propiedades privadas: `_nombre`

### Estructura de Providers

```python
class MiProvider(BaseProvider):
    # Propiedades de clase
    provider_id = "id_corto"
    display_name = "Nombre Legible"
    
    def get_capabilities(self) -> ProviderCapabilities:
        # Documentar qué soporta
        pass
    
    async def search(self, ...):
        # 1. Construir URL
        # 2. Hacer request
        # 3. Parsear
        # 4. Retornar SearchResults
        pass
```

## Manejo de Errores

- Usar excepciones personalizadas en `app.core.exceptions`
- Loggear errores con `self.logger` (no print)
- Nunca dejar que una excepción cruda llegue al usuario - envolver en XML de error

```python
from app.core.exceptions import ScrapingError

try:
    response = await self.http_client.get(url)
except Exception as e:
    self.logger.error(f"Error en búsqueda: {e}")
    return []  # Devolver lista vacía, no propagar error
```

## Logging

- Obtener logger: `self.logger = logging.getLogger(f"provider.{self.provider_id}")`
- Niveles:
  - `info`: Provider registrado, búsqueda iniciada
  - `warning`: Enriquecimiento falló, rate limit
  - `error`: Request falló, parsing error

## Docstrings

Usar Google-style docstrings:

```python
def search(self, query: str, categories: list[int], **kwargs) -> list[SearchResult]:
    """
    Busca contenido en el provider.
    
    Args:
        query: Término de búsqueda
        categories: Lista de IDs de categoría Newznab
        **kwargs: Parámetros adicionales (imdb_id, season, etc.)
    
    Returns:
        Lista de SearchResult
    """
```
