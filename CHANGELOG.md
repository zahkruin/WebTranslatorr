# Changelog

Todos los cambios notables de este proyecto se documentarán en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-06-28

### Added
- 6 nuevos providers (4 books + 2 video): Epubgratis (books), Ebiblioteca (books), Bajaebooks (books), LeLibros (books), DivxTotal (video), EliteTorrent (video)
- 12 nuevas variables de entorno en `.env.example` para los 6 nuevos providers (`_ENABLED` + `_DOMAIN` por provider)
- 12 nuevas entradas de configuración en `config.py` para los 6 nuevos providers
- Registro de 6 nuevos providers en `app/api/torznab.py` (`_init_providers()`)
- Registro de DomainResolver para 6 nuevos providers en `app/server.py` (`lifespan()`)
- Sistema de agentes especializados `.kilo/`: orquestador + 15 agentes especializados, análisis del proyecto, sistema de aprendizaje continuo
- Infraestructura de trazabilidad: CHANGELOG.md (Keep a Changelog), VERSION_HISTORY.md, registro central de errores
- Documentación de arquitectura de agentes en `.kilo/analysis/`
- CI workflow para validación de documentación agéntica (`.github/workflows/agentic-docs.yml`)
- Pre-commit hook `validate-agentic-docs` en `.pre-commit-config.yaml`
- 6 archivos de test para providers nuevos
- GitHub hooks: post-commit y post-merge para actualización automática de docs agénticos
- Scripts: `validate_docs.py`, `update-agentic-docs.sh`, `classify_changes.py`
- Plan de integración (`integration_plan.md`)
- Metodología de documentación agéntica (`.plans/agented-docs-methodology.md`)

### Changed
- Provider count: de 14 (12 books + 2 video) a 20 (16 books + 4 video)

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

## [Unreleased]

---

> **Última actualización**: 2026-06-28 — v0.1.2 con personalización de nombres de indexer.
