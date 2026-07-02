# Changelog

Todos los cambios notables de este proyecto se documentarán en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **BookSee provider**: scraping de en.booksee.org (2.4M libros, PDF, sin protecciones)
- **OceanOfPDF provider**: scraping de oceanofpdf.com (WordPress, PDF/EPUB/MOBI, sin protecciones)

## [0.3.0] — 2026-07-01

### Added
- **Panel de administración web**: frontend HTML/JS/CSS autocontenido accesible en `/` para gestionar providers, API keys y configuración sin editar `.env` ni reiniciar la aplicación. Incluye 3 pestañas: Providers (tabla con toggles enable/disable, edición de dominio, filtro por tipo, reload registry), Settings (API keys con toggle visibilidad, URLs externas, proxy), y Readarr (gestión de instancias, test de conexión, sincronización one-click).
- **Persistencia de configuración en SQLite**: nueva capa `app/persistence/` con esquema de 3 tablas (`provider_config`, `settings`, `readarr_instances`). La configuración de providers (habilitado/deshabilitado, dominio) y las settings globales (API key, URLs, API keys externas) se almacenan en `data/webtranslatorr.db` y se gestionan en runtime.
- **Migración automática env vars → SQLite**: en el primer arranque, todas las variables de entorno existentes se migran automáticamente a SQLite. Arranques posteriores usan la DB como fuente de verdad, con fallback a env vars para claves no presentes en DB.
- **Sincronización con Readarr**: nuevo servicio `ReadarrSyncer` (`app/services/readarr_syncer.py`) y endpoints `/api/admin/readarr/*` que permiten configurar instancias Readarr y sincronizar automáticamente los providers de libros activos como indexers Torznab individuales (estilo Prowlarr). Incluye test de conectividad y opción de eliminar indexers huérfanos.
- **Endpoints de administración**: `GET/PUT /api/admin/providers`, `POST /api/admin/providers/reload`, `GET/PUT /api/admin/settings`, CRUD `/api/admin/readarr`, `POST /api/admin/readarr/{id}/sync`, `POST /api/admin/readarr/{id}/test`.
- **Hot-reload de providers**: cambios en la configuración (habilitar/deshabilitar provider) se aplican en runtime sin reinicio mediante `POST /api/admin/providers/reload`, que re-registra providers desde la DB.

### Changed
- `_init_providers()` ahora consulta la base de datos vía `ConfigManager` en lugar de leer directamente de `config.settings`. Mantiene fallback a env vars para compatibilidad con tests.
- `_validate_apikey()` ahora es asíncrona y valida contra la DB (con fallback a env vars).
- `app/server.py` inicializa la base de datos SQLite y el `ConfigManager` en `lifespan()`, sirve archivos estáticos desde `static/`, y registra los DomainConfigs dinámicamente desde la DB.
- La configuración vía variables de entorno (`WTR_*_ENABLED`, `WTR_*_DOMAIN`, etc.) sigue siendo soportada como fuente inicial en el primer arranque, pero la DB prevalece en arranques posteriores.
- Ruta raíz `/` movida de `health.py` (`/api/root`) para servir el panel de administración.

## [0.2.1] — 2026-06-29

### Fixed
- **Translation Pipeline no documentado**: añadidas 5 variables de entorno (`WTR_TRANSLATION_PIPELINE_SEARCH_ENABLED`, `WTR_TRANSLATION_PIPELINE_WIKIDATA_ENABLED`, `WTR_TRANSLATION_PIPELINE_GOOGLE_BOOKS_ENABLED`, `WTR_GOOGLE_BOOKS_API_KEY`, `WTR_TRANSLATION_PIPELINE_TIMEOUT`) a `.env.example` con comentarios explicativos. La variable maestra `WTR_TRANSLATION_PIPELINE_SEARCH_ENABLED` tiene default `false` en `config.py:96`, por lo que sin esta documentación los usuarios no sabían que el pipeline existía ni cómo activarlo.

