# Arquitectura de Agentes Especializados — Metodología Genérica

> **Versión**: 1.1.0
> **Tipo**: Metodología genérica reutilizable para cualquier aplicación
> **Objetivo**: Definir un proceso completo para analizar una aplicación, crear una arquitectura de agentes especializados, y establecer mecanismos de aprendizaje continuo y trazabilidad.

---

## 1. Fase de Análisis de la Aplicación Objetivo

### 1.1 Extracción de la estructura del proyecto

**Objetivo**: Obtener una visión completa del árbol de directorios, archivos, y tecnologías del proyecto.

| Paso | Acción | Herramientas/Enfoque |
|------|--------|---------------------|
| 1.1.1 | Listar el árbol completo de directorios (excluyendo `.git`, `node_modules`, `venv`, `__pycache__`, etc.) | `tree` o equivalente |
| 1.1.2 | Clasificar archivos por tipo: código fuente, configuración, tests, assets, documentación, scripts, CI/CD, Docker | Extensión + ubicación |
| 1.1.3 | Detectar el sistema de build, gestor de paquetes, framework principal, lenguaje(s) | Archivos raíz (`package.json`, `requirements.txt`, `go.mod`, `Cargo.toml`, `pom.xml`, etc.) |
| 1.1.4 | Identificar la versión del runtime/compilador requerida | `.python-version`, `.nvmrc`, `pyproject.toml`, `Dockerfile` |

**Entregable**: `analysis/01-project-structure.md` — Árbol clasificado, stack tecnológico, versión runtime.

### 1.2 Análisis de dependencias

| Paso | Acción |
|------|--------|
| 1.2.1 | Extraer la lista completa de dependencias del gestor de paquetes (directas + transitivas) |
| 1.2.2 | Clasificar dependencias: frameworks, utilidades, testing, build, runtime-only |
| 1.2.3 | Identificar dependencias internas entre módulos del proyecto |
| 1.2.4 | Construir un grafo de dependencias e identificar acoplamientos fuertes, dependencias circulares, y módulos aislados |

**Entregable**: `analysis/02-dependencies.md` — Lista clasificada + grafo de dependencias internas.

### 1.3 Identificación de módulos y funcionalidades

| Paso | Acción |
|------|--------|
| 1.3.1 | Agrupar archivos fuente en módulos lógicos (por directorio, por prefijo, por responsabilidad) |
| 1.3.2 | Para cada módulo, documentar: propósito, APIs públicas, dependencias entrantes/salientes, tecnologías internas |
| 1.3.3 | Identificar patrones arquitectónicos (MVC, hexagonal, capas, microservicios, event-driven, etc.) |
| 1.3.4 | Identificar puntos de extensión (plugins, hooks, interfaces, estrategias) y puntos de fricción (código duplicado, god objects) |

**Entregable**: `analysis/03-modules.md` — Catálogo de módulos con descripción, responsabilidad, tamaño y dependencias.

### 1.4 Mapeo de secciones a agentes especialistas

**Criterios de decisión para asignar agente propio a un módulo**:

| Criterio | Umbral | Peso |
|----------|--------|------|
| Complejidad (líneas de código, número de archivos) | > 500 LOC o > 5 archivos | Alto |
| Frecuencia de cambio esperada | Módulo activo (commits frecuentes en el último mes) | Alto |
| Criticidad | Si falla, afecta a > 1 módulo o rompe funcionalidad core | Crítico |
| Aislamiento | Fronteras bien definidas, pocas dependencias externas | Medio |
| Especialización de dominio | Requiere conocimiento específico (ej: protocolo, algoritmo, API externa) | Alto |

**Reglas de agrupación**:
- Un agente puede cubrir varios módulos pequeños y relacionados (ej: `app/utils/` + `app/helpers/`)
- Un módulo muy grande y complejo puede requerir más de un agente (ej: dividido por subdominio)
- Los módulos de infraestructura transversal (logging, configuración) suelen agruparse con el módulo que los consume

**Entregable**: `analysis/04-agent-mapping.md` — Matriz: módulo → agente propuesto, con justificación de inclusiones y exclusiones.

### 1.5 Inventario de documentación existente

| Paso | Acción |
|------|--------|
| 1.5.1 | Inventariar: `README.md`, `CONTRIBUTING.md`, `docs/`, `wiki/`, comentarios de arquitectura en código |
| 1.5.2 | Identificar documentación agéntica previa (archivos `.cursor/`, `.gemini/`, `AGENTS.md`, etc.) si existe |
| 1.5.3 | Para cada documento, evaluar: vigencia, completitud, precisión |
| 1.5.4 | Detectar gaps: módulos sin documentación, documentación obsoleta, conceptos no explicados |

**Entregable**: `analysis/05-documentation-audit.md` — Inventario con estado y gaps.

