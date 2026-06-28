# 03 — Catálogo de Módulos

> **Fase**: 1.3 | **Generado**: 2026-06-28 | **Proyecto**: WebTranslatorr

## Módulos Identificados (agrupación lógica)

### M1 — API Layer
**Archivos**: `app/api/torznab.py`, `app/api/health.py`, `app/api/domains.py`, `app/api/providers.py`, `app/server.py`, `main.py`
**LOC**: ~898 | **Categoría**: API_LAYER + ENTRY_POINT

| Propiedad | Valor |
|-----------|-------|
| **Propósito** | Exponer endpoints Torznab, health, gestión de dominios y discovery de providers. Gestionar ciclo de vida de la app FastAPI. |
| **APIs públicas** | 11 endpoints HTTP (6 GET con params, 2 POST) |
| **Dependencias entrantes** | Ninguna (es la capa más externa) |
| **Dependencias salientes** | routing, torznab, providers, services, core |
| **Tecnologías internas** | FastAPI, Starlette |
| **Criticidad** | Crítica — es la interfaz de usuario |
| **Frecuencia de cambio** | Alta (nuevos endpoints, ajustes de params) |

### M2 — Core & Config
**Archivos**: `app/core/models.py`, `app/core/categories.py`, `app/core/enums.py`, `app/core/exceptions.py`, `config.py`
**LOC**: 258 | **Categoría**: MODEL + CONFIG

| Propiedad | Valor |
|-----------|-------|
| **Propósito** | Definir los contratos de datos (SearchResult, ProviderCapabilities), categorías Newznab, enumeraciones, jerarquía de excepciones, y configuración de la aplicación. |
| **APIs públicas** | Dataclasses, enums, clase Settings |
| **Dependencias entrantes** | 15 (models) + 10 (config) — usados por casi todos |
| **Dependencias salientes** | 0 — no depende de otros módulos |
| **Tecnologías internas** | Pydantic Settings, dataclasses |
| **Criticidad** | Crítica — models.py es el contrato universal |
| **Frecuencia de cambio** | Baja (modelos estables, config crece con features) |

### M3 — Provider Infrastructure
**Archivos**: `app/providers/base.py`, `app/providers/registry.py`
**LOC**: 185 | **Categoría**: CONTRACT + SERVICE_LOCATOR

| Propiedad | Valor |
|-----------|-------|
| **Propósito** | Definir el contrato BaseProvider (ABC) y el registro central de providers (singleton). |
| **APIs públicas** | BaseProvider (ABC), ProviderRegistry (singleton) |
| **Dependencias entrantes** | 14 (base) + 5 (registry) |
| **Dependencias salientes** | models, http_client |
| **Tecnologías internas** | ABC, patrón singleton |
| **Criticidad** | Crítica — sin esto no hay providers |
| **Frecuencia de cambio** | Muy baja (el contrato es estable) |

### M4 — Books Providers
**Archivos**: `app/providers/books/*.py` (12 archivos)
**LOC**: ~1,967 | **Categoría**: PROVIDERS

| Propiedad | Valor |
|-----------|-------|
| **Propósito** | Implementar scraping de 12 sitios de descarga directa de libros (DDL). Cada provider es independiente. |
| **APIs públicas** | Métodos search(), get_download_url(), get_capabilities() de BaseProvider |
| **Dependencias entrantes** | Registry (registro), Torznab API (invocación) |
| **Dependencias salientes** | base.py, http_client, domain_resolver, models |
| **Tecnologías internas** | BeautifulSoup, cloudscraper, httpx |
| **Criticidad** | Alta — es la funcionalidad core del producto |
| **Frecuencia de cambio** | Alta (cambios en sitios web requieren ajustes) |
| **Notas** | 6 providers sin tests: epubflix1, libgen, booobook, lectuepublibre5, mundoepublibre1, zlibrary |

### M5 — Video Providers
**Archivos**: `app/providers/video/mejortorrent.py`, `app/providers/video/dontorrent.py`
**LOC**: 487 | **Categoría**: PROVIDERS

| Propiedad | Valor |
|-----------|-------|
| **Propósito** | Implementar scraping de 2 sitios de torrents (video): MejorTorrent y DonTorrent. |
| **APIs públicas** | Métodos search(), get_download_url(), get_capabilities() de BaseProvider |
| **Dependencias entrantes** | Registry (registro), Torznab API (invocación) |
| **Dependencias salientes** | base.py, http_client, domain_resolver, models |
| **Tecnologías internas** | BeautifulSoup, httpx (no usa cloudscraper) |
| **Criticidad** | Media — funcionalidad secundaria |
| **Frecuencia de cambio** | Media |

### M6 — Scraping Layer
**Archivos**: `app/scraping/http_client.py`, `app/scraping/wp_api_client.py`, `app/scraping/parser.py`
**LOC**: 544 | **Categoría**: SERVICE + UTIL

