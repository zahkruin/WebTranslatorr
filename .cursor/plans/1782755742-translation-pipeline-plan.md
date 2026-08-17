# Plan: Pipeline de Traducción Literaria (Cascada 4 Fases)

> **ID**: PLAN-20260629-001
> **Fecha**: 2026-06-29
> **Origen**: Petición del usuario — implementar un sistema de cascada (fallback) con 4 fases para traducir títulos de libros (inglés → español) antes de que los providers realicen el scraping. Fases: Caché Local → Wikidata → Google Books → Limpieza de Strings.
> **Estado**: aprobado

---

## 1. Análisis de impacto

### Módulos afectados
| Módulo | Tipo de afectación | Criticidad |
|--------|-------------------|------------|
| M7 — Services | Nuevo archivo `app/services/translation_pipeline.py` (~450 LOC) | Alta — nueva funcionalidad core de traducción |
| M2 — Core & Config | Modificación `config.py` (5 nuevas variables) | Media — cambios de configuración |
| M1 — API Layer | Modificación opcional `app/api/torznab.py` (inyección del pipeline en el flujo de búsqueda) | Media — punto de integración |
| M6 — Scraping | Sin cambios directos, pero el pipeline usará `httpx` (ya dependencia existente) | Baja — sin impacto |
| Tests | Nuevo archivo `tests/test_translation_pipeline.py` | Alta — tests unitarios requeridos |
| Tests | Nuevo archivo `tests/integration/test_translation_pipeline_live.py` (opcional) | Baja — tests de integración condicionales |

### Dependencias impactadas
- **Internas**: `app/services/translation_pipeline.py` dependerá de `config.py` (Settings), `httpx` (ya en el proyecto), `aiosqlite` (nueva dependencia externa)
- **Externas**: `aiosqlite>=0.20.0` — nueva dependencia de paquete para SQLite async
- **APIs externas**: Wikidata SPARQL + REST, Google Books API

---

## 2. Plan de implementación

### Paso 1: Añadir dependencia y configuración
- **Archivos**: `config.py` (modificar), `requirements.txt` (modificar)
- **Descripción**: Añadir `aiosqlite>=0.20.0` a `requirements.txt`. Añadir 5 nuevas variables de configuración a `Settings`: `TRANSLATION_CACHE_PATH`, `TRANSLATION_PIPELINE_TIMEOUT`, `GOOGLE_BOOKS_API_KEY`, `TRANSLATION_PIPELINE_WIKIDATA_ENABLED`, `TRANSLATION_PIPELINE_GOOGLE_BOOKS_ENABLED`.
- **Depende de**: ninguno
- **Agente asignado**: core
- **Consideraciones**: Seguir el prefijo `WTR_` y las convenciones de nombres existentes. Valores por defecto seguros (timeout=10, paths vacíos para usar defaults calculados).

### Paso 2: Implementar módulo TranslationCache (Fase 1)
- **Archivos**: `app/services/translation_pipeline.py` (crear)
- **Descripción**: Implementar clase `TranslationCache` con SQLite vía `aiosqlite`. Incluye: `_normalize()`, `_compute_hash()` (SHA256), `connect()`, `_create_schema()`, `close()`, `get()`, `set()`, `invalidate_one()`, `stats()`. Soporta async context manager. Tabla `translation_cache` con índice único en `title_en_hash`. Modo WAL para lecturas concurrentes.
- **Depende de**: Paso 1
- **Agente asignado**: services
- **Consideraciones**: Hashing determinístico con normalización (lowercase, sin puntuación, espacios colapsados). Bloqueo con `asyncio.Lock` en escrituras. Campo `hit_count` y `last_hit_at` para estadísticas.

### Paso 3: Implementar WikidataClient (Fase 2)
- **Archivos**: `app/services/translation_pipeline.py` (añadir clase)
- **Descripción**: Cliente SPARQL + REST para Wikidata. Método `get_spanish_title(title_en, author)`. Estrategia en dos pasos: (1) buscar QID con SPARQL filtrando por `wdt:P31/wdt:P279* wd:Q571` (instancia de libro) y `rdfs:label` en inglés; (2) extraer label en español vía `Special:EntityData/{qid}.json`. Todas las excepciones capturadas, retorna `None` en caso de error.
- **Depende de**: Paso 2
- **Agente asignado**: services
- **Consideraciones**: Usar `httpx.AsyncClient` compartido. Timeout configurable. Escapar comillas en query SPARQL. User-Agent identificativo. Rate limit implícito (el caché reduce volumen).