---

## 2. Creación de Agentes Especializados

### 2.1 Plantilla base de agente (común a todos)

Cada agente se define mediante un documento estructurado con las siguientes secciones obligatorias:

```markdown
# Agente: {nombre-del-agente}

## Identidad
- **Rol**: {especialista en X | testing | versiones | auditor | orquestador | planificador}
- **Sección(es) asignada(s)**: {lista de módulos/directorios bajo su responsabilidad}
- **Nivel de autonomía**: {bajo | medio | alto}

## Conocimiento base
Lista de archivos de documentación y código fuente que este agente DEBE leer antes de cualquier intervención:
1. {ruta al doc de arquitectura de su sección}
2. {ruta al doc de modelos de datos si aplica}
3. ...

## Ámbito de actuación
- **Puede modificar**: {lista de archivos/directorios permitidos}
- **No puede modificar**: {lista de archivos/directorios prohibidos}
- **Puede consultar**: {qué otros agentes o fuentes puede consultar}

## Reglas de comportamiento
- Convenciones de código específicas de su sección
- Restricciones (tecnologías, versiones, patrones)
- Anti-patrones a evitar
- Protocolo de testing pre-commit

## Registro de aprendizaje
- Ubicación de su registro de experiencias: `learning/{nombre-agente}/experiences.md`
- Ubicación de su registro de errores: `learning/{nombre-agente}/errors.md`
- Ubicación de sus patrones: `learning/{nombre-agente}/patterns.md`

## Regla de cesión al orquestador (OBLIGATORIA)
> Si el usuario te invoca directamente, NO ejecutes ninguna acción por tu cuenta. Responde indicando que debes ceder el control al orquestador. Redirige la petición al orquestador para que evalúe y asigne la tarea al agente más adecuado. Esta regla no tiene excepciones.
```

### 2.2 Agente especialista planificador (FIJO)

**Definición**: Agente fijo presente en todos los proyectos. Su función principal es, cuando el orquestador lo requiere, analizar las partes de la aplicación afectadas por la petición del usuario y elaborar un plan detallado y exhaustivo con las implementaciones, cambios y consideraciones necesarias.

**Responsabilidades**:
- Recibir del orquestador una petición del usuario que requiere planificación previa
- Identificar y analizar las partes de la aplicación afectadas por la petición (módulos, archivos, dependencias, APIs)
- Consultar a los agentes especialistas correspondientes para obtener información detallada de sus secciones cuando la petición las involucre
- Elaborar un plan de implementación detallado que incluya:
  - **Análisis de impacto**: qué módulos, archivos, funciones, clases y dependencias se ven afectados
  - **Descomposición en subtareas**: lista ordenada de pasos de implementación, con dependencias entre ellos
  - **Archivos a modificar/crear**: para cada paso, listar los archivos concretos y el tipo de cambio (crear, modificar, eliminar)
  - **Consideraciones de arquitectura**: cómo se integra el cambio en la arquitectura existente, patrones a seguir, convenciones aplicables
  - **Riesgos identificados**: posibles problemas, efectos secundarios, puntos de fricción
  - **Estrategia de testing**: qué tipo de tests se necesitan y qué casos deben cubrir
  - **Estrategia de versionado**: estimación del tipo de bump (MAJOR/MINOR/PATCH) si aplica
  - **Agentes necesarios**: qué agentes especialistas deben intervenir y en qué orden
  - **Alternativas consideradas**: otros enfoques evaluados y por qué se descartaron
- Entregar el plan al orquestador para su revisión y aprobación
- Actualizar el plan si el orquestador solicita modificaciones
- Colaborar con el agente auditor cuando sea necesario verificar la viabilidad del plan

**Conocimiento base**:
- Documentación de arquitectura global (`01-architecture.md` o equivalente)
- Matriz de módulos → agentes (`analysis/04-agent-mapping.md`)
- Catálogo completo de agentes y sus responsabilidades
- Documentación de patrones y convenciones del proyecto

**Ámbito de actuación**:
- **Puede modificar**: exclusivamente el plan (documento `.cursor/plans/{id}-plan.md` o similar). No modifica código fuente.
- **No puede modificar**: ningún archivo de código fuente, configuración, tests, documentación de agentes, ni CHANGELOG
- **Puede consultar**: cualquier agente especialista, documentación del proyecto, código fuente (solo lectura)

**Protocolo de actuación**:

