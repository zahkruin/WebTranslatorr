# 11 — Search Cache

## Propósito

Documenta el `SearchCache`, un caché TTL (Time-To-Live) para resultados de búsqueda que reduce el scraping redundante de queries repetitivas.

Cuándo consultar: para depurar problemas de caché (resultados stale, invalidación), ajustar TTL, o entender qué se cachea y qué no.

---

## Arquitectura

```
SearchCache (Singleton)
    │
    ├── cachetools.TTLCache
    │   ├── maxsize: 512 entradas
    │   └── ttl: 300 segundos (5 min, configurable)
    │
    ├── Clave compuesta: "{provider_id}|{normalized_query}|{sorted_categories}"
    │
    └── Operaciones: get(), set(), invalidate()
```

---

## Constructor

**Archivo:** `app/services/cache.py:21-23`

```python
def __init__(self, maxsize: int = 512, ttl: int = 300):
    self._cache: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl)
    self._enabled = settings.CACHE_ENABLED
```

- `maxsize=512`: máximo 512 entradas en caché (LRU eviction)
- `ttl=300`: entradas expiran después de 5 minutos
- `_enabled`: controlado por `WTR_CACHE_ENABLED`

---

## Estructura de Clave

**Archivo:** `app/services/cache.py:25-27`

```python
def _make_key(self, provider_id: str, query: str, categories: Optional[list[int]]) -> str:
    cat_part = ",".join(str(c) for c in sorted(categories)) if categories else ""
    return f"{provider_id}|{query}|{cat_part}"
```

**Ejemplos de claves:**
| Provider | Query | Categories | Clave |
|----------|-------|------------|-------|
| ebookelo | `quijote` | `[7000,7020]` | `ebookelo|quijote|7000,7020` |
| mejortorrent | `inception` | `[2000,2030]` | `mejortorrent|inception|2000,2030` |
| epublibre | `harry potter` | `[]` | `epublibre|harry potter|` |

**IMPORTANTE:** La clave incluye las categorías. Si Readarr busca el mismo query con diferentes categorías, se consideran entradas de caché distintas.

---

## Operaciones

### `get(provider_id, query, categories) → list | None`

**Archivo:** `app/services/cache.py:29-34`

```python
def get(self, provider_id: str, query: str, categories: Optional[list[int]] = None):
    if not self._enabled:
        return None
    key = self._make_key(provider_id, query, categories)
    return self._cache.get(key)
```

Devuelve `None` si:
- La caché está deshabilitada (`CACHE_ENABLED=false`)
- No hay entrada para esa clave
- La entrada expiró (TTL vencido)

### `set(provider_id, query, results, categories)`

**Archivo:** `app/services/cache.py:36-42`

```python
def set(self, provider_id: str, query: str, results, categories: Optional[list[int]] = None):
    if not self._enabled:
        return
    key = self._make_key(provider_id, query, categories)
    self._cache[key] = results
    logger.debug(f"Cached {len(results)} results for {key}")
```

Almacena la lista de `SearchResult` en caché.

### `invalidate(provider_id, query=None)`

**Archivo:** `app/services/cache.py:44-47`

```python
def invalidate(self, provider_id: str, query: str = None):
    logger.debug(f"Cache invalidation requested for {provider_id}")
```

**IMPORTANTE:** `TTLCache` no soporta invalidación por patrón. Este método es un no-op (solo loggea). Para invalidar realmente, habría que iterar todas las claves o usar otro backend de caché.

---

## Integración con el Endpoint

**Archivo:** `app/api/torznab.py:168-190`

```python
async def search_with_cache(provider, **kw):
    # Intentar cache primero
    cached = search_cache.get(provider.provider_id, q, parsed_cats)
    if cached is not None:
        logging.debug(f"Cache hit for {provider.provider_id} / '{q}'")
        return cached
    
    # Cache miss → hacer la búsqueda real
    try:
        results = await asyncio.wait_for(
            provider.search(**kw),
            timeout=SEARCH_TIMEOUT_SECONDS,
        )
        # Guardar en cache
        if isinstance(results, list):
            search_cache.set(provider.provider_id, q, results, parsed_cats)
        return results
    except ...:
        return []
```

**Flujo:**
1. Intentar obtener de caché
2. Si hay cache hit → devolver resultados cacheados (sin hacer request HTTP)
3. Si cache miss → ejecutar `provider.search()` con timeout de 45s
4. Guardar resultados en caché

---

## Instancia Global

```python
# app/services/cache.py:51-54
search_cache = SearchCache(
    maxsize=512,
    ttl=settings.CACHE_TTL_SECONDS,
)
```

Una sola instancia compartida por todos los providers.

---

## Configuración Relacionada

| Variable | Campo | Default | Impacto |
|----------|-------|---------|---------|
| `WTR_CACHE_ENABLED` | `CACHE_ENABLED` | `True` | Habilitar/deshabilitar caché |
| `WTR_CACHE_TTL_SECONDS` | `CACHE_TTL_SECONDS` | `300` | Tiempo de vida de entradas (5 min) |

---

## Qué NO se Cachea

- Resultados de `get_download_url()` — Las URLs de descarga pueden ser temporales
- Health checks
- Resolución de dominios
- Errores / excepciones (solo se cachean resultados exitosos)

---

## Trampas / Problemas Conocidos

1. **Invalidación limitada** — `TTLCache` no soporta invalidación por patrón. El método `invalidate()` es un no-op. Para forzar refresco, hay que esperar al TTL o reiniciar el servidor.

2. **No hay distinción por offset/limit** — La clave no incluye offset/limit. Si se busca con `offset=0` y luego con `offset=50`, se devuelven los mismos resultados cacheados. La paginación se aplica después en `_handle_torznab_request()`.

3. **La caché es en memoria** — Si hay múltiples workers/instancias, cada una tiene su propia caché.

4. **Resultados stale** — Si un sitio web añade/quita contenido, la caché seguirá devolviendo resultados antiguos hasta que el TTL expire.

---

## Archivos Relevantes

| Archivo | Rol |
|---------|-----|
| `app/services/cache.py` | Implementación del SearchCache |
| `app/api/torznab.py` | Integración caché en el endpoint |
| `config.py` | Settings: CACHE_ENABLED, CACHE_TTL_SECONDS |
