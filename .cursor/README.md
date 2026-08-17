# 📚 Documentación Agéntica — WebTranslatorr

> **⚠️ LEE ESTO PRIMERO. OBLIGATORIO PARA TODO AGENTE.**
>
> Este directorio (`.cursor/`) es la **única fuente de verdad** de toda la documentación
> agéntica del proyecto: planes, agentes, metodología, contexto de código, análisis,
> aprendizaje, mapeos y reglas.
>
> **Regla inviolable:** antes de leer, planificar, modificar o ejecutar **cualquier cosa**
> sobre este proyecto, debes leer este `README.md` y el `AGENTS.md` (raíz del proyecto).
> No existen otros repositorios de documentación agéntica.

---

## 🚀 Punto de entrada — Orden de lectura obligatorio

1. **`README.md`** ← este archivo (dónde está todo)
2. **`AGENTS.md`** (raíz del proyecto) ← visión general, stack, convenciones, anti-patrones, reglas
3. **`INDEX.md`** ← mapa de casos de uso → documentación específica
4. **`methodology.md`** ← Metodología de Documentación Agéntica (MDA)

> Las reglas en `.cursor/rules/*.mdc` (cargadas automáticamente por Cursor) y los agentes
> especializados (`agent/*.md`) enumeran además sus propios documentos de lectura
> obligatoria. Cúmplelos siempre.

---

## 🗂️ Estructura del directorio

```
.cursor/
├── README.md                ← punto de entrada OBLIGATORIO (este archivo)
├── INDEX.md                 ← mapa de casos de uso → documentación
├── methodology.md           ← Metodología de Documentación Agéntica (MDA)
├── styleguide.md            ← convenciones de código
├── doc-mapping.json         ← mapeo archivos fuente ↔ documentación a actualizar
├── phase0-ficha-tecnica.yaml← ficha técnica del proyecto
├── phase1-modules.json      ← análisis estático de módulos
├── phase2-dynamic.json      ← análisis dinámico (endpoints, issues)
│
├── rules/                   ← reglas activas (.mdc) cargadas automáticamente por Cursor
│   ├── project-overview.mdc ← reglas globales (alwaysApply)
│   ├── coding-style.mdc     ← convenciones de código
│   ├── providers.mdc        ← reglas de providers
│   └── torznab.mdc          ← reglas de protocolo Torznab
│
├── context/                 ← documentos de contexto del código (numerados 01–17)
│   └── 06-provider-strategies/  ← estrategias de scraping por provider
│
├── analysis/                ← análisis estático del proyecto (Fase 1 MDA)
├── agent/                   ← definiciones de los agentes especializados y orquestador
├── learning/                ← registro de errores, experiencias y patrones por agente
│   ├── CENTRAL_ERROR_REGISTRY.md   ← registro central de errores
│   ├── CROSS_AGENT_INSIGHTS.md     ← conocimiento transversal
│   └── VERSION_HISTORY.md          ← historial de versionado semántico
│
├── plans/                   ← planes de trabajo (históricos y activos)
│
└── legacy/                  ← documentación antigua/redundante, conservada solo como referencia
```

> También existe `AGENTS.md` en la **raíz del proyecto**, que Cursor lee automáticamente
> como instrucción global. Mantén ambos sincronizados (este README es la referencia
> estructural; `AGENTS.md` es la referencia operativa).

---

## 🧭 ¿Qué hay en cada subdirectorio?

| Subdirectorio | Propósito | Cuándo leerlo |
|---------------|-----------|---------------|
| **raíz** | Guías globales, método, mapeos y fases | Siempre (punto de partida) |
| `rules/` | Reglas `.mdc` cargadas automáticamente por Cursor | Automático (no manual) |
| `context/` | Cómo funciona el código (arquitectura, módulos, protocolo, providers) | Según la tarea (ver `INDEX.md`) |
| `analysis/` | Resultados del análisis estático del proyecto | Coordinación, planificación |
| `agent/` | Roles, responsabilidades y protocolo de cada agente | Antes de asumir un rol |
| `learning/` | Errores, experiencias y patrones aprendidos | Antes de intervenir (evitar repetir errores) |
| `plans/` | Planes de implementación detallados | Al planificar trabajo complejo |
| `legacy/` | Documentación obsoleta o duplicada | Solo por referencia histórica |

---

## 🔧 Herramientas que operan sobre este directorio

| Herramienta | Ubicación | Propósito |
|-------------|-----------|-----------|
| `validate_docs.py` | `scripts/validate_docs.py` | Valida integridad de la doc agéntica (`--strict` en CI) |
| `classify_changes.py` | `scripts/classify_changes.py` | Clasifica cambios de código fuente → docs afectados |
| `update-agentic-docs.sh` | `scripts/update-agentic-docs.sh` | Sugiere/ejecuta actualización de docs |
| pre-commit hook | `.pre-commit-config.yaml` | Ejecuta `validate_docs.py --strict` |
| CI | `.github/workflows/agentic-docs.yml` | Bloquea PRs con cambios críticos sin actualizar docs |
| git hooks | `.githooks/post-commit`, `post-merge` | Avisan al modificar código fuente |

---

## ⛔ Regla de mantenimiento obligatorio

Todo cambio en archivos fuente (`app/`, `config.py`, `main.py`, `Dockerfile`,
`docker-compose*.yml`) **debe** ir acompañado de la actualización de los documentos
agénticos correspondientes. Usa `doc-mapping.json` para identificar qué documentos
actualizar y ejecuta `python scripts/validate_docs.py --strict` antes de hacer commit.

---

> **Última actualización**: 2026-08-17 — migración al ecosistema Cursor (`.cursor/` + `AGENTS.md` + `rules/`).