```
Orquestador solicita plan para petición del usuario
  │
  ▼
1. ANALIZAR LA PETICIÓN: extraer requisitos, objetivos, restricciones
2. IDENTIFICAR ÁREAS AFECTADAS: determinar qué módulos/secciones se ven impactados
3. CONSULTAR AGENTES: solicitar a los especialistas de las secciones afectadas
   que analicen en profundidad sus áreas y reporten:
   - Estado actual del código relevante
   - Posibles puntos de extensión o modificación
   - Riesgos específicos de su sección
   - Tests existentes que podrían verse afectados
4. CONSULTAR APRENDIZAJE: revisar CENTRAL_ERROR_REGISTRY.md y CROSS_AGENT_INSIGHTS.md
   para detectar antecedentes relevantes
5. ELABORAR PLAN: estructurar el plan completo según el formato definido
6. ENTREGAR AL ORQUESTADOR: presentar el plan para revisión
7. REFINAR: si el orquestador solicita cambios, iterar hasta aprobación
```

**Formato del plan**:

```markdown
# Plan: {título descriptivo}

> **ID**: PLAN-{YYYYMMDD}-{NNN}
> **Fecha**: YYYY-MM-DD
> **Origen**: {petición original del usuario}
> **Estado**: borrador | en_revisión | aprobado | en_ejecución | completado | cancelado

## 1. Análisis de impacto

### Módulos afectados
| Módulo | Tipo de afectación | Criticidad |
|--------|-------------------|------------|
| {nombre} | {nuevo/cambio/eliminación} | {crítica/alta/media/baja} |

### Dependencias impactadas
- Internas: {lista de dependencias entre módulos afectadas}
- Externas: {nuevas dependencias de paquetes, cambios de versión, etc.}

## 2. Plan de implementación

### Paso 1: {título del paso}
- **Archivos**: `ruta/archivo1.py` (modificar), `ruta/archivo2.py` (crear)
- **Descripción**: qué se va a hacer y cómo
- **Depende de**: {ninguno | paso N}
- **Agente asignado**: {nombre del agente especialista}
- **Consideraciones**: {convenciones, patrones, restricciones}

### Paso 2: {título del paso}
- ...

## 3. Consideraciones de arquitectura
- Patrones a aplicar
- Convenciones a seguir
- Restricciones tecnológicas
- Integración con módulos existentes

## 4. Riesgos identificados
| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|

## 5. Estrategia de testing
- Tests unitarios necesarios
- Tests de integración necesarios
- Casos límite a cubrir
- Tests existentes que deben actualizarse

## 6. Estrategia de versionado
- Tipo de bump estimado: {MAJOR/MINOR/PATCH}
- Justificación

## 7. Agentes involucrados
| Agente | Rol | Orden de intervención |
|--------|-----|---------------------|

## 8. Alternativas consideradas
| Alternativa | Ventajas | Desventajas | Motivo de descarte |
|-------------|----------|-------------|-------------------|

## 9. Referencias
- Documentación relacionada
- Issues/PRs relacionados
- Errores previos relacionados (CENTRAL_ERROR_REGISTRY)
```

**Regla de cesión al orquestador (OBLIGATORIA)**:
> Si el usuario te invoca directamente, NO ejecutes ninguna acción por tu cuenta. Responde indicando que debes ceder el control al orquestador. Redirige la petición al orquestador para que evalúe y asigne la tarea al agente más adecuado. Esta regla no tiene excepciones.

### 2.3 Agente especialista por sección

**Definición**: Un agente por cada sección identificada en la fase 1, responsable en profundidad de esa sección.

**Responsabilidades**:
- Comprender la arquitectura, modelos de datos, flujos y dependencias de su sección
- Implementar nuevas funcionalidades dentro de su sección
- Corregir bugs en su sección
- Modificar configuraciones que afecten a su sección
- Actualizar la documentación asociada a su sección
- Registrar todas sus acciones, errores y lecciones en su registro de aprendizaje
- Colaborar con otros agentes especialistas cuando una tarea cruza fronteras de sección (siempre bajo coordinación del orquestador)

**Conocimiento inicial**: En el momento de su creación, recibe:
- Toda la documentación de análisis de su sección (fase 1)
- El código fuente completo de los archivos bajo su responsabilidad
- Las reglas de codificación y testing aplicables

**Entregable**: Un documento de definición por cada agente especialista (`agents/{nombre-agente}.md`).

### 2.4 Agente especialista en pruebas

**Definición**: Responsable exclusivo de la estrategia y ejecución de testing del proyecto.

**Responsabilidades**:
- Diseñar tests para cualquier cambio realizado por cualquier agente especialista (unitarios, integración, e2e según corresponda)
- Ejecutar la suite de tests completa antes de validar cualquier cambio
- Reportar resultados de tests al orquestador
- Mantener los tests existentes actualizados cuando las APIs o comportamientos cambian
- Identificar gaps de cobertura y proponer nuevos tests al orquestador
- Registrar en su aprendizaje: fallos de test recurrentes, patrones de mock/stub efectivos, configuraciones de CI problemáticas
- Conocer los frameworks de testing del proyecto, fixtures disponibles, y patrones establecidos

