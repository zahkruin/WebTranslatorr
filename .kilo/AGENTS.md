# WebTranslatorr — Guía para Agentes

> **Documento autogenerado.** Derivado del commit: consultar `git log -1 --format=%H -- .kilo/`
>
> ⚠️ **REGLA OBLIGATORIA:** Todo cambio en archivos fuente DEBE ir acompañado de la actualización de los documentos agénticos correspondientes en `.kilo/`. Usa `doc-mapping.json` para identificar qué documentos actualizar según los archivos modificados. Ejecuta `python scripts/validate_docs.py --strict` antes de hacer commit.

<!-- AGENT-MANAGED:START -->
<!-- AGENT-MANAGED:END -->

<!-- AGENT-PROTECTED:START -->
## Visión General

WebTranslatorr es un proxy Torznab universal que actúa como capa de traducción entre aplicaciones *Arr (Readarr, Sonarr, Radarr) y fuentes de contenido heterogéneas. Traduce fuentes de descarga directa (DDL) al formato Torznab.

**Providers implementados:** 16 de libros + 4 de video = 20 providers activos.

## Stack Tecnológico

- **Framework**: FastAPI (Python 3.11+)
- **HTTP Client**: httpx con rate-limiting y retry + cloudscraper para bypass Cloudflare
- **Parsing HTML**: BeautifulSoup4 + lxml
- **Configuración**: Pydantic Settings (.env, prefijo `WTR_`)
- **Testing**: pytest + pytest-asyncio
- **Cache**: cachetools (TTLCache)

## Cómo Arrancar

```bash
# Desarrollo local
pip install -r requirements.txt
python main.py

# Con Docker
docker-compose up -d
```

El servidor escucha en `http://localhost:9811` (puerto estándar Jackett).

## Estructura de Módulos

```
app/
├── api/           # Endpoints FastAPI (torznab.py, health.py, domains.py)
├── core/          # Modelos (SearchResult), categorías, enums, excepciones
├── providers/     # 20 implementaciones de providers
│   ├── books/     # 16 providers de libros
│   └── video/     # 4 providers de video
├── routing/       # SmartRouter - enrutamiento por tipo de contenido
├── scraping/      # HttpClient, parser helpers
├── services/      # DomainResolver, SearchCache
├── torznab/       # Mapeo a XML (mapper, caps, errors)
└── utils/         # ZipExtractor
```

## Documentación Agéntica Disponible

> **Usa `INDEX.md` como punto de entrada.** Contiene un mapa de casos de uso → documentación específica.

### Documentos Core (numerados)
| # | Documento | Tema |
|---|-----------|------|
| 01 | `context/01-architecture.md` | Arquitectura global y flujo de datos |
| 02 | `context/02-configuration.md` | Variables de configuración (.env) |
| 03 | `context/03-data-models.md` | SearchResult, ProviderCapabilities, enums |
| 04 | `context/04-http-client.md` | HttpClient: rate limiting, cloudscraper |
| 05 | `context/05-providers-base.md` | Sistema de providers, BaseProvider, ProviderRegistry |
| 07 | `context/07-smart-router.md` | SmartRouter: inferencia de contenido |
| 08 | `context/08-torznab-protocol.md` | Protocolo Torznab, XML mapper, errores |
| 09 | `context/09-categories.md` | Mapeo de categorías Newznab |
| 10 | `context/10-domain-resolver.md` | Resolución dinámica de dominios |
| 11 | `context/11-cache.md` | SearchCache (TTL) |
| 12 | `context/12-zip-extractor.md` | Extracción on-the-fly de ZIPs |
| 13 | `context/13-api-endpoints.md` | Endpoints FastAPI |
| 14 | `context/14-deployment.md` | Despliegue (Docker, bare-metal) |
| 15 | `context/15-testing.md` | Guía de testing (pytest) |
| 16 | `context/16-known-issues.md` | Bugs y problemas conocidos |
| 17 | `context/17-adding-providers.md` | Guía para añadir providers |

