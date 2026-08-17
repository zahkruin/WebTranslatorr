# 04 — Mapeo de Módulos a Agentes

> **Fase**: 1.4 | **Generado**: 2026-06-28 | **Proyecto**: WebTranslatorr

## Matriz de Asignación

| Agente | Módulo(s) | LOC | Criterios |
|--------|-----------|-----|-----------|
| **api** | M1 (API Layer) | 898 | Criticidad alta, frecuencia de cambio alta, interfaz de usuario |
| **core** | M2 (Core & Config) | 258 | Criticidad crítica (contratos), usado por todos, cambio bajo |
| **providers-base** | M3 (Provider Infra) | 185 | Criticidad crítica, cambio muy bajo, aislamiento perfecto |
| **books-providers** | M4 (Books Providers) | 1,967 | Complejidad alta (>500 LOC), criticidad alta, especialización de dominio |
| **video-providers** | M5 (Video Providers) | 487 | Complejidad media, especialización de dominio (torrents vs DDL) |
| **scraping** | M6 (Scraping Layer) | 544 | Criticidad crítica (16 dependientes), especialización de dominio (HTTP) |
| **services** | M7 (Services) | 616 | Complejidad media-alta, criticidad alta |
| **routing** | M8 (Routing) | 153 | Criticidad crítica, lógica especializada, aislamiento |
| **torznab** | M9 (Torznab Protocol) | 286 | Especialización de dominio (protocolo), criticidad alta |

## Justificación de Inclusiones y Exclusiones

### ¿Por qué 9 agentes especialistas?

**Regla aplicada**: complejidad > 500 LOC o > 5 archivos → agente propio.

| Decisión | Justificación |
|----------|---------------|
| **API separado de Core** | API (898 LOC, 6 archivos) tiene frecuencia de cambio alta y es la interfaz de usuario; Core (258 LOC) es estable y define contratos. Cambios en API no deberían requerir contexto de modelos. |
| **Books y Video separados** | Aunque comparten BaseProvider, los dominios son distintos: books = DDL + cloudscraper + ZIPs; video = torrents + magnet links. La frecuencia de cambio y el conocimiento requerido difieren significativamente. |
| **Providers Base separado de Books** | BaseProvider (106 LOC) es el contrato estable; los 12 providers de books (1,967 LOC) son implementaciones que cambian frecuentemente. Un cambio en BaseProvider debe ser revisado con cuidado extremo por su impacto en 14 providers. |
| **Scraping separado de Services** | Scraping es capa de infraestructura HTTP de bajo nivel; Services son lógica de negocio (dominios, caché). Diferentes responsabilidades y frecuencias de cambio. |
| **Routing con agente propio pese a ser pequeño** | Solo 153 LOC pero criticidad crítica: una mala inferencia rompe toda búsqueda. Lógica compleja de scoring. Merece atención especializada. |
| **Torznab con agente propio** | Protocolo especializado (XML namespaces, RSS 2.0). El mapper es sensible a cambios en SearchResult. Errores de XML son difíciles de depurar. |
| **Utils (zip_extractor) agrupado con Services** | Solo 27 LOC, usado por un provider. No justifica agente propio. Relacionado con infraestructura. |

### ¿Por qué NO se crearon estos agentes?

| Propuesta descartada | Motivo |
|----------------------|--------|
| **Un agente por provider individual** | 14 agentes sería excesivo. Los providers comparten el 90% de su conocimiento (misma interfaz, mismos patrones). Agrupar por tipo (books/video) es suficiente. |
| **Un solo agente "Providers"** | 2,547 LOC + 14 archivos + 2 dominios distintos. Sería demasiado contexto para un solo agente, degradando la calidad de las respuestas. |
| **Agente "Infraestructura" (scraping + services + utils)** | 1,160 LOC, demasiado amplio. Mezcla HTTP de bajo nivel con lógica de negocio de dominios. |
| **Agente "Todo Core" (core + config + base + registry + routing)** | 596 LOC, responsabilidades muy dispares: contratos de datos + infraestructura de providers + lógica de routing. |