**Interacción con otros agentes**:
- Recibe del orquestador: la especificación de qué tests se necesitan para un cambio concreto
- Entrega al orquestador: resultados de tests, informe de cobertura, recomendaciones
- Colabora con agentes especialistas para entender el comportamiento esperado de su sección

### 2.5 Agente especialista en versiones y repositorio

**Definición**: Responsable de la gestión del repositorio git, versionado semántico, y sincronización de la versión entre git tags y el código en runtime.

**Responsabilidades**:
- Ejecutar operaciones git: commits, creación de ramas, merges, tags, resolución de conflictos simples
- Determinar el incremento de versión según Semantic Versioning (MAJOR.MINOR.PATCH):
  - **MAJOR**: cambios que rompen compatibilidad hacia atrás (API pública, esquema de datos, configuración)
  - **MINOR**: nuevas funcionalidades compatibles hacia atrás
  - **PATCH**: correcciones de bugs compatibles hacia atrás
- **Sincronizar la versión con el código**: al crear un tag `vX.Y.Z`, el agente DEBE actualizar el archivo `VERSION` en la raíz del proyecto con el valor `X.Y.Z` (sin prefijo "v"). Este archivo es leído por el código en runtime (ej: `app/core/version.py`) para que la API, health checks, y metadatos reflejen siempre la versión real del despliegue.
- Mantener `CHANGELOG.md` actualizado con cada release
- Gestionar releases y tags
- Garantizar integridad del historial (no commits de secretos, no archivos binarios grandes, mensajes de commit significativos)
- Mantener `learning/VERSION_HISTORY.md` con el historial completo de versiones y justificación de cada incremento

**Protocolo de sincronización de versión**:
```
Al crear un release:
1. Determinar el nuevo número de versión X.Y.Z según criterios SemVer
2. Escribir "X.Y.Z\n" en el archivo VERSION (raíz del proyecto, sin prefijo "v")
3. Hacer commit del cambio: "chore(version): bump to X.Y.Z"
4. Crear tag anotado: git tag -a vX.Y.Z -m "vX.Y.Z: {descripción breve}"
5. Actualizar CHANGELOG.md con la nueva versión
6. Actualizar learning/VERSION_HISTORY.md
7. Push: commits + tags
```

**Archivo VERSION**:
- Ubicación: `VERSION` (raíz del proyecto)
- Formato: una sola línea con `MAJOR.MINOR.PATCH` (sin prefijo "v", sin saltos de línea extra)
- Ejemplo: `0.1.2`
- Consumido por: `app/core/version.py` (módulo `get_version()`), que es importado por `app/server.py` (metadata de FastAPI) y `app/api/health.py` (endpoint raíz `GET /`)

**Criterios de decisión para el incremento de versión**:

| Naturaleza del cambio | Bump |
|-----------------------|------|
| Nuevo endpoint de API pública | MINOR |
| Cambio en firma de función pública | MAJOR |
| Cambio en esquema de respuesta JSON | MAJOR |
| Nueva dependencia externa | MINOR |
| Corrección de bug sin cambiar API | PATCH |
| Refactor interno sin cambio de comportamiento | PATCH |
| Cambio en variables de entorno requeridas | MAJOR |
| Deprecación de funcionalidad | MINOR |

### 2.6 Agente auditor

**Definición**: Agente transversal que utiliza al resto de agentes para analizar el código y detectar problemas.

**Responsabilidades**:
- Analizar el código de cualquier sección, solicitando a los agentes especialistas que realicen análisis profundos de sus respectivas áreas
- Detectar:
  - **Errores**: bugs potenciales, condiciones de carrera, fugas de memoria, errores de lógica
  - **Incongruencias**: código que contradice la documentación, documentación que no refleja la realidad
  - **Inconsistencias**: diferentes estilos o enfoques para el mismo problema en distintas secciones
  - **Desviaciones de buenas prácticas**: violaciones de principios SOLID, DRY, patrones establecidos
  - **Violaciones de la arquitectura**: acoplamientos no permitidos, dependencias circulares, bypass de capas
- Emitir informes de auditoría estructurados con hallazgos categorizados por severidad (crítico, alto, medio, bajo, informativo)
- Verificar que correcciones previas se han aplicado correctamente y no han reintroducido problemas
- Revisar periódicamente los registros de aprendizaje para detectar patrones de error sistémicos

**Ciclo de auditoría**:
1. El orquestador solicita una auditoría (por tiempo, por evento, o por demanda del usuario)
2. El auditor solicita a cada agente especialista un auto-análisis de su sección
3. El auditor consolida hallazgos, los categoriza y asigna severidad
4. El auditor entrega el informe al orquestador
5. El orquestador asigna las correcciones a los agentes correspondientes
6. El auditor verifica las correcciones en la siguiente auditoría

