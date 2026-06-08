# 05 — Sistema de Providers

## Propósito

Documenta el sistema de providers: la clase abstracta `BaseProvider`, el `ProviderRegistry` (Service Locator), el ciclo de vida de un provider, y las convenciones que todos los providers deben seguir.

Cuándo consultar: para entender cómo funciona el sistema de providers, crear un nuevo provider, o modificar el comportamiento base.

---

## BaseProvider (Clase Abstracta)

**Archivo:** `app/providers/base.py`

Todo provider debe heredar de `BaseProvider` (ABC) e implementar los métodos abstractos.

### Constructor

```python
def __init__(
    self,
    http_client: HttpClient,
    provider_id: str = None,
    display_name: str = None,
    base_url: str = None,
    categories: list[int] = None,
    **kwargs
):
```

**Parámetros:**
| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `http_client` | Requerido | Instancia compartida de HttpClient |
| `provider_id` | `class.__name__.lower()` | ID único del provider |
| `display_name` | `class.__name__` | Nombre legible |
| `base_url` | `""` | URL base del sitio (puede actualizarse vía DomainResolver) |
| `categories` | `[7000, 7020, 8000, 8010]` | Categorías Newznab por defecto (libros) |

### Métodos Abstractos (DEBEN implementarse)

#### `async search(query, categories, **kwargs) -> list[SearchResult]`

```python
@abstractmethod
async def search(
    self,
    query: str,
    categories: list[int] = None,
    *,
    offset: int = 0,
    limit: int = 50,
    imdb_id: Optional[str] = None,
    tvdb_id: Optional[int] = None,
    season: Optional[int] = None,
    episode: Optional[int] = None,
    author: Optional[str] = None,
    title: Optional[str] = None,
    **kwargs
) -> list[SearchResult]:
```

**Reglas:**
- NUNCA propagar excepciones. Devolver `[]` en caso de error.
- Usar `self.http_client` para requests (rate-limiting integrado).
- No interactuar directamente con Torznab. Solo devolver `SearchResult`.

#### `async get_download_url(internal_id: str, **kwargs) -> str | None`

```python
@abstractmethod
async def get_download_url(self, internal_id: str) -> str:
```

Resuelve la URL final de descarga. `internal_id` es el ID extraído durante la búsqueda.

**Reglas:**
- Devolver `None` si no se puede resolver.
- Para providers de torrent, puede devolver `internal_id` directamente.

### Métodos Opcionales (PUEDEN sobrescribirse)

#### `get_capabilities() -> ProviderCapabilities`

```python
def get_capabilities(self) -> ProviderCapabilities:
    return ProviderCapabilities(
        provider_id=self.provider_id,
        display_name=self.display_name,
        supported_categories=self.categories,
        supported_search_params=["q"],
        supports_movie_search=False,
        supports_tv_search=False,
        supports_book_search=True
    )
```

Default: book search. Los providers de video deben sobrescribir con `supports_movie_search=True` y/o `supports_tv_search=True`.

#### `is_healthy() -> bool`

```python
async def is_healthy(self) -> bool:
    try:
        resp = await self.http_client.get(self.base_url)
        return resp.status_code == 200
    except Exception:
        return False
```

#### `normalize_query(raw_query: str) -> str`

```python
def normalize_query(self, raw_query: str) -> str:
    cleaned = re.sub(r'[^\w\s\-]', ' ', raw_query)
    return ' '.join(cleaned.split()).strip().lower()
```

Limpia el query: elimina caracteres especiales, normaliza espacios, convierte a minúsculas.

### Métodos Helper (proporcionados por BaseProvider)

#### `_combine_query(query, author, title) -> str`

Combina query con author/title si vienen separados (útil para búsquedas de libros):

```python
def _combine_query(self, query: str, author: Optional[str], title: Optional[str]) -> str:
    parts = []
    if author:
        parts.append(author)
    if title:
        parts.append(title)
    if query and not parts:
        parts.append(query)
    elif query and parts:
        if query not in ' '.join(parts):
            parts.append(query)
    return ' '.join(parts)
```

---

## ProviderRegistry (Service Locator)

**Archivo:** `app/providers/registry.py`

Registro central de providers. Patrón Singleton + Service Locator.

### Instancia Global

```python
# app/providers/registry.py:79
registry = ProviderRegistry()
```

### Métodos

#### `register(provider: BaseProvider) -> None`

Registra un provider. Usa `provider.provider_id` como clave.

