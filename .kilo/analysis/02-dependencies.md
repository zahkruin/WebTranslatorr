# 02 — Dependencias

> **Fase**: 1.2 | **Generado**: 2026-06-28 | **Proyecto**: WebTranslatorr

## Dependencias Externas (requirements.txt)

| Paquete | Versión | Tipo | Propósito |
|---------|---------|------|-----------|
| fastapi | ≥0.115.0 | Framework | Framework web ASGI, endpoints, middleware |
| uvicorn[standard] | ≥0.30.0 | Runtime | Servidor ASGI |
| httpx | ≥0.27.0 | HTTP Client | Cliente HTTP asíncrono con rate-limiting |
| beautifulsoup4 | ≥4.12.0 | Parsing | Parseo HTML de sitios web |
| lxml | ≥5.0.0 | Parsing | Backend de parsing para BeautifulSoup |
| pydantic-settings | ≥2.0.0 | Config | Settings desde .env con validación |
| python-dotenv | ≥1.0.0 | Config | Carga de archivos .env |
| cachetools | ≥5.3.0 | Caching | TTLCache para resultados de búsqueda |
| cloudscraper | (latest) | Anti-bot | Bypass de Cloudflare para sitios protegidos |

### Dependencias de Desarrollo (requirements-dev.txt)

| Paquete | Versión | Propósito |
|---------|---------|-----------|
| pytest | ≥8.0 | Framework de testing |
| pytest-asyncio | ≥0.24 | Soporte async para pytest |
| pytest-cov | ≥5.0 | Reportes de cobertura |
| pytest-mock | ≥3.14 | Fixtures de mock |
| pytest-xdist | ≥3.6 | Ejecución paralela de tests |
| pytest-timeout | ≥2.3 | Timeout por test |
| pytest-randomly | ≥3.15 | Orden aleatorio de tests |
| coverage | ≥7.6 | Medición de cobertura |

## Dependencias del Sistema (Dockerfile)

| Paquete | Propósito |
|---------|-----------|
| gcc | Compilación de lxml |
| libxml2-dev | Dependencia de lxml |
| libxslt1-dev | Dependencia de lxml |

## Grafo de Dependencias Internas

```
                    ┌─────────────┐
                    │  config.py  │ (in-degree: 10, out: 0)
                    └──────┬──────┘
                           │ importado por casi todos
                           ▼
┌──────────┐     ┌──────────────────┐     ┌─────────────────┐
│  main.py │────▶│  app/server.py   │────▶│  app/api/       │
│ (in:0)   │     │  (in:1, out:8)   │     │  torznab.py     │◀────────┐
└──────────┘     └──────────────────┘     │  (in:8, out:10) │         │
                                          │  health.py      │         │
                                          │  domains.py     │         │
                                          │  providers.py   │         │
                                          └────────┬─────────┘         │
                                                   │                   │
                          ┌────────────────────────┼───────────────────┤
                          │                        │                   │
                          ▼                        ▼                   │
               ┌──────────────────┐    ┌──────────────────┐           │
               │  app/routing/    │    │  app/torznab/    │           │
               │  smart_router.py │    │  mapper.py       │           │
               │  (in:3, out:3)   │    │  caps.py         │           │
               └────────┬─────────┘    │  errors.py       │           │
                        │              └──────────────────┘           │
                        │                                              │
          ┌─────────────┼──────────────┐                              │
          │             │              │                              │
          ▼             ▼              ▼                              │
┌──────────────────────────────────────────────────┐                  │
│              app/providers/                       │                  │
│  ┌─────────────────┐  ┌──────────────────────┐   │                  │
│  │ base.py         │  │ registry.py          │   │                  │
│  │ (in:14, out:2)  │  │ (in:5, out:2)        │   │                  │
│  └────────┬────────┘  └──────────────────────┘   │                  │
│           │                                       │                  │
│  ┌────────┴──────────────────────────────┐       │                  │
│  │        books/ (12 providers)          │       │                  │
│  │        video/ (2 providers)           │       │                  │
│  │        (in:0 cada uno, out:0-3)       │       │                  │
│  └───────────────────────────────────────┘       │                  │
└──────────────────────────────────────────────────┘                  │
          │                                                            │
          ▼                                                            │
┌──────────────────────────────────────────────────┐                  │
│              app/scraping/                        │                  │
│  ┌──────────────────────────────────────────┐    │                  │
│  │ http_client.py  (in:16, out:0)           │◀───┘                  │
│  │ wp_api_client.py (in:6, out:2)           │                       │
│  │ parser.py (in:0, out:0) [huérfano]       │                       │
│  └──────────────────────────────────────────┘    │                  │
└──────────────────────────────────────────────────┘                  │
                                                                       │
┌──────────────────────────────────────────────────┐                  │
│              app/services/                        │                  │
│  ┌──────────────────────────────────────────┐    │                  │
│  │ domain_resolver.py (in:3, out:2)         │◀───┘                  │
│  │ domain_strategies.py (in:2, out:1)       │                       │
│  │ cache.py (in:2, out:0)                   │                       │
│  └──────────────────────────────────────────┘    │                  │
└──────────────────────────────────────────────────┘                  │
                                                                       │
┌──────────────────────────────────────────────────┐                  │
│              app/core/                            │                  │
│  ┌──────────────────────────────────────────┐    │                  │
│  │ models.py (in:15, out:0) [crítico]        │◀───┘                  │
│  │ categories.py (in:5, out:0)               │                       │
│  │ enums.py (in:3, out:0)                    │                       │
│  │ exceptions.py (in:6, out:0)               │                       │
│  └──────────────────────────────────────────┘    │                  │
└──────────────────────────────────────────────────┘                  │
                                                                       │
┌──────────────────────────────────────────────────┐                  │
│              app/utils/                           │                  │
│  ┌──────────────────────────────────────────┐    │                  │
│  │ zip_extractor.py (in:1, out:0)           │◀───┘                  │
│  └──────────────────────────────────────────┘    │                  │
└──────────────────────────────────────────────────┘                  │
```

## Módulos Críticos (alto in-degree)

| Módulo | In-degree | Impacto si falla |
|--------|-----------|-----------------|
| `app/scraping/http_client.py` | 16 | Todos los providers y el download proxy fallan |
| `app/core/models.py` | 15 | Todos los providers rompen (contrato SearchResult) |
| `app/providers/base.py` | 14 | Ningún provider funciona |
| `config.py` | 10 | La aplicación no arranca |
| `app/api/torznab.py` | 8 | El endpoint principal no responde |

## Puntos de Acoplamiento

- **Alto acoplamiento**: Todos los módulos de providers dependen de `http_client.py` (16 dependientes). Un cambio en la firma de HttpClient afecta a todos los providers.
- **Acoplamiento sano**: `app/core/models.py` es estable (solo dataclasses), usado por muchos pero raramente modificado.
- **Aislamiento**: Los providers individuales no dependen entre sí (plugin system bien diseñado).
- **Dependencia circular**: No detectada.

## Dependencias de Infraestructura

| Componente | Dependencia | Ubicación |
|-----------|-------------|-----------|
| Docker | Docker Engine | `Dockerfile`, `docker-compose.yml` |
| CI | GitHub Actions | `.github/workflows/` |
| Pre-commit | pre-commit framework | `.pre-commit-config.yaml` |
| Domain data | `data/domains.json` | Persistencia de estado de dominios |
