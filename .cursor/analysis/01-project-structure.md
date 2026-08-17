# 01 — Estructura del Proyecto

> **Fase**: 1.1 | **Generado**: 2026-06-28 | **Proyecto**: WebTranslatorr

## Stack Tecnológico

| Componente | Tecnología | Versión |
|-----------|-----------|---------|
| Lenguaje | Python | 3.11+ |
| Framework web | FastAPI | ≥0.115.0 |
| Servidor ASGI | uvicorn | ≥0.30.0 |
| HTTP Client | httpx + cloudscraper | ≥0.27.0 |
| Parsing HTML | BeautifulSoup4 + lxml | ≥4.12.0 / ≥5.0.0 |
| Configuración | pydantic-settings | ≥2.0.0 |
| Caché | cachetools (TTLCache) | ≥5.3.0 |
| Testing | pytest + pytest-asyncio | ≥8.0 / ≥0.24 |
| CI/CD | GitHub Actions | — |
| Contenedor | Docker + docker-compose | — |

## Runtime

- **Intérprete**: Python 3.11 (Dockerfile: `python:3.11-slim`)
- **CI test**: Python 3.11 + 3.12
- **Puerto**: 9811 (estándar Jackett)

## Árbol de Directorios Clasificado

```
WebTranslatorr/                          (~155 archivos fuente/relevantes)
├── 📄 CÓDIGO FUENTE (app/ + top-level)
│   ├── main.py                          [ENTRY] 17 líneas — punto de entrada uvicorn
│   ├── config.py                        [CONFIG] 77 líneas — Pydantic Settings (prefijo WTR_)
│   ├── app/server.py                    [ENTRY] 208 líneas — FastAPI app, lifespan, middleware
│   ├── app/api/                         [API] 4 archivos, 684 líneas
│   │   ├── torznab.py                   [API] 430 líneas — endpoint Torznab principal + multi-indexer + download proxy
│   │   ├── health.py                    [API] 92 líneas — health check + deep search health
│   │   ├── domains.py                   [API] 83 líneas — gestión de dominios
│   │   └── providers.py                 [API] 79 líneas — discovery de providers
│   ├── app/core/                        [MODEL] 4 archivos, 181 líneas
│   │   ├── models.py                    [MODEL] 48 líneas — SearchResult, ProviderCapabilities
│   │   ├── categories.py                [MODEL] 82 líneas — CategoryMapper, IDs Newznab
│   │   ├── enums.py                     [MODEL] 18 líneas — ContentType, SearchType
│   │   └── exceptions.py                [MODEL] 33 líneas — jerarquía de excepciones
│   ├── app/providers/                   [PROVIDERS] 16 archivos, 2547 líneas
│   │   ├── base.py                      [CONTRACT] 106 líneas — BaseProvider (ABC)
│   │   ├── registry.py                  [LOCATOR] 79 líneas — ProviderRegistry (singleton)
│   │   ├── books/                       [PROVIDERS] 12 archivos, ~1967 líneas
│   │   │   ├── annas_archive.py         125 líneas
│   │   │   ├── booobook.py             171 líneas
│   │   │   ├── ebookelo.py             279 líneas
│   │   │   ├── epubflix1.py            173 líneas
│   │   │   ├── epublibre.py            116 líneas
│   │   │   ├── espaebook.py            120 líneas
│   │   │   ├── holaebook.py            119 líneas
│   │   │   ├── lectuepublibre5.py      180 líneas
│   │   │   ├── lectulandia.py          179 líneas
│   │   │   ├── libgen.py               203 líneas
│   │   │   ├── mundoepublibre1.py      142 líneas
│   │   │   └── zlibrary.py             248 líneas
│   │   └── video/                       [PROVIDERS] 2 archivos, 487 líneas
│   │       ├── dontorrent.py           156 líneas
│   │       └── mejortorrent.py         331 líneas
│   ├── app/routing/                     [ROUTER] 1 archivo, 153 líneas
│   │   └── smart_router.py             [ROUTER] SmartRouter — inferencia de contenido
│   ├── app/scraping/                    [SCRAPING] 3 archivos, 544 líneas
│   │   ├── http_client.py              [SERVICE] 206 líneas — HttpClient con rate-limiting
│   │   ├── wp_api_client.py            [SERVICE] 305 líneas — WordPress API client
│   │   └── parser.py                   [UTIL] 33 líneas — helpers de parsing (huérfano)
│   ├── app/services/                    [SERVICES] 3 archivos, 589 líneas
│   │   ├── domain_resolver.py          [SERVICE] 307 líneas — resolución dinámica de dominios
│   │   ├── domain_strategies.py        [SERVICE] 228 líneas — estrategias de resolución
│   │   └── cache.py                    [SERVICE] 54 líneas — SearchCache (TTL)
│   ├── app/torznab/                     [TORZNAB] 3 archivos, 286 líneas
│   │   ├── mapper.py                   [SERVICE] 129 líneas — SearchResult → XML
│   │   ├── caps.py                     [SERVICE] 104 líneas — generación de capabilities XML
│   │   └── errors.py                   [SERVICE] 53 líneas — códigos de error Torznab
│   └── app/utils/                       [UTIL] 1 archivo, 27 líneas
│       └── zip_extractor.py            [UTIL] 27 líneas — extracción on-the-fly de ZIPs
│
├── 🧪 TESTS (tests/)
│   └── 32 archivos de test (~18 providers + API + core + servicios + integración)
│
├── 🐳 DOCKER
│   ├── Dockerfile                       python:3.11-slim, EXPOSE 9811
│   └── docker-compose.yml              puerto 9811:9811, volume ./data:/app/data
│
├── ⚙️ CONFIGURACIÓN
│   ├── .env.example                     69 líneas — todas las variables documentadas
│   ├── .env                             (no versionado)
│   ├── pyproject.toml                   configuración de pytest y pre-commit
│   ├── .pre-commit-config.yaml          pytest + validate_docs.py
│   ├── requirements.txt                 9 dependencias directas
│   └── requirements-dev.txt             + testing/linting
│
├── 🔧 SCRIPTS
│   ├── scripts/validate_docs.py         validador de documentación agéntica
│   ├── scripts/classify_changes.py      clasificador de cambios
│   ├── scripts/update-agentic-docs.sh   actualizador de docs agénticos
│   ├── scripts/check_coverage.sh        verificador de cobertura
│   └── deploy.sh                        script de despliegue bare-metal
│
├── 📊 CI/CD (.github/workflows/)
│   ├── test.yml                         pytest Python 3.11/3.12 → ≥90% coverage
│   ├── docker.yml                       build + push a ghcr.io
│   └── agentic-docs.yml                 validación de docs agénticos en PRs
│
├── 📚 DOCUMENTACIÓN AGÉNTICA (.cursor/)
│   ├── AGENTS.md                        guía general para agentes
│   ├── INDEX.md                         mapa casos de uso → docs
│   ├── styleguide.md                    convenciones de código
│   ├── doc-mapping.json                 mapeo archivos fuente → docs
│   ├── phase0-ficha-tecnica.yaml         ficha técnica del proyecto
│   ├── phase1-modules.json              análisis estático de módulos
│   ├── phase2-dynamic.json              análisis dinámico (endpoints, errores, issues)
│   └── context/                         17 documentos de contexto + 14 estrategias de provider
│
├── 📦 DATOS
│   └── data/domains.json                estado persistido de dominios resueltos
│
└── 📄 DOCUMENTACIÓN GENERAL
    ├── README.md                        106 líneas
    └── docs/
        ├── architecture.md              66 líneas
        └── adding_providers.md          86 líneas
```