```python
registry.register(EbookeloProvider(http_client, resolver))
```

#### `get(provider_id: str) -> BaseProvider`

Obtiene un provider por ID. Lanza `ProviderNotFoundError` si no existe.

#### `get_by_categories(categories: list[int]) -> list[BaseProvider]`

Devuelve providers que soporten al menos una de las categorías pedidas. Usa `CategoryMapper.get_parent_category()` para matching por categoría padre.

#### `get_by_content_type(content_type: str) -> list[BaseProvider]`

Filtra por tipo de contenido: `"books"`, `"movies"`, `"tv"`. Usa los flags `supports_book_search`, etc.

#### `get_all() -> list[BaseProvider]`

Devuelve todos los providers registrados.

#### `unregister(provider_id: str) -> None`

Elimina un provider del registro.

#### `clear() -> None`

Limpia todos los providers. Usado antes de reinicializar.

---

## Ciclo de Vida de un Provider

```
1. STARTUP (app/server.py:lifespan)
   ├── Crear HttpClient (compartido)
   ├── Crear DomainResolver
   ├── Registrar DomainConfigs
   └── Llamar torznab._init_providers(resolver)
       ├── Limpiar registry
       ├── Crear instancia de cada provider
       └── Registrar en registry

2. RUNTIME (por cada petición)
   ├── SmartRouter selecciona providers
   ├── search_with_cache() → provider.search()
   │   ├── Cache hit → devolver resultados cacheados
   │   └── Cache miss → provider.search() → guardar en cache
   └── TorznabMapper → XML

3. DOWNLOAD (cuando el usuario selecciona)
   ├── registry.get(provider_id)
   ├── provider.get_download_url(internal_id)
   └── http_client.download_file(url)

4. SHUTDOWN
   └── http_client.close()
```

---

## Lista Completa de Providers

### Books (12 implementados + 2 pendientes)

| Provider ID | Clase | Archivo | is_zipped |
|-------------|-------|---------|-----------|
| `ebookelo` | `EbookeloProvider` | `books/ebookelo.py` | No |
| `epublibre` | `EpubLibreProvider` | `books/epublibre.py` | No |
| `lectulandia` | `LectulandiaProvider` | `books/lectulandia.py` | No |
| `espaebook` | `EspaebookProvider` | `books/espaebook.py` | No |
| `holaebook` | `HolaEbookProvider` | `books/holaebook.py` | **Sí** |
| `annasarchive` | `AnnasArchiveProvider` | `books/annas_archive.py` | No |
| `epubflix1` | `Epubflix1Provider` | `books/epubflix1.py` | No |
| `libgen` | `LibgenProvider` | `books/libgen.py` | No |
| `booobook` | `BooobookProvider` | `books/booobook.py` | No |
| `lectuepublibre5` | `LectuEpubLibre5Provider` | `books/lectuepublibre5.py` | No |
| `mundoepublibre1` | `MundoEpubLibre1Provider` | `books/mundoepublibre1.py` | No |
| `zlibrary` | `ZLibraryProvider` | `books/zlibrary.py` | No |
| `elejandria` | — | *No implementado* | — |
| `gutenberg` | — | *No implementado* | — |

### Video (2 implementados)

| Provider ID | Clase | Archivo |
|-------------|-------|---------|
| `mejortorrent` | `MejorTorrentProvider` | `video/mejortorrent.py` |
| `dontorrent` | `DonTorrentProvider` | `video/dontorrent.py` |

---

## Trampas / Anti-Patrones

1. **No hardcodear URLs** — Usar `self.base_url` (inyectado) o `settings.*_DOMAIN`.
2. **No propagar excepciones** — `search()` debe devolver `[]`, `get_download_url()` debe devolver `None`.
3. **No usar requests/httpx directamente** — Usar `self.http_client` para rate-limiting y retries.
4. **No devolver diccionarios** — Siempre usar el dataclass `SearchResult`.
5. **No olvidar registrar el provider** — En `_init_providers()` y en `DomainConfig` (si aplica).

---

## Archivos Relevantes

| Archivo | Rol |
|---------|-----|
| `app/providers/base.py` | BaseProvider (ABC) |
| `app/providers/registry.py` | ProviderRegistry |
| `app/core/models.py` | SearchResult, ProviderCapabilities |
| `app/api/torznab.py` | Registro de providers en `_init_providers()` |
| `app/server.py` | DomainConfig en startup |
| `config.py` | Settings de enable/disable y dominios |