### 2.7 Agente orquestador (tech lead)

**Definición**: Punto único de control y coordinación de todos los agentes.

**Responsabilidades**:
- **Ser el punto único de entrada**: toda petición del usuario debe llegar a él
- **Analizar y descomponer**: ante cualquier petición, analizar su alcance y descomponerla en subtareas
- **Decidir si planificar**: para peticiones complejas (múltiples módulos, cambio arquitectónico, nueva funcionalidad grande), delegar en el agente planificador la elaboración de un plan detallado antes de ejecutar
- **Seleccionar agente(s)**: determinar qué agente(s) es/son el/los más adecuado(s) para cada subtarea, basándose en:
  - La sección afectada (→ agente especialista correspondiente)
  - El tipo de tarea (feature → especialista, test → agente de pruebas, release → agente de versiones, revisión → auditor, planificación compleja → planificador)
  - La complejidad (si abarca múltiples secciones, coordinar varios especialistas)
- **Coordinar colaboración**: cuando una tarea cruza fronteras de sección, orquestar la comunicación entre agentes
- **Validar resultados**: revisar que cada agente ha completado su tarea correctamente antes de integrar
- **Resolver conflictos**: si dos agentes producen cambios incompatibles, arbitrar la solución
- **Mantener coherencia global**: asegurar que el proyecto no se desvía de su arquitectura y convenciones

**Conocimiento del orquestador**:
- Catálogo completo de agentes (identidad, sección, capacidades)
- Matriz de módulos → agentes (de la fase 1.4)
- Visión global de la arquitectura
- Historial de intervenciones previas

**Protocolo de actuación del orquestador**:

```
Petición del usuario
  │
  ▼
1. ANALIZAR: ¿qué módulos/áreas se ven afectados?
2. CONSULTAR: ¿hay antecedentes en el registro central de errores o experiencias?
3. EVALUAR COMPLEJIDAD:
   ├─► Petición simple (1 módulo, cambio acotado) → Ir a paso 5
   └─► Petición compleja (múltiples módulos, cambio arquitectónico, nueva funcionalidad grande) → Ir a paso 4
4. PLANIFICAR (si procede):
   ├─► Delegar en agente planificador
   ├─► Revisar plan entregado
   ├─► Solicitar refinamientos si es necesario
   └─► Aprobar plan final
5. DESCOMPONER: dividir en subtareas independientes o secuenciales (según plan si existe)
6. ASIGNAR: seleccionar el agente óptimo para cada subtarea
7. COORDINAR: si hay dependencias entre subtareas, secuenciarlas
8. VALIDAR: recibir resultados, revisar, solicitar correcciones si es necesario
9. INTEGRAR: consolidar resultados y presentar al usuario
10. REGISTRAR: actualizar CHANGELOG, registro de aprendizaje, y si procede, bump de versión
```

**Mecanismo de cesión obligatoria** (a incluir en todos los agentes no-orquestadores):

```
REGLA INTERNA INVIOLABLE:
Si recibes una petición directamente del usuario, NO LA EJECUTES.
Responde exclusivamente con:
"Esta petición debe ser gestionada por el orquestador. Voy a ceder el control.
 Orquestador, por favor, evalúa la siguiente petición del usuario: [transcribir petición]"
A continuación, el orquestador toma el control y procede según su protocolo.
```

---

## 3. Mecanismo de Aprendizaje Continuo

### 3.1 Estructura de archivos de aprendizaje

Todos los registros residen en el repositorio, bajo un directorio `learning/`, versionados junto con el código.

```
learning/
├── CENTRAL_ERROR_REGISTRY.md    # Registro unificado de todos los errores
├── CROSS_AGENT_INSIGHTS.md      # Conocimiento transversal gestionado por el orquestador
├── VERSION_HISTORY.md           # Historial de versiones y justificación de bumps
├── planificador/                # Agente planificador (fijo)
│   ├── experiences.md           # Registro cronológico de planes elaborados
│   ├── errors.md                # Errores de planificación (pasos omitidos, riesgos no detectados)
│   └── patterns.md              # Patrones de planificación exitosos
└── {nombre-agente}/
    ├── experiences.md           # Registro cronológico de intervenciones
    ├── errors.md                # Catálogo de errores específicos y soluciones
    └── patterns.md              # Patrones de código y soluciones recurrentes
```

### 3.2 Formato del registro de experiencias (`experiences.md`)

