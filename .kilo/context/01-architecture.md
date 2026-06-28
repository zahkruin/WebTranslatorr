# 01 — Arquitectura Global

## Propósito

Este documento describe la arquitectura completa de WebTranslatorr: el flujo de datos desde las aplicaciones *Arr hasta los sitios web fuente y viceversa, las dependencias entre módulos, y el ciclo de vida de la aplicación.

Cuándo consultar: para entender cómo encajan los componentes, depurar flujos end-to-end, o planificar cambios arquitectónicos.

---

## Diagrama de Flujo End-to-End

```
┌──────────────┐   Torznab HTTP API    ┌───────────────────────────────────────┐
│  Sonarr      │ ────────────────────► │  FastAPI Application (app/server.py) │
│  Radarr      │                       │                                       │
│  Readarr     │ ◄──────────────────── │  ┌─────────┐  ┌───────────────────┐   │
└──────────────┘   XML RSS 2.0         │  │CORS     │  │ Lifespan Manager  │   │
                                       │  │Middleware│  │ (startup/shutdown)│   │
                                       │  └─────────┘  └─────────┬─────────┘   │
                                       │                          │             │
                                       │  ┌───────────────────────┼───────┐    │
                                       │  │ API Routers           │       │    │
                                       │  │                       ▼       │    │
                                       │  │  /api (torznab.py) ◄──┤       │    │
                                       │  │  /api/{provider_id}   │       │    │
                                       │  │  /api/download        │       │    │
                                       │  │  /health              │       │    │
                                       │  │  /api/domains/*       │       │    │
                                       │  └───────────┬───────────┘       │    │
                                       │              │                   │    │
                                       │  ┌───────────▼───────────┐       │    │
                                       │  │   SmartRouter          │       │    │
                                       │  │   (smart_router.py)    │       │    │
                                       │  └───────────┬───────────┘       │    │
                                       │              │                   │    │
                                       │  ┌───────────▼───────────┐       │    │
                                       │  │   ProviderRegistry     │       │    │
                                       │  │   (registry.py)        │       │    │
                                       │  └───────────┬───────────┘       │    │
                                       └──────────────┼───────────────────┘
                                                      │
                    ┌─────────────────────────────────┼──────────────────────┐
                    │                                 │                      │
                    ▼                                 ▼                      ▼
          ┌──────────────────┐            ┌──────────────────┐   ┌──────────────────┐
          │ Ebook Providers  │            │ Video Providers  │   │ Services         │
          │ (12 providers)   │            │ (2 providers)    │   │                  │
          │                  │            │                  │   │ SearchCache      │
          │ ebookelo         │            │ mejortorrent     │   │ DomainResolver   │
          │ epublibre        │            │ dontorrent       │   │ ZipExtractor     │
          │ lectulandia      │            │                  │   │                  │
          │ espaebook        │            └────────┬─────────┘   └──────────────────┘
          │ holaebook        │                     │
          │ annasarchive     │                     │
          │ epubflix1        │                     │
          │ libgen           │          ┌──────────▼──────────┐
          │ booobook         │          │ HttpClient          │
          │ lectuepublibre5  │          │ (http_client.py)    │
          │ mundoepublibre1  │          │                     │
          │ zlibrary         │          │ httpx + cloudscraper │
          └────────┬─────────┘          │ Rate limiting       │
                   │                    │ User-Agent rotation │
                   │                    │ Exponential backoff │
                   ▼                    └──────────┬──────────┘
          ┌──────────────────┐                     │
          │ TorznabMapper    │                     │
          │ (mapper.py)      │                     ▼
          │ CapsGenerator    │          ┌──────────────────────┐
          │ (caps.py)        │          │ Internet             │
          └────────┬─────────┘          │                      │
                   │                    │ ebookelo.com         │
                   ▼                    │ epublibre.bid        │
            XML Response                │ lectulandia.co       │
          to *Arr apps                  │ annas-archive.org    │
                                        │ mejortorrent.eu      │
                                        │ libgen.ee            │
                                        │ z-library.sk         │
                                        │ ...                  │
                                        └──────────────────────┘
```

---

## Flujo de una Petición Típica

### 1. Startup (`app/server.py:lifespan()`)

```
1. Crear HttpClient (shared, con rate limiting global)
2. Crear DomainResolver (carga dominios persistidos de data/domains.json)
3. Registrar DomainConfig por cada provider habilitado
4. Llamar a torznab._init_providers(resolver):
   - Limpiar ProviderRegistry
   - Instanciar cada provider con su HttpClient y DomainResolver
   - Registrar en el registry
5. Ejecutar resolución inicial de dominios (resolve_all)
6. Iniciar background task: domain_check_loop (cada DOMAIN_CHECK_INTERVAL segundos)
```

### 2. Petición `GET /api?t=search&q=quijote&apikey=xxx`

```
1. FastAPI → app/api/torznab.py → torznab_api()
2. Validar API key (_validate_apikey)
3. Si t=caps → CapsGenerator.generate() → XML
4. Si no → SmartRouter.route(params):
   a. Detectar search_type (book/movie/tv/generic)
   b. Extraer categorías del parámetro cat=
   c. Si hay tipo explícito → filtrar providers por tipo
   d. Si hay categorías → filtrar por CategoryMapper
   e. Si hay imdbid/author → filtrar por tipo de contenido
   f. Si hay query → inferir tipo por keywords
   g. Sin filtros → devolver todos los providers
5. _handle_torznab_request():
   a. Crear tasks asyncio por provider
   b. Cada task: search_cache.get() → si miss → provider.search() → search_cache.set()
   c. asyncio.gather(tasks) con timeout de 45s por provider
   d. Merge de resultados de todos los providers
   e. Paginar (offset/limit)
   f. TorznabMapper.results_to_xml() → Response XML
```

