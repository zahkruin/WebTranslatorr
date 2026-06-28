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

## [Unreleased]

---

> **Última actualización**: 2026-06-28 — release inicial con 20 providers y sistema de agentes.