### Estrategias de Provider
| Provider | Documento |
|----------|-----------|
| Ebookelo | `context/06-provider-strategies/ebookelo.md` |
| EpubLibre | `context/06-provider-strategies/epublibre.md` |
| Lectulandia | `context/06-provider-strategies/lectulandia.md` |
| Espaebook | `context/06-provider-strategies/espaebook.md` |
| HolaEbook | `context/06-provider-strategies/holaebook.md` |
| Anna's Archive | `context/06-provider-strategies/annas-archive.md` |
| Epubflix1 | `context/06-provider-strategies/epubflix1.md` |
| Library Genesis | `context/06-provider-strategies/libgen.md` |
| B00k.Bond | `context/06-provider-strategies/booobook.md` |
| LectuEpubLibre5 | `context/06-provider-strategies/lectuepublibre5.md` |
| MundoEpubLibre1 | `context/06-provider-strategies/mundoepublibre1.md` |
| Z-Library | `context/06-provider-strategies/zlibrary.md` |
| MejorTorrent | `context/06-provider-strategies/mejortorrent.md` |
| DonTorrent | `context/06-provider-strategies/dontorrent.md` |
| Epubgratis | `context/06-provider-strategies/epubgratis.md` |
| Ebiblioteca | `context/06-provider-strategies/ebiblioteca.md` |
| Bajaebooks | `context/06-provider-strategies/bajaebooks.md` |
| LeLibros | `context/06-provider-strategies/lelibros.md` |
| DivxTotal | `context/06-provider-strategies/divxtotal.md` |
| EliteTorrent | `context/06-provider-strategies/elitetorrent.md` |

## Convenciones Importantes

### Providers
- Heredar de `BaseProvider` (ABC)
- Implementar: `search()`, `get_download_url()`, `get_capabilities()`
- No interactuar directamente con formato Torznab — solo devolver `SearchResult`
- Usar `self.http_client` para requests (rate-limiting integrado)
- NUNCA propagar excepciones — devolver `[]` o `None`

### Categorías Newznab
- Libros: 7000, 7020, 8000, 8010 (Readarr busca en ambos rangos)
- Películas: 2000, 2030, 2040, 2045
- TV: 5000, 5030, 5040, 5045

### Código
- Async/await para todo I/O
- Type hints en todos los métodos públicos
- snake_case para variables, PascalCase para clases
- Google-style docstrings
- Logging con `self.logger` (no print)

## Qué NO Hacer

- **NUNCA seguir enlaces de profitablecpmgate.com** (trampa publicitaria de Ebookelo)
- No hardcodear URLs de providers — usar configuración o DomainResolver
- No hacer requests síncronos — todo es async/await
- No parsear XML manualmente — usar ElementTree
- No devolver diccionarios desde search() — usar SearchResult dataclass
- No propagar excepciones desde providers

## Endpoints Principales

| Endpoint | Descripción |
|----------|-------------|
| `GET /api?t=caps` | Capabilities del proxy |
| `GET /api?t=search&q=...` | Búsqueda genérica (todos los providers) |
| `GET /api?t=book&q=...` | Búsqueda de libros |
| `GET /api?t=movie&imdbid=...` | Búsqueda de películas |
| `GET /api?t=tvsearch&q=...` | Búsqueda de series |
| `GET /api/{provider_id}?t=search&q=...` | Búsqueda en un provider específico (multi-indexer) |
| `GET /api/download?provider=...&id=...` | Proxy de descarga |
| `GET /health` | Health check |
| `GET /api/domains` | Estado de dominios |
| `POST /api/domains/refresh` | Forzar resolución de dominios |

## Para Dónde Ir Según la Tarea

| Tarea | Documento principal |
|-------|-------------------|
| Crear un provider nuevo | `17-adding-providers.md` → `05-providers-base.md` → `03-data-models.md` |
| Depurar un provider roto | `06-provider-strategies/{provider}.md` → `16-known-issues.md` |
| Cambió un dominio | `10-domain-resolver.md` → `POST /api/domains/refresh` |
| Error en el XML Torznab | `08-torznab-protocol.md` → `09-categories.md` |
| Problema de rendimiento | `11-cache.md` → `04-http-client.md` → `07-smart-router.md` |
| Escribir tests | `15-testing.md` → `03-data-models.md` |
| Desplegar | `14-deployment.md` → `02-configuration.md` |
| Entender la arquitectura | `01-architecture.md` → `AGENTS.md` |