### 3. Petición `GET /api/download?provider=ebookelo&id=1828&fmt=epub`

```
1. FastAPI → app/api/torznab.py → download_proxy()
2. registry.get(provider) → obtener instancia del provider
3. provider.get_download_url(internal_id, fmt=fmt):
   - Resuelve URL final (puede involucrar HTTP requests adicionales)
4. http_client.download_file(final_url):
   - Usa cloudscraper si el provider requiere bypass de Cloudflare
5. Si provider.is_zipped → ZipExtractor.extract_epub_from_memory()
6. Servir bytes como Response con Content-Type apropiado
```

---

## Dependencias entre Módulos

```
config.py (Settings)
    │
    ├──► app/server.py (FastAPI app factory)
    │       ├──► app/api/torznab.py
    │       │       ├──► app/routing/smart_router.py
    │       │       │       ├──► app/providers/registry.py
    │       │       │       └──► app/core/categories.py
    │       │       ├──► app/providers/base.py (ABC)
    │       │       │       └──► app/core/models.py
    │       │       ├──► app/providers/books/*.py (14 providers)
    │       │       ├──► app/providers/video/*.py (2 providers)
    │       │       ├──► app/scraping/http_client.py
    │       │       ├──► app/torznab/mapper.py
    │       │       ├──► app/torznab/caps.py
    │       │       ├──► app/torznab/errors.py
    │       │       ├──► app/services/cache.py
    │       │       └──► app/utils/zip_extractor.py
    │       ├──► app/api/health.py
    │       ├──► app/api/domains.py
    │       │       └──► app/services/domain_resolver.py
    │       │               └──► app/services/domain_strategies.py
    │       └──► app/services/domain_resolver.py
    │
    └──► app/services/cache.py
```

**Regla de dependencias:** Los providers NO dependen del layer Torznab. Solo conocen `SearchResult`. El layer Torznab consume `SearchResult`.

---

## Jerarquía de Providers

```
BaseProvider (ABC)
├── EbookeloProvider          # Libros - sitio con ad-gate (profitablecpmgate)
├── EpubLibreProvider         # Libros - WordPress, cloudscraper requerido
├── LectulandiaProvider       # Libros - WordPress + download.php + JS linkCode
├── EspaebookProvider         # Libros - WordPress, paths /libro/ y /book/
├── HolaEbookProvider         # Libros - ZIP wrapper (is_zipped=True)
├── AnnasArchiveProvider      # Libros - Anna's Archive, MD5 IDs
├── Epubflix1Provider         # Libros - WordPress estándar (NUEVO)
├── LibgenProvider            # Libros - Library Genesis, tabla HTML, MD5 (NUEVO)
├── BooobookProvider          # Libros - B00k.Bond, multi-selector (NUEVO)
├── LectuEpubLibre5Provider   # Libros - WordPress estándar (NUEVO)
├── MundoEpubLibre1Provider   # Libros - WordPress estándar (NUEVO)
├── ZLibraryProvider          # Libros - Z-Library, card-based layout (NUEVO)
├── MejorTorrentProvider      # Video - .torrent directos, IMDb→TMDB
└── DonTorrentProvider        # Video - listados, sin búsqueda GET (fallback)
```

---

## Flujo de Datos: SearchResult

```
Provider.search()
    │
    ▼
SearchResult (dataclass)
    │  .title, .guid, .link, .download_url
    │  .size_bytes, .pub_date, .categories
    │  .author (libros), .imdb_id/.tvdb_id/.season/.episode (video)
    │  .seeders, .peers (simulados), .info_hash, .magnet_uri
    │  .extra_attrs (metadata flexible)
    │
    ▼
TorznabMapper.results_to_xml()
    │
    ▼
XML RSS 2.0 + namespaces torznab/newznab
    │
    ▼
*Arr application (Readarr/Sonarr/Radarr)
```

---

## Archivos Relevantes

| Archivo | Rol |
|---------|-----|
| `main.py` | Entry point: `uvicorn.run("app.server:app")` |
| `app/server.py` | FastAPI app factory, lifespan, middleware |
| `app/api/torznab.py` | Endpoints Torznab, init providers, download proxy |
| `app/api/health.py` | GET /health |
| `app/api/domains.py` | GET/POST /api/domains/* |
| `app/routing/smart_router.py` | Routing inteligente |
| `app/providers/base.py` | BaseProvider (ABC) |
| `app/providers/registry.py` | ProviderRegistry (Service Locator) |
| `app/torznab/mapper.py` | SearchResult → XML |
| `app/torznab/caps.py` | ProviderCapabilities → XML |
| `app/torznab/errors.py` | XML de error Torznab |
| `app/scraping/http_client.py` | HTTP client con rate limiting |
| `app/services/cache.py` | Cache de resultados |
| `app/services/domain_resolver.py` | Resolución dinámica de dominios |
| `app/services/domain_strategies.py` | Estrategias de resolución |
| `app/utils/zip_extractor.py` | Extracción ZIP en memoria |
| `app/core/models.py` | SearchResult, ProviderCapabilities |
| `app/core/categories.py` | CategoryMapper |
| `app/core/enums.py` | ContentType, SearchType |
| `app/core/exceptions.py` | Jerarquía de excepciones |
| `config.py` | Settings (Pydantic) |