## Clasificación por Categoría

| Categoría | Archivos | LOC total | % del código |
|-----------|---------|-----------|-------------|
| Providers (libros) | 12 | 1,967 | 38.4% |
| Providers (video) | 2 | 487 | 9.5% |
| API Layer | 4 | 684 | 13.4% |
| Services | 3 | 589 | 11.5% |
| Scraping | 3 | 544 | 10.6% |
| Provider Infra | 2 | 185 | 3.6% |
| Torznab | 3 | 286 | 5.6% |
| Core/Models | 4 | 181 | 3.5% |
| Routing | 1 | 153 | 3.0% |
| Entry Points | 2 | 225 | 4.4% |
| Utils | 1 | 27 | 0.5% |
| **TOTAL** | **47** | **5,118** | **100%** |

## Patrones Arquitectónicos Detectados

| Patrón | Evidencia |
|--------|----------|
| **Hexagonal (Ports & Adapters)** | API → Router → Providers (contrato BaseProvider) → Scraping (adapters HTTP) |
| **Plugin System** | ProviderRegistry + BaseProvider: providers registrables como plugins |
| **Service Locator** | ProviderRegistry como singleton global para localizar providers |
| **Strategy** | Múltiples estrategias de scraping por provider, domain_strategies para resolución |
| **Adapter** | Cada provider adapta un sitio web distinto al contrato SearchResult |
| **Factory** | _init_providers() construye e instancia providers según flags de configuración |
| **Singleton** | ProviderRegistry, HttpClient (instancia única compartida) |

## Archivos Huérfanos

- `app/scraping/parser.py` (33 líneas): in-degree 0, out-degree 0. No es importado por ningún módulo.

## Dependencias Circulares

No se detectaron dependencias circulares entre módulos.