### Paso 4: Implementar GoogleBooksClient (Fase 3)
- **Archivos**: `app/services/translation_pipeline.py` (añadir clase)
- **Descripción**: Cliente para Google Books API. Método `get_spanish_title(title_en, author)`. Query con `intitle:"TITLE"+inauthor:"AUTHOR"`, `langRestrict=es`, `maxResults=3`, `printType=books`. Extrae título del primer resultado. Manejo explícito de HTTP 429 (rate limit) y 403 (auth/billing). Todas las excepciones capturadas.
- **Depende de**: Paso 3
- **Agente asignado**: services
- **Consideraciones**: Requiere API key de Google Cloud. Si no se proporciona, la fase 3 se deshabilita. Timeout configurable.

### Paso 5: Implementar TitleCleaner (Fase 4)
- **Archivos**: `app/services/translation_pipeline.py` (añadir clase)
- **Descripción**: Clase con método estático `clean(raw_title)` que aplica 11 patrones regex en cascada: eliminar "[Edición de bolsillo]", "[Kindle Edition]", "(Spanish Edition)", años entre paréntesis, ": A Novel", " - Vol. X", etc. Si un patrón vacía el título, revierte al valor anterior. Colapsa espacios múltiples al final.
- **Depende de**: Paso 4
- **Agente asignado**: services
- **Consideraciones**: Patrones ordenados de más específico a más genérico. La reversión garantiza que nunca se pierda el título original. Logging cuando se modifica el título.

### Paso 6: Implementar TranslationPipeline (Orquestador)
- **Archivos**: `app/services/translation_pipeline.py` (añadir clase)
- **Descripción**: Clase principal que orquesta la cascada. Async context manager que inicializa `httpx.AsyncClient`, `TranslationCache`, `WikidataClient`, `GoogleBooksClient`. Método `translate(title_en, author)` que ejecuta: Fase 1 (cache) → HIT: retorna `TranslationResult(source="cache", confidence=1.0)`; MISS: Fase 2 (wikidata) → HIT: guarda en caché y retorna `TranslationResult(source="wikidata", confidence=0.95)`; MISS: Fase 3 (google books) → HIT: aplica TitleCleaner, guarda en caché y retorna `TranslationResult(source="google_books", confidence=0.70)`; MISS: retorna `None`. Métodos auxiliares: `get_stats()`, `invalidate()`.
- **Depende de**: Pasos 2, 3, 4, 5
- **Agente asignado**: services
- **Consideraciones**: `TranslationResult` como dataclass inmutable con campos `title_es`, `source`, `confidence`. El pipeline completo es un async context manager para gestión limpia de recursos.

### Paso 7: Escribir tests unitarios
- **Archivos**: `tests/test_translation_pipeline.py` (crear)
- **Descripción**: Tests con mocks para todas las clases: `TranslationCache` (insert/get/invalidate con SQLite `:memory:`), `TitleCleaner` (casos con/sin basura, caso extremo título vacío), `WikidataClient` (mock de httpx: respuesta válida, sin label español, vacía, timeout, error HTTP), `GoogleBooksClient` (mock de httpx: respuesta válida, sin items, 429, timeout), `TranslationPipeline` (orquestador con mocks: cache hit, wikidata hit, google hit, all miss, sin API key).
- **Depende de**: Pasos 1-6
- **Agente asignado**: testing
- **Consideraciones**: Usar `pytest-asyncio` para tests async. Fixtures para cliente httpx mockeado. Cobertura ≥85%.

### Paso 8: (Opcional) Integrar en el flujo de búsqueda
- **Archivos**: `app/api/torznab.py` (modificar opcional)
- **Descripción**: Inyectar `TranslationPipeline` en el endpoint de búsqueda de libros. Antes de pasar el query al SmartRouter, llamar a `pipeline.translate(query, author_from_params)` y usar el `title_es` resultante como `effective_query`.
- **Depende de**: Paso 6
- **Agente asignado**: api
- **Consideraciones**: Este paso es opcional para el MVP. El pipeline puede usarse de forma independiente sin modificar los endpoints existentes. Requiere que Readarr envíe el parámetro `author` (actualmente no garantizado).

### Paso 9: Actualizar documentación y CHANGELOG
- **Archivos**: `CHANGELOG.md` (modificar)
- **Descripción**: Registrar la nueva funcionalidad en CHANGELOG como `Added` (MINOR bump).
- **Depende de**: Pasos 1-6
- **Agente asignado**: versioning
- **Consideraciones**: Bump MINOR: nueva funcionalidad compatible hacia atrás.