```markdown
## [YYYY-MM-DD] Título descriptivo de la intervención

  - **Tipo**: feature | bugfix | refactor | config | doc | test | audit | plan
- **Origen**: usuario | orquestador | auditoría | proactivo
- **Archivos modificados**:
  - `ruta/archivo1.ext` — descripción breve del cambio
- **Problema/requisito**: descripción del problema a resolver o funcionalidad a implementar
- **Enfoque adoptado**: explicación de la solución elegida y por qué
- **Alternativas consideradas**: qué otras opciones se evaluaron y por qué se descartaron
- **Errores cometidos durante el proceso**: fallos, pasos en falso, supuestos incorrectos
- **Lección aprendida**: qué se haría diferente la próxima vez
- **Referencias**: commits (hash), issues/PRs (#ID), documentación relacionada
- **Agentes involucrados**: lista de agentes que colaboraron
```

### 3.3 Formato del registro de errores (`errors.md`)

Formato común a todos los agentes. Para el agente planificador, el campo **Módulo afectado** se sustituye por **Plan afectado** con el ID del plan.

```markdown
## [ERROR-001] Título descriptivo

- **Fecha detección**: YYYY-MM-DD
- **Detectado por**: {agente}
- **Severidad**: crítica | alta | media | baja
- **Módulo/Plan afectado**: {nombre del módulo | ID del plan}
- **Síntomas**: descripción de lo que se observa
- **Causa raíz**: explicación de la causa subyacente
- **Solución**: pasos concretos para resolver
- **Verificado por**: {agente auditor o tests}
- **Lección**: aprendizaje extraído para prevenir recurrencia
- **Estado**: detectado | en_progreso | resuelto | verificado | reabierto
```

### 3.4 Formato del registro central de errores (`CENTRAL_ERROR_REGISTRY.md`)

Tabla unificada accesible por todos los agentes:

```markdown
| ID | Fecha | Agente | Módulo | Severidad | Descripción | Solución | Lección | Estado |
|----|-------|--------|--------|-----------|-------------|----------|---------|--------|
| E-001 | 2026-01-15 | especialista-api | api | alta | Timeout en consultas > 5s | Añadir paginación | Siempre paginar consultas sin límite explícito | resuelto |
| E-002 | 2026-02-01 | auditor | core | crítica | Race condition en caché | Añadir lock distribuido | Cachés compartidos requieren sincronización | resuelto |
```

### 3.5 Protocolo de consulta pre-acción (OBLIGATORIO)

Antes de que cualquier agente inicie una nueva intervención, debe ejecutar este protocolo:

```
PASO 1: Leer learning/CENTRAL_ERROR_REGISTRY.md
        → Verificar si el problema ya fue encontrado y resuelto
        → Si existe entrada relacionada, aplicar la solución documentada

PASO 2: Leer learning/{nombre-agente}/errors.md
        → Verificar errores específicos de su sección

PASO 3: Leer learning/{nombre-agente}/experiences.md
        → Obtener contexto histórico de intervenciones similares

PASO 4: Si la tarea afecta a múltiples secciones, solicitar al orquestador
        que consulte learning/CROSS_AGENT_INSIGHTS.md

PASO 5: Reportar al orquestador cualquier antecedente relevante encontrado
        antes de proceder
```

### 3.6 Compartición de conocimiento entre agentes

**Flujo de compartición**:

```
Agente A completa una intervención
  │
  ├─► Registra en learning/{A}/experiences.md
  ├─► Si hubo errores, registra en learning/{A}/errors.md
  │
  ▼
Orquestador revisa el registro
  │
  ├─► ¿La lección es aplicable a otros agentes?
  │     SÍ → Registrar en learning/CROSS_AGENT_INSIGHTS.md
  │     NO → Fin
  │
  ├─► ¿El error es nuevo y relevante para el proyecto?
  │     SÍ → Registrar en learning/CENTRAL_ERROR_REGISTRY.md
  │     NO → Fin
  │
  ▼
Próxima auditoría: el agente auditor verifica que las lecciones
transversales se están aplicando en todas las secciones

Caso especial — Agente planificador:
  │
  ├─► Registra en learning/planificador/experiences.md el plan aprobado
  │   y su resultado final (éxito, desviaciones, lecciones)
  ├─► Si se detectaron fallos en el plan (pasos omitidos, riesgos no
  │   identificados, estimaciones incorrectas), registra en
  │   learning/planificador/errors.md
  └─► El orquestador evalúa si la experiencia debe promoverse a
      CROSS_AGENT_INSIGHTS.md como patrón de planificación
```

---

## 4. Sistema de Trazabilidad y Documentación de Cambios

### 4.1 CHANGELOG.md