## Catálogo de Agentes

```
Orquestador (tech-lead)
├── planificador            # Planificación detallada de tareas complejas (fijo)
├── api                    # app/api/ + app/server.py + main.py
├── core                   # app/core/ + config.py
├── providers-base         # app/providers/base.py + registry.py
├── books-providers        # app/providers/books/ (12 providers)
├── video-providers        # app/providers/video/ (2 providers)
├── scraping               # app/scraping/ (http_client, wp_api_client, parser)
├── services               # app/services/ + app/utils/
├── routing                # app/routing/smart_router.py
├── torznab                # app/torznab/ (mapper, caps, errors)
├── testing                # tests/ (todos los tests)
├── versioning             # git, versionado semántico, CHANGELOG
└── auditor                # análisis transversal, usa a todos los demás
```

## Matriz de Responsabilidades (RACI simplificado)

| Módulo / Actividad | api | core | p-base | books | video | scraping | services | routing | torznab | testing | versioning | auditor |
|---------------------|-----|------|--------|-------|-------|----------|----------|---------|---------|---------|------------|---------|
| Endpoints Torznab | **R** | C | C | C | C | — | — | C | C | — | — | I |
| Health/Domains API | **R** | C | — | — | — | — | C | — | — | — | — | I |
| SearchResult model | I | **R** | C | C | C | — | — | — | C | C | — | I |
| Settings/Config | C | **R** | C | C | C | C | C | C | — | — | — | I |
| BaseProvider | I | C | **R** | C | C | — | — | — | — | C | — | I |
| ProviderRegistry | I | — | **R** | C | C | — | — | — | — | C | — | I |
| Book provider X | I | — | C | **R** | — | C | C | — | — | C | — | I |
| Video provider X | I | — | C | — | **R** | C | C | — | — | C | — | I |
| HttpClient | — | — | — | C | C | **R** | C | — | — | C | — | I |
| DomainResolver | I | — | — | C | C | — | **R** | — | — | C | — | I |
| SearchCache | I | — | — | C | C | — | **R** | — | — | C | — | I |
| SmartRouter | I | C | C | — | — | — | — | **R** | — | C | — | I |
| XML Mapper | I | C | — | — | — | — | — | — | **R** | C | — | I |
| Tests | C | C | C | C | C | C | C | C | C | **R** | — | I |
| Git / Versionado | — | — | — | — | — | — | — | — | — | — | **R** | I |
| Auditoría | I | I | I | I | I | I | I | I | I | I | I | **R** |

> **R** = Responsible (ejecuta), **C** = Consulted (aportan input), **I** = Informed (reciben notificación)

## Documentación Asociada por Agente

| Agente | Documentos de contexto obligatorios |
|--------|-------------------------------------|
| planificador | TODOS los documentos de contexto + analysis/ + learning/ (solo lectura, elabora planes) |
| api | 01-architecture, 13-api-endpoints, 08-torznab-protocol, 14-deployment |
| core | 03-data-models, 09-categories, 02-configuration, 16-known-issues |
| providers-base | 05-providers-base, 03-data-models, 17-adding-providers |
| books-providers | 05-providers-base, 06-provider-strategies/* (12 docs), 04-http-client, 11-cache |
| video-providers | 05-providers-base, 06-provider-strategies/mejortorrent, 06-provider-strategies/dontorrent, 04-http-client |
| scraping | 04-http-client, 01-architecture, 06-provider-strategies/* |
| services | 10-domain-resolver, 11-cache, 12-zip-extractor, 02-configuration |
| routing | 07-smart-router, 01-architecture, 09-categories |
| torznab | 08-torznab-protocol, 09-categories, 03-data-models, 13-api-endpoints |
| testing | 15-testing, 03-data-models, 05-providers-base |
| versioning | AGENTS.md (convenciones), 14-deployment, CHANGELOG.md |
| auditor | TODOS los documentos de contexto + learning/ |