---

## 3. Consideraciones de arquitectura

### Patrones a aplicar
- **Cascade/Fallback Pattern**: El pipeline implementa una cadena de responsabilidad donde cada fase intenta resolver la traducción y falla silenciosamente a la siguiente.
- **Async Context Manager**: `TranslationPipeline` como context manager async para gestión limpia de ciclo de vida (conexión BD, cliente HTTP).
- **Repository Pattern**: `TranslationCache` abstrae el almacenamiento SQLite detrás de una interfaz async limpia (`get`, `set`, `invalidate`).
- **Circuit Breaker implícito**: Cada fase externa captura todas las excepciones y retorna `None`, evitando que un fallo en cascada tumbe el scraper.

### Convenciones a seguir
- **Async/await para todo I/O** (convención del proyecto)
- **Type hints en todos los métodos públicos** (convención del proyecto)
- **Google-style docstrings** (convención del proyecto)
- **Logging con `self._logger`** (convención del proyecto)
- **NUNCA propagar excepciones** desde llamadas externas (convención de providers, aplicable aquí)
- **snake_case para variables, PascalCase para clases**

### Restricciones tecnológicas
- Python 3.11+ (runtime del proyecto)
- `httpx` ya es dependencia del proyecto (usado por `HttpClient`)
- `aiosqlite` es la única dependencia nueva
- SQLite es ubicuo (stdlib) y no requiere servidor externo

### Integración con módulos existentes
- El pipeline es autocontenido en `app/services/translation_pipeline.py`
- Usa `config.py` para Settings (mismo patrón que `cache.py` y `domain_resolver.py`)
- Usa `httpx.AsyncClient` (mismo patrón que `http_client.py`)
- Puede ser inyectado en `app/api/torznab.py` o usado standalone

---

## 4. Riesgos identificados

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Wikidata SPARQL endpoint inestable o lento | Media | Bajo — solo retrasa la cascada, no la rompe | Timeout de 10s; si falla, se pasa a Google Books |
| Google Books API sin API key o cuota excedida | Alta | Bajo — la fase 3 se convierte en no-op | El pipeline funciona con solo caché + Wikidata; Google Books es opcional si no hay API key |
| Colisiones de hash SHA256 (title_en + author) | Muy baja | Medio — devolvería traducción incorrecta | SHA256 tiene 2^256 espacio; probabilidad de colisión astronómicamente baja con volúmenes de libros |
| Títulos con caracteres Unicode que rompan la normalización | Media | Bajo — títulos no encontrados en caché | La normalización usa `re.UNICODE`; el fallback a Wikidata/Google Books maneja el caso |
| Rate limit de Google Books (1000 req/día gratuitas) | Media | Medio — sin caché, se agotaría rápido | El caché reduce drásticamente las llamadas; solo se consulta Google Books en cache miss + wikidata miss |
| Título vacío después de TitleCleaner | Baja | Bajo — se perdería el título | Mecanismo de reversión: si un patrón vacía el título, se revierte al valor anterior |
| Concurrencia en escrituras SQLite | Media | Medio — posible corrupción | `asyncio.Lock` en todas las escrituras; modo WAL para lecturas concurrentes seguras |
| El pipeline bloquea el event loop de FastAPI | Baja | Alto — degradaría todo el servidor | Todas las operaciones son async; SQLite con aiosqlite no bloquea; httpx es async nativo |

---

## 5. Estrategia de testing

### Tests unitarios necesarios

1. **TranslationCache** (`:memory:` SQLite):
   - `test_normalize` — casos con mayúsculas, puntuación, espacios múltiples, Unicode
   - `test_hash_deterministic` — mismo input → mismo hash
   - `test_hash_different` — inputs distintos → hashes distintos
   - `test_set_and_get` — insertar y recuperar
   - `test_get_miss` — buscar entrada inexistente
   - `test_hit_count_increments` — múltiples gets incrementan el contador
   - `test_invalidate` — borrar entrada y verificar miss
   - `test_stats` — entries y hits correctos

2. **TitleCleaner**:
   - `test_no_basura` — título limpio sin cambios
   - `test_edicion_bolsillo` — "[Edición de bolsillo]" eliminado
   - `test_spanish_edition` — "(Spanish Edition)" eliminado
   - `test_año_entre_parentesis` — "(2020)" eliminado
   - `test_a_novel` — ": A Novel" eliminado
   - `test_kindle_edition` — "[Kindle Edition]" eliminado
   - `test_multiples_patrones` — combinación de varios patrones
   - `test_titulo_vacio_revierte` — patrón que vacía el título → revierte
   - `test_espacios_colapsados` — múltiples espacios → uno