## [0.2.0] — 2026-06-29

### Added
- **Translation Pipeline**: sistema de cascada de 4 fases para traducción de títulos de libros (inglés → español) con fallback silencioso. Fases: (1) Caché local SQLite con hashing SHA-256, (2) Wikidata SPARQL lookup gratuito, (3) Google Books API, (4) TitleCleaner post-procesamiento. Nuevo módulo `app/services/translation_pipeline.py` (737 LOC, 6 clases, 45 tests unitarios).
- **Nueva dependencia**: `aiosqlite>=0.20.0` para caché persistente de traducciones.
- **Nuevas variables de configuración**: `TRANSLATION_CACHE_PATH`, `TRANSLATION_PIPELINE_TIMEOUT`, `GOOGLE_BOOKS_API_KEY`, `TRANSLATION_PIPELINE_WIKIDATA_ENABLED`, `TRANSLATION_PIPELINE_GOOGLE_BOOKS_ENABLED` (todas con defaults seguros, prefijo `WTR_`).
- **Integración en búsqueda**: el TranslationPipeline se integra en el endpoint de búsqueda Torznab (`/api`). Cuando `TRANSLATION_PIPELINE_SEARCH_ENABLED=true`, las queries de libros (categorías 7000-8999) se traducen automáticamente de inglés a español antes de enviarse a los providers. El pipeline se inicializa como singleton en el lifespan de FastAPI. Nueva variable `TRANSLATION_PIPELINE_SEARCH_ENABLED` (default `false`).

## [0.1.3] — 2026-06-29

### Fixed
- **WP API Client categories**: los resultados de providers WordPress (Epubgratis, Epubflix1, LectuEpubLibre5) ahora incluyen todas las categorías `[7000, 7020, 8000, 8010]` en vez de solo `[7020]`. Corrige el error de Readarr "no results in configured categories" cuando solo se solicita `cat=8010`.
- **Diagnóstico de browse()**: añadido logging individual de providers que devuelven 0 resultados durante RSS sync/browse, facilitando identificar qué provider específico está fallando.

### Changed
- **CAPS XML**: `supportedParams` para `book-search` ahora se deriva de las capabilities reales de los providers en vez de hardcodear `"q,author,title"`. Si ningún provider declara `author`/`title`, el CAPS refleja solo `"q"`.

## [0.1.2] — 2026-06-29

### Added
- **Multi-indexer personalizado**: cada provider muestra su `display_name` real en Readarr (ej: "WebTranslatorr - EpubLibre") cuando se usa el endpoint single-provider `/api/{provider_id}`.

### Fixed
- CAPS endpoint single-provider devuelve `server_url` correcto apuntando a `/api/{provider_id}`.
- CAPS endpoint single-provider devuelve `server_title` con el nombre del provider.

## [0.1.1] — 2026-06-28

### Fixed
- **Torznab CAPS endpoint** ahora permite `t=caps` sin API key (comportamiento compatible con Jackett/Prowlarr), permitiendo a Readarr/Radarr/Sonarr detectar el indexer antes de configurar autenticación
- **Routers** de FastAPI registrados en orden correcto: `/api/domains` y `/api/providers` ahora tienen prioridad sobre la ruta dinámica `/api/{provider_id}`, evitando que las peticiones de dominios sean interceptadas incorrectamente
- **URLs en respuestas XML** (CAPS y RSS) ahora usan `settings.EXTERNAL_URL` en lugar de `http://localhost:9811` hardcodeado, permitiendo que las *Arr apps en contenedores o hosts remotos sigan los enlaces correctamente
- **Ruta raíz `/`** añadida para que las *Arr apps puedan verificar conectividad básica antes de probar los endpoints Torznab
- **Headers de error Torznab** (`X-Torznab-Error-Code`, `X-Torznab-Error-Description`) añadidos en respuestas de error para mejorar la compatibilidad con Readarr