**Formato**: Keep a Changelog (https://keepachangelog.com/)

**Ubicación**: raíz del repositorio

**Estructura**:

```markdown
# Changelog

## [MAJOR.MINOR.PATCH] — YYYY-MM-DD

### Added
- Descripción de nuevas funcionalidades

### Changed
- Cambios en funcionalidades existentes

### Deprecated
- Funcionalidades marcadas como obsoletas

### Removed
- Funcionalidades eliminadas

### Fixed
- Correcciones de bugs

### Security
- Correcciones de vulnerabilidades
```

**Responsable**: El agente de versiones actualiza CHANGELOG.md como paso final de cada release.

**Creación inicial**: Si `CHANGELOG.md` no existe, el agente de versiones lo crea durante la primera release, incluyendo una sección `[Unreleased]` para cambios no publicados aún.

### 4.2 Trazabilidad en commits

Cada commit debe incluir en su mensaje:
- El identificador del agente que realizó el cambio: `[agent: {nombre-agente}]`
- Referencia al issue/PR si aplica
- Tipo de cambio (para clasificación en CHANGELOG)

Ejemplo:
```
fix(api): corregir timeout en búsquedas multicriterio [agent: especialista-api]

Añadido límite de resultados por defecto para evitar consultas sin límite
que causaban timeout en providers lentos.

Ref: E-001
```

### 4.3 Historial de versiones (`learning/VERSION_HISTORY.md`)

```markdown
| Versión | Fecha | Tipo de bump | Justificación | Agente responsable |
|---------|-------|-------------|---------------|-------------------|
| 1.0.0 | 2026-01-01 | — | Release inicial | versiones |
| 1.1.0 | 2026-01-15 | MINOR | Añadido endpoint /api/search avanzado | versiones |
| 1.1.1 | 2026-01-20 | PATCH | Corregido bug en caché (E-002) | versiones |
```

---

## 5. Verificación de la Integración

### 5.1 Criterios de aceptación del sistema de agentes

| Criterio | Cómo verificarlo |
|----------|-----------------|
| **Cobertura total**: cada módulo de la fase 1 tiene un agente asignado | Contrastar `analysis/04-agent-mapping.md` con `analysis/03-modules.md` |
| **Orquestador único**: ninguna petición se ejecuta sin pasar por el orquestador | Revisar registros de aprendizaje: toda entrada debe mencionar al orquestador como origen o coordinador |
| **Trazabilidad completa**: todo cambio está en CHANGELOG.md, registro de aprendizaje y git | Auditoría cruzada cada N intervenciones |
| **Aprendizaje activo**: antes de cada intervención se consulta el registro de errores | Los registros de experiencia deben incluir referencia a la consulta pre-acción |
| **Auditoría periódica**: el agente auditor emite informes regulares | Verificar existencia y periodicidad de informes de auditoría |

### 5.2 Pruebas de integración del sistema de agentes

**Escenario 1: Feature simple en una sección**
- Petición: "Añadir campo X al modelo Y"
- Esperado: Orquestador → asigna a especialista de esa sección → especialista implementa → agente de pruebas valida → agente de versiones registra en CHANGELOG

**Escenario 2: Bug cross-sección**
- Petición: "El endpoint Z falla cuando el provider W devuelve datos mal formados"
- Esperado: Orquestador → asigna análisis a especialista-api y especialista-provider-W → ambos colaboran → pruebas valida → versiones registra

**Escenario 3: Petición directa a agente no-orquestador**
- Petición directa al agente de pruebas: "Ejecuta los tests"
- Esperado: Agente de pruebas cede el control al orquestador → orquestador evalúa y reasigna al agente de pruebas si procede

**Escenario 4: Error ya conocido**
- Petición que coincide con un error ya registrado en CENTRAL_ERROR_REGISTRY.md
- Esperado: El agente asignado detecta el antecedente en la consulta pre-acción, aplica la solución documentada, y lo notifica al orquestador

**Escenario 5: Auditoría completa**
- Petición: "Audita el proyecto"
- Esperado: Orquestador → auditor → auditor solicita auto-análisis a cada especialista → consolida informe → orquestador asigna correcciones → auditor verifica en siguiente ciclo

**Escenario 6: Planificación de feature compleja**
- Petición: "Añade soporte para un nuevo tipo de contenido (música)"
- Esperado: Orquestador → evalúa complejidad (alta, múltiples módulos) → delega en planificador → planificador analiza impacto, consulta a especialistas (api, routing, torznab, categorías) → elabora plan detallado → orquestador revisa y aprueba → asigna pasos a agentes según el plan → ejecuta → pruebas valida → versiones registra

**Escenario 7: Petición directa al agente planificador**
- Petición directa: "Planifica cómo añadir cache distribuida"
- Esperado: Planificador cede el control al orquestador → orquestador evalúa y reasigna al planificador si procede

**Escenario 8: Release con sincronización de versión**
- Petición: "Versiona y sube los cambios"
- Esperado: Orquestador → versiones determina bump → versiones actualiza `VERSION` con el nuevo número → commit → crea tag `vX.Y.Z` → actualiza CHANGELOG → actualiza VERSION_HISTORY → push
- Verificación: `GET /` devuelve `{"version": "X.Y.Z"}` (coincide con el tag); `app.version` en FastAPI coincide

### 5.3 Métricas de calidad del sistema de agentes

| Métrica | Definición | Frecuencia de medición |
|---------|-----------|----------------------|
| Tiempo de resolución | Tiempo desde petición hasta integración completada | Por intervención |
| Tasa de reincidencia | % de errores que reaparecen tras ser marcados como "resueltos" | Mensual |
| Cobertura de tests | % de código cubierto por tests | Por cada cambio |
| Frecuencia de auditoría | Días entre informes de auditoría | Mensual |
| Integridad de CHANGELOG | % de releases con entrada en CHANGELOG | Por release |
| Sincronización de versión | Coincidencia entre tag git, archivo VERSION, y `GET /` response | Por release |
| Eficacia del aprendizaje | % de intervenciones donde la consulta pre-acción encontró antecedentes útiles | Por intervención |

---

## 6. Entregables por Fase

| Fase | Entregable | Responsable |
|------|-----------|-------------|
| 1.1 | `analysis/01-project-structure.md` | Analista (humano o agente general) |
| 1.2 | `analysis/02-dependencies.md` | Analista |
| 1.3 | `analysis/03-modules.md` | Analista |
| 1.4 | `analysis/04-agent-mapping.md` | Analista + futuro orquestador |
| 1.5 | `analysis/05-documentation-audit.md` | Analista |
| 2.2 | `agents/planificador.md` (fijo, uno por proyecto) | Creador del sistema |
| 2.3–2.7 | `agents/{nombre-agente}.md` (uno por agente) | Creador del sistema |
| 3.1–3.6 | `learning/` (directorio completo con subdirectorios y plantillas) | Orquestador (inicial) |
| 4.1 | `CHANGELOG.md` (creado si no existe) | Agente de versiones |
| 4.1b | `VERSION` (archivo con versión actual, creado si no existe) | Agente de versiones |
| 4.1c | `app/core/version.py` (módulo `get_version()`, creado si no existe) | Agente de versiones |
| 4.3 | `learning/VERSION_HISTORY.md` | Agente de versiones |
| 5.1–5.3 | Checklist de verificación + resultados de escenarios | Orquestador + auditor |

---

## 7. Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|-----------|
| Solapamiento de responsabilidades entre agentes | Media | Alto | Definir fronteras precisas en la fase 1.4; el orquestador arbitra disputas y ajusta asignaciones |
| El orquestador se convierte en cuello de botella | Media | Alto | El orquestador puede despachar tareas simples sin análisis profundo; delegar subtareas en paralelo cuando sea posible; el planificador reduce carga cognitiva en tareas complejas |
| El planificador produce planes incompletos o erróneos | Media | Alto | El orquestador revisa y aprueba todo plan antes de ejecutarlo; el auditor verifica en post-mortem la correspondencia plan↔resultado; los errores de planificación se registran en learning/planificador/errors.md |
| Registro de aprendizaje se vuelve obsoleto o ruidoso | Alta | Medio | El agente auditor revisa y limpia periódicamente los registros; entradas sin referencias a commits se marcan como obsoletas |
| Un agente ignora la regla de cesión al orquestador | Baja | Crítico | Incluir la regla como primera instrucción del agente; el auditor verifica en cada auditoría que no hay intervenciones no orquestadas |
| Inconsistencia entre documentación y código | Alta | Medio | El agente auditor verifica documentación vs código; cada agente especialista es responsable de mantener actualizada la doc de su sección |
| Agentes que alucinan información o toman decisiones incorrectas | Media | Alto | El orquestador valida resultados; el agente de pruebas ejecuta tests; el auditor revisa código generado; el planificador cruza información de múltiples agentes para verificar consistencia |
| El sistema de aprendizaje crece indefinidamente | Alta | Bajo | Archivos rotados por año; entradas antiguas movidas a `learning/archive/` por el orquestador |

---

## 8. Apéndice: Secuencia de Implementación Recomendada

1. **Ejecutar la fase 1** (análisis completo de la aplicación)
2. **Crear al orquestador** (necesario para todo lo demás)
3. **Crear al agente planificador** (fijo, necesario para tareas complejas)
4. **Crear los agentes especialistas** según la matriz de la fase 1.4
5. **Crear el agente de pruebas** (necesario para validar cualquier cambio)
6. **Crear el agente de versiones** (necesario para releases y CHANGELOG)
7. **Crear el agente auditor** (último, porque necesita que los demás existan para poder invocarlos)
8. **Inicializar la estructura `learning/`** con plantillas vacías
9. **Ejecutar los escenarios de verificación** (fase 5.2)
10. **Primera auditoría** para establecer línea base
11. **Operación normal**: el orquestador recibe peticiones y coordina