3. **WikidataClient** (mock httpx):
   - `test_found_with_spanish_label` — respuesta SPARQL con QID + EntityData con label "es"
   - `test_found_no_spanish_label` — QID válido pero sin label en español
   - `test_not_found` — SPARQL sin resultados
   - `test_sparql_timeout` — timeout → None
   - `test_sparql_http_error` — HTTP 500 → None
   - `test_entitydata_http_error` — EntityData falla → None

4. **GoogleBooksClient** (mock httpx):
   - `test_found_with_title` — respuesta con items[0].volumeInfo.title
   - `test_not_found` — respuesta sin items
   - `test_rate_limit_429` — HTTP 429 → None y log error
   - `test_auth_error_403` — HTTP 403 → None y log error
   - `test_timeout` — timeout → None
   - `test_result_sin_title` — items[0] sin volumeInfo.title → None

5. **TranslationPipeline** (orquestador con mocks):
   - `test_cache_hit` — mock cache retorna valor; NO se llaman wikidata ni google
   - `test_cache_miss_wikidata_hit` — cache miss → wikidata hit → guarda en cache → NO llama a google
   - `test_cache_miss_wikidata_miss_google_hit` — cache miss → wikidata miss → google hit → limpieza → guarda en cache
   - `test_all_miss` — cache miss → wikidata miss → google miss → retorna None
   - `test_no_google_api_key` — sin API key, google books es None → solo fases 1 y 2
   - `test_confidence_values` — cache=1.0, wikidata=0.95, google=0.70

### Tests de integración necesarios (opcionales, requieren red)

- `test_wikidata_live_known_book` — "The Lord of the Rings" + "Tolkien" → label español
- `test_wikidata_live_no_spanish` — libro sin traducción al español
- `test_google_books_live` — requiere API key en variable de entorno
- `test_full_pipeline_live` — integración completa con BD en `:memory:`

### Casos límite a cubrir
- Título vacío → None
- Autor vacío → buscar solo por título
- Título con caracteres Unicode (chino, árabe, cirílico) → normalización no rompe
- Título con comillas dobles → escapado correcto en SPARQL
- Título muy largo (>500 caracteres) → truncado o manejado

### Tests existentes que deben actualizarse
- Ninguno. El pipeline es un módulo nuevo sin impacto en tests existentes.

---

## 6. Estrategia de versionado

- **Tipo de bump estimado**: MINOR
- **Justificación**: Nueva funcionalidad compatible hacia atrás. No se modifican APIs públicas existentes. No se cambian esquemas de respuesta. No se requieren nuevas variables de entorno obligatorias (todas tienen defaults seguros). La dependencia `aiosqlite` es nueva pero opcional (el módulo solo se carga si se usa).

---

## 7. Agentes involucrados

| Agente | Rol | Orden de intervención |
|--------|-----|---------------------|
| core | Añadir configuración y dependencia `aiosqlite` | 1 |
| services | Implementar `translation_pipeline.py` completo (5 clases) | 2 |
| testing | Escribir tests unitarios con mocks | 3 |
| api | (Opcional) Integrar pipeline en endpoint de búsqueda | 4 |
| versioning | Actualizar CHANGELOG.md (MINOR bump) | 5 |
| auditor | Verificar coherencia de la implementación final | 6 |

---

## 8. Alternativas consideradas

