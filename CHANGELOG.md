# Changelog

Todos los cambios notables de este proyecto se documentarán en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]



### Added



### Fixed



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

> **Última actualización**: 2026-06-29 — v0.1.7 con docs de URLs por provider.