| Propiedad | Valor |
|-----------|-------|
| **Propósito** | Capa de infraestructura HTTP: rate-limiting, User-Agent rotation, cloudscraper wrapper, retries. WP API client para providers WordPress. |
| **APIs públicas** | HttpClient, WpApiClient |
| **Dependencias entrantes** | 16 (http_client) + 6 (wp_api_client) |
| **Dependencias salientes** | config.py, exceptions |
| **Tecnologías internas** | httpx, cloudscraper, tenacity (retry) |
| **Criticidad** | Crítica — todos los providers dependen de HttpClient |
| **Frecuencia de cambio** | Baja (infraestructura estable) |
| **Notas** | `parser.py` está huérfano (no importado por nadie) |

### M7 — Services
**Archivos**: `app/services/domain_resolver.py`, `app/services/domain_strategies.py`, `app/services/cache.py`, `app/utils/zip_extractor.py`
**LOC**: 616 | **Categoría**: SERVICE + UTIL

| Propiedad | Valor |
|-----------|-------|
| **Propósito** | Servicios de infraestructura: resolución dinámica de dominios (privtree → Telegram → healthcheck), caché de resultados de búsqueda (TTL), extracción on-the-fly de ZIPs. |
| **APIs públicas** | DomainResolver, SearchCache, ZipExtractor |
| **Dependencias entrantes** | domain_resolver (3), cache (2), domain_strategies (2), zip_extractor (1) |
| **Dependencias salientes** | config.py, http_client |
| **Tecnologías internas** | cachetools.TTLCache, httpx, zipfile |
| **Criticidad** | Alta (domain resolver es crítico para providers con dominios rotativos) |
| **Frecuencia de cambio** | Media (nuevas estrategias de dominio, ajustes de caché) |

### M8 — Routing
**Archivos**: `app/routing/smart_router.py`
**LOC**: 153 | **Categoría**: ROUTER

| Propiedad | Valor |
|-----------|-------|
| **Propósito** | Inferir el tipo de contenido de una búsqueda (libro/película/TV) basándose en el parámetro `t`, categorías, parámetros especiales, y keywords en el query. |
| **APIs públicas** | SmartRouter.route() |
| **Dependencias entrantes** | 3 |
| **Dependencias salientes** | categories.py, enums.py, registry.py |
| **Tecnologías internas** | Algoritmo de scoring por keywords |
| **Criticidad** | Crítica — una mala inferencia envía la búsqueda al provider equivocado |
| **Frecuencia de cambio** | Baja |
| **Notas** | Keywords hardcodeados (18 book, 15 movie, 11 TV); sin NLP |

### M9 — Torznab Protocol
**Archivos**: `app/torznab/mapper.py`, `app/torznab/caps.py`, `app/torznab/errors.py`
**LOC**: 286 | **Categoría**: SERVICE

| Propiedad | Valor |
|-----------|-------|
| **Propósito** | Serializar SearchResult → XML Torznab/Newznab (RSS 2.0 + namespaces), generar capabilities XML, definir códigos de error Torznab. |
| **APIs públicas** | TorznabMapper, generate_caps_xml(), TorznabErrorCodes |
| **Dependencias entrantes** | mapper (3), caps (2), errors (2) |
| **Dependencias salientes** | models.py, categories.py |
| **Tecnologías internas** | xml.etree.ElementTree |
| **Criticidad** | Alta — si el XML está mal formado, las *Arr apps no entienden la respuesta |
| **Frecuencia de cambio** | Baja (el protocolo Torznab es estable) |

## Patrones Arquitectónicos

| Patrón | Módulos involucrados | Descripción |
|--------|---------------------|-------------|
| **Hexagonal (Ports & Adapters)** | M1→M8→M3→M6 | La API (M1) es el puerto de entrada. El Router (M8) dirige al sistema de providers (M3). Los providers son adaptadores que traducen sitios web heterogéneos al contrato SearchResult. |
| **Plugin System** | M3, M4, M5 | ProviderRegistry + BaseProvider forman un sistema de plugins: añadir un provider es crear una clase + registrarla. |
| **Service Locator** | M3 | Registry como singleton global accesible desde cualquier punto. |
| **Strategy** | M4, M5, M7 | Cada provider implementa una estrategia de scraping distinta. DomainResolver aplica cadena de estrategias de resolución. |

## Puntos de Extensión

1. **Nuevo provider**: Crear clase en `app/providers/{books|video}/`, heredar de BaseProvider, registrar en `_init_providers()`.
2. **Nueva estrategia de dominio**: Añadir método en `domain_strategies.py`.
3. **Nuevo endpoint**: Añadir ruta en `app/api/`, cablear en `app/server.py`.
4. **Nuevo tipo de contenido**: Extender `ContentType`, `SearchType`, añadir keywords en SmartRouter.

## Puntos de Fricción

| Problema | Módulo | Severidad |
|----------|--------|-----------|
| Keywords hardcodeados en SmartRouter | M8 | Media — requiere recompilación para añadir keywords |
| parser.py huérfano | M6 | Baja — código muerto |
| ProviderRegistry como singleton global | M3 | Media — difícil de testear en aislamiento |
| _last_request dict crece sin límite en HttpClient | M6 | Media — memory leak potencial |
| 6 providers sin tests | M4 | Alta — riesgo de regresión |
| URLs de providers como defaults hardcodeados | M2 (config.py) | Alta — pueden quedar obsoletos |