| Alternativa | Ventajas | Desventajas | Motivo de descarte |
|-------------|----------|-------------|-------------------|
| **cachetools.TTLCache en lugar de SQLite** | Sin dependencia externa, ya está en el proyecto | No persiste entre reinicios; se pierde el caché en cada deploy | El caché de traducciones es valioso y acumulativo; perderlo en cada reinicio obliga a reconsultar APIs externas |
| **`requests` síncrono en lugar de `httpx` async** | Más simple, sin async/await | Bloquearía el event loop de FastAPI; inconsistente con el resto del proyecto | El proyecto es 100% async; mezclar código síncrono degradaría el rendimiento global |
| **Usar solo Google Books (sin Wikidata)** | Más simple, una sola API | Wikidata es gratuito, sin rate limit, y a menudo tiene mejor cobertura de títulos literarios | Wikidata proporciona traducciones oficiales de alta calidad sin coste; es un excelente primer filtro antes de Google Books |
| **Usar la API de OpenLibrary** | Gratuito, buena cobertura | API menos fiable, tiempos de respuesta erráticos, datos a veces desactualizados | Wikidata tiene una comunidad de editores más activa y datos más estructurados para traducciones |
| **Usar Redis como caché en lugar de SQLite** | Más rápido, soporte nativo para TTL | Requiere infraestructura adicional (servidor Redis); mayor complejidad operativa | SQLite es autocontenido, no requiere servidor, y es suficientemente rápido para este volumen (<100k entradas) |
| **Cache en memoria (dict) sin persistencia** | Máxima velocidad | Se pierde en cada reinicio; sin historial de hits | El valor del caché crece con el tiempo; perderlo es desperdiciar consultas previas |
| **Integrar traducción en cada provider individualmente** | Control fino por provider | Requiere modificar 20 providers; duplicación de lógica; inconsistencia | Centralizar en un pipeline llamado desde el endpoint o el router es más mantenible |

---

## 9. Referencias

### Documentación relacionada
- `.cursor/AGENTS.md` — Convenciones del proyecto (async/await, type hints, logging, anti-patrones)
- `.cursor/analysis/03-modules.md` — M7 (Services) es el módulo destino
- `.cursor/analysis/04-agent-mapping.md` — Agente `services` es el responsable de `app/services/`
- `config.py` — Settings existentes (patrón a seguir)
- `app/services/cache.py` — SearchCache existente (patrón de referencia para el nuevo módulo)
- `app/scraping/http_client.py` — HttpClient existente (usa httpx, mismo patrón de cliente HTTP)

### APIs externas documentadas
- Wikidata SPARQL: https://query.wikidata.org/sparql
- Wikidata EntityData: https://www.wikidata.org/wiki/Special:EntityData/{qid}.json
- Google Books API: https://developers.google.com/books/docs/v1/using

### Errores previos relacionados (CENTRAL_ERROR_REGISTRY)
- Sin entradas relevantes (el registro está vacío — primera implementación de este tipo)

---

## 10. Diagrama de Arquitectura de la Solución

```
┌─────────────────────────────────────────────────────────────┐
│                    TranslationPipeline                       │
│                                                              │
│  translate(title_en, author) → TranslationResult | None     │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ FASE 1: TranslationCache (SQLite)                    │   │
│  │   Lookup table: translation_cache                    │   │
│  │   Key: SHA256(normalize(title_en) | author)          │   │
│  │   → HIT: return (source="cache", confidence=1.0)     │   │
│  │   → MISS: continue                                   │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           ▼                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ FASE 2: WikidataClient                               │   │
│  │   SPARQL: find QID by title + author (instance book) │   │
│  │   REST: get Spanish label for QID                    │   │
│  │   → FOUND: set_cache() → return (source="wikidata")  │   │
│  │   → NOT FOUND / ERROR: continue                      │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           ▼                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ FASE 3: GoogleBooksClient                            │   │
│  │   GET ?q=intitle:TITLE+inauthor:AUTHOR               │   │
│  │       &langRestrict=es&maxResults=3                  │   │
│  │   → FOUND: proceed to FASE 4                         │   │
│  │   → NOT FOUND / ERROR: return None                   │   │
│  └──────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           ▼                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ FASE 4: TitleCleaner (aplicada a resultado de FASE 3)│   │
│  │   11 regex patterns en cascada:                      │   │
│  │   - [Edición de bolsillo] → ""                       │   │
│  │   - (Spanish Edition) → ""                           │   │
│  │   - (2020) → ""                                      │   │
│  │   - : A Novel → ""                                   │   │
│  │   - ... (8 más)                                      │   │
│  │   → set_cache() → return (source="google_books")     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  FALLBACK TOTAL: return None                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 11. Código de Referencia (Resumen)

Ver el plan completo en la respuesta del orquestador para los bloques de código detallados de:
- `TranslationCache` (~120 líneas): SQLite async con normalización y hashing
- `WikidataClient` (~90 líneas): SPARQL + REST
- `GoogleBooksClient` (~80 líneas): Google Books API
- `TitleCleaner` (~55 líneas): 11 patrones regex
- `TranslationPipeline` (~100 líneas): orquestador de cascada
- `TranslationResult` (~20 líneas): dataclass inmutable

**Total estimado**: ~465 líneas de código de producción + ~300 líneas de tests