### Changed
- `TorznabErrors` ahora expone `error_headers()` para generar headers HTTP de error estándar
- `caps.py` y `mapper.py` importan `settings` para usar `EXTERNAL_URL` configurable

## [0.1.2] — 2026-06-28

### Changed
- **Multi-indexer CAPS personalizado**: cada provider individual (`/api/{provider_id}`) ahora devuelve `<server title="WebTranslatorr - {display_name}">` y `<server url="{EXTERNAL_URL}/api/{provider_id}">`, permitiendo a Readarr mostrar cada indexer con su nombre real (ej: "WebTranslatorr - EpubLibre", "WebTranslatorr - Library Genesis") en lugar de todos con el mismo nombre genérico "WebTranslatorr"
- `CapsGenerator.generate()` ahora acepta parámetros opcionales `server_title` y `server_url` para personalizar el XML de capabilities

### Added
- Tests para el endpoint multi-indexer `/api/{provider_id}`: CAPS con/sin API key, CAPS con nombre personalizado, búsqueda con API key inválida, provider desconocido, y verificación de que el endpoint agregado no incluye nombres de provider

## [0.1.3] — 2026-06-28

### Fixed
- **Categorías de libros unificadas**: los 15 providers de libros que taggeaban resultados con `categories=[7020]` ahora usan `[7000, 7020, 8000, 8010]` para cubrir ambos rangos Newznab (Books y Books alt), eliminando el error "Query successful, but no results in the configured categories" que Readarr mostraba cuando filtraba por el rango 8000/8010
- **Default category en SearchResult**: cambiado de `[8010]` a `[7000, 7020, 8000, 8010]` para consistencia con los providers y máxima compatibilidad con Readarr

### Added
- **Filtrado server-side por categorías**: `_handle_torznab_request()` ahora filtra resultados que no coinciden con las categorías solicitadas (`cat=`), evitando que resultados de video contaminen respuestas de búsqueda de libros y viceversa

## [0.1.4] — 2026-06-28

### Added
- **Modo RSS/browse**: 11 providers de libros ahora soportan devolver listados recientes cuando Readarr envía peticiones de sincronización sin query (`t=book` sin `q=`), eliminando el error "Query successful, but no results in the configured categories" en syncs periódicos
- **Método `browse()` en BaseProvider**: nuevo método opcional que los providers pueden sobrescribir para devolver resultados recientes sin búsqueda explícita
- **`list_recent()` en WordPressApiClient**: consulta `/wp-json/wp/v2/posts` sin `search=` para devolver posts recientes vía API (usado por Epubflix1, LectuEpubLibre5, Epubgratis)
- **Scrapeo de homepage**: EpubLibre, Espaebook, HolaEbook, B00k.Bond, MundoEpubLibre1, LeLibros, Bajaebooks y Ebookelo ahora scrapean su página principal cuando no hay query

### Changed
- **`_handle_torznab_request()`**: detecta peticiones RSS sin query y usa `browse()` en lugar de `search()`, evitando que los 16 providers retornen vacío en syncs de Readarr

## [0.1.5] — 2026-06-28

### Added
- **Modo browse en 5 providers restantes**: Lectulandia (homepage /book/), Ebiblioteca (catálogo homepage), Library Genesis (/last.php), Anna's Archive (homepage /md5/), Z-Library (homepage cards + fallback /book/) — completando los 16 providers de libros con soporte RSS/browse

## [0.1.7] — 2026-06-29

### Changed
- **README**: sección "Uso en *Arr Apps" reescrita con tabla de URLs específicas por provider (8 providers), categorías exactas y separación Readarr / Radarr+Sonarr

## [0.1.6] — 2026-06-28

### Added
- Generación de archivos .torrent para descargas de libros (compatibilidad Readarr)

---

> **Última actualización**: 2026-06-29 — v0.2.0 con Translation Pipeline.
