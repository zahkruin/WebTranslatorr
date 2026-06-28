# Metodología de Documentación Agéntica (MDA)

> **Versión:** 1.0 — Marco reutilizable para analizar cualquier aplicación software y generar documentación agéntica estructurada, mantenible y auto-actualizable.
> **Aplica a:** Web, backend, móvil, CLI, desktop, monorepo.
> **Referencia validada:** WebTranslatorr (`.gemini/`).

---

## 0. Clasificación del Proyecto (Fase 0)

**Objetivo:** Determinar el tipo de aplicación para activar/desactivar módulos del análisis y seleccionar las herramientas adecuadas.

### 0.1 Matriz de Decisión

| Dimensión | Opciones | Qué activa |
|-----------|----------|------------|
| **Runtime** | Web (SPA/SSR), Backend (API/microservicio), Móvil (nativo: Swift/Kotlin, híbrido: React Native/Flutter), CLI, Desktop, Lambda/Serverless | Módulos de análisis específicos |
| **Lenguaje(s)** | Python, TypeScript/JS, Go, Rust, Java/Kotlin, C#/.NET, Ruby, PHP, multi-lenguaje | Toolchain de análisis |
| **Framework** | FastAPI, Express, Next.js, React Native, Spring Boot, etc. | Patrones de escaneo |
| **Build system** | pip, npm/yarn/pnpm, cargo, go mod, Maven/Gradle, dotnet CLI | Análisis de dependencias |
| **Estructura** | Monolito, microservicios, monorepo (Nx/Turborepo), plugin-system | Estrategia de particionado |
| **Persistencia** | SQL, NoSQL, archivos, sin estado | Documentación de contratos de datos |
| **CI/CD** | GitHub Actions, GitLab CI, Jenkins, sin CI | Integración de auto-actualización |
| **Testing** | pytest, Jest/Vitest, go test, cargo test, JUnit, sin tests | Validación de completitud |

### 0.2 Ficha Técnica de Salida

```yaml
project:
  name: string
  type: web|backend|mobile-native|mobile-hybrid|cli|desktop|monorepo
  primary_language: string
  secondary_languages: [string]
  framework: string
  build_system: string
  package_manager: string
  runtime_version: string
  deployment: docker|bare-metal|serverless|paas|app-store|testflight
  repo_structure: monolith|microservices|monorepo|plugin-system
  ci_provider: github-actions|gitlab-ci|none
  test_framework: string
  existing_docs: path|null
```

### 0.3 Herramientas de Descubrimiento

| Propósito | Python | Node/TS | Go | Rust | JVM | .NET | Dart/Flutter | Swift/Kotlin |
|-----------|--------|---------|----|------|-----|------|--------------|---------------|
| Detectar lenguaje | `pyproject.toml`, `setup.py` | `package.json` | `go.mod` | `Cargo.toml` | `pom.xml`, `build.gradle` | `*.csproj`, `*.sln` | `pubspec.yaml` | `*.xcodeproj`, `build.gradle.kts` |
| Detectar framework | `pipdeptree \| grep fastapi` | `jq .dependencies` | `go list -m` | `cargo metadata` | `mvn dependency:tree` | `dotnet list package` | `flutter pub deps` | `swift package dump-package` |
| Detectar build | `requirements.txt`, `pyproject.toml` | `scripts` en `package.json` | `Makefile`, `Taskfile` | `Cargo.toml [bin]` | `pom.xml` plugins | `*.csproj` tasks | `flutter build`, `dart compile` | `xcodebuild`, `gradlew` |
| Detectar tests | glob `test_*.py` | glob `*.test.*`, `*.spec.*` | glob `*_test.go` | glob `*_test.rs` | glob `*Test.java` | glob `*Test.cs` | glob `*_test.dart` | glob `*Test.swift`, `*Test.kt` |
| Detectar CI | `.github/workflows/` | `.github/workflows/` | `.github/workflows/` | `.github/workflows/` | `.github/workflows/` | `.github/workflows/` | `.github/workflows/` | `.github/workflows/`, `bitrise.yml` |

### 0.4 Estrategia de Particionado para Monorepos y Proyectos Multi-Lenguaje

Cuando el repositorio contiene múltiples paquetes, lenguajes o artefactos desplegables independientes, se aplica una de estas tres estrategias:

#### Estrategia A — Documentación Unificada con Secciones por Paquete
**Aplica cuando** los paquetes comparten modelo de datos, configuración, o protocolo de comunicación (ej: `frontend/` + `backend/` que hablan vía REST/GraphQL).

```
.{tool}/
├── INDEX.md
├── AGENTS.md                            ← Stack global + tabla de paquetes
├── styleguide.md                        ← Convenciones por lenguaje
├── doc-mapping.json                     ← Reglas con prefijo de paquete
└── context/
    ├── 01-architecture.md               ← Diagrama multi-paquete
    ├── 02-configuration.md              ← Config compartida
    ├── 03-data-models.md                ← Modelos compartidos (API types, DTOs)
    ├── 04-packages/                     ← Documentos por paquete
    │   ├── frontend/
    │   │   ├── 01-architecture.md
    │   │   ├── 02-state-management.md
    │   │   ├── 03-component-catalog.md
    │   │   └── 04-routing.md
    │   └── backend/
    │       ├── 01-architecture.md
    │       ├── 02-api-endpoints.md
    │       └── 03-database-schema.md
    ├── 08-api-protocol.md               ← Contrato de comunicación entre paquetes
    ├── 14-deployment.md
    └── 15-testing.md
```

#### Estrategia B — Documentación Independiente por Paquete
**Aplica cuando** los paquetes son débilmente acoplados (ej: monorepo Nx/Turborepo con apps independientes, o microservicios en un mismo repo).

```
packages/
├── web-app/
│   └── .{tool}/          ← Documentación agéntica propia (INDEX, AGENTS, context/)
├── mobile-app/
│   └── .{tool}/
├── shared-lib/
│   └── .{tool}/
└── .{tool}/              ← Documentación global del monorepo (orquestación, CI, convenciones)
    ├── INDEX.md
    ├── AGENTS.md
    └── context/
        ├── 01-monorepo-architecture.md
        ├── 02-shared-contracts.md       ← Interfaces entre paquetes
        └── 03-ci-cd-pipeline.md
```

#### Estrategia C — Bootstrapping Automático
**Aplica cuando** se aplica la metodología por primera vez a un monorepo grande (>10 paquetes).

1. Ejecutar Fase 0 sobre la raíz del repo para generar la ficha técnica multi-paquete
2. Para cada paquete, ejecutar Fase 0 independiente y decidir entre Estrategia A o B según:
   - ¿Comparte modelos de datos con otros paquetes? → A
   - ¿Tiene su propio deploy pipeline? → B
   - ¿El equipo que lo mantiene es distinto? → B
   - ¿Tiene >50 archivos fuente? → B (merece documentación propia)
3. Generar documentación raíz con `INDEX.md` que enlace a los `INDEX.md` de cada paquete

```yaml
# Ficha técnica multi-paquete (salida de Fase 0)
monorepo:
  strategy: unified|independent
  packages:
    - name: web-app
      path: packages/web-app
      language: typescript
      framework: next.js
      doc_strategy: independent
    - name: api
      path: packages/api
      language: python
      framework: fastapi
      doc_strategy: independent
    - name: shared-types
      path: packages/shared-types
      language: typescript
      framework: none
      doc_strategy: unified  # Se documenta dentro de quien lo consume
```

---

## 1. Fase 1 — Análisis Estático

**Objetivo:** Inventariar todos los módulos, mapear dependencias estáticas, extraer contratos públicos (interfaces, tipos, firmas) y detectar patrones arquitectónicos sin ejecutar el código.

### 1.1 Técnicas de Exploración

#### 1.1.1 Análisis Estructural (Tree Scanning)

Recorrer el árbol de archivos y clasificar cada nodo en una taxonomía:

```
Taxonomía de archivos:
  ENTRY_POINT    → main.py, index.ts, main.go, lib.rs, Program.cs, main.dart
  ROUTER         → api/*.py, routes/*.ts, controllers/*.go, handlers/*.rs
  PAGE           → pages/*.tsx, screens/*.tsx, views/*.vue, Activities/*.kt, ViewControllers/*.swift
  COMPONENT      → components/*.tsx, widgets/*.dart, Composables/*.kt, *.swiftui
  HOOK           → hooks/*.ts, composables/*.ts, use*.ts, use*.dart
  STORE          → stores/*.ts, slices/*.ts, reducers/*.ts, providers/*.dart, *Bloc*.dart
  STYLE          → *.css, *.scss, *.module.css, tailwind.config.*, *.styles.ts
  NAVIGATION     → router/*.ts, navigation/*.kt, Navigator.tsx, *Navigator*.swift
  I18N           → locales/*.json, i18n/*.ts, strings.xml, *.lproj/*
  MODEL          → models/*.py, entities/*.ts, domain/*.go, structs/*.rs
  SERVICE        → services/*.py, usecases/*.ts, service/*.go, services/*.rs
  REPOSITORY     → repositories/*.py, dal/*.ts, repository/*.go, repos/*.rs
  MIDDLEWARE     → middleware/*.py, middlewares/*.ts, middleware/*.go
  CONFIG         → config.py, .env*, settings.*, appsettings.json, env.dart
  UTIL           → utils/*.py, helpers/*.ts, util/*.go, utils/*.rs
  TEST           → test_*.py, *.test.ts, *_test.go
  STATIC_ASSET   → *.css, *.html, *.svg, *.png, *.webp, *.lottie
  INFRA          → Dockerfile, docker-compose.yml, k8s/*, terraform/*, fastlane/*
  DOCS           → *.md, docs/*, README
  CI_CD          → .github/workflows/*, .gitlab-ci.yml, Jenkinsfile, bitrise.yml
```

**Reglas de decisión para categorizar:**
1. Si un archivo define una clase abstracta/interface → marcar como `CONTRACT`
2. Si un archivo importa/usa un router framework → `API_LAYER`
3. Si un archivo contiene SQL directo o usa ORM → `DATA_LAYER`
4. Si un archivo exporta una sola función/clase pública → `PUBLIC_API`
5. Si un archivo define un componente UI (React, Vue, SwiftUI, Flutter Widget) → `UI_COMPONENT`
6. Si un archivo gestiona estado global (Redux, Zustand, Pinia, Bloc) → `STATE_MANAGEMENT`

#### 1.1.2 Análisis de Dependencias

Construir el grafo dirigido de imports/dependencias:

```
app/api/torznab.py ──► app/routing/smart_router.py ──► app/providers/registry.py
                           │
                           └──► app/core/categories.py
```

**Propiedades a extraer:**
- **Dependencias entrantes** (quién me usa): `in_degree`
- **Dependencias salientes** (a quién uso): `out_degree`
- **Dependencias circulares**: ciclos en el grafo
- **Módulos huérfanos**: sin dependencias entrantes ni salientes (posible dead code)
- **Módulos críticos**: `in_degree` alto (>5), cambios aquí impactan muchos destinos
- **Acoplamiento aferente/ eferente**: `Ca` / `Ce`
- **Inestabilidad**: `I = Ce / (Ca + Ce)` → módulos con I alto son frágiles

#### 1.1.3 Extracción de Contratos (Interfaces Públicas)

Para cada módulo con `PUBLIC_API`, extraer:

| Atributo | Origen |
|----------|--------|
| Nombre del contrato | Clase, función, interfaz |
| Parámetros de entrada | Type hints, JSDoc, Go types, Rust traits |
| Valor de retorno | Tipo de retorno |
| Excepciones/Errores | Lanza/throws, excepciones documentadas |
| Efectos secundarios | I/O, mutación de estado global, logs |
| Precondiciones | Validaciones de entrada, asserts |
| Postcondiciones | Garantías sobre el estado tras la llamada |

**Herramientas específicas por lenguaje:**

| Lenguaje | Extracción de AST | Tipos | Contratos |
|----------|-------------------|-------|-----------|
| Python | `ast` (stdlib), `ast-grep`, `pyastgrep` | `mypy --strict`, `pyright` | `pydocstyle`, `interrogate` |
| TypeScript | `ts-morph`, `ts-ast-viewer` | `tsc --noEmit`, `typescript-eslint` | `typedoc`, `api-extractor` |
| Go | `go/ast`, `go/parser` | `go vet`, `staticcheck` | `goda`, `guru` |
| Rust | `syn`, `rust-analyzer` | `cargo check`, `clippy` | `cargo doc`, `rustdoc` |
| Java | `javaparser`, `spoon` | `checker-framework`, `nullaway` | `javadoc`, `revapi` |
| C# | `roslyn`, `syntax tree API` | `nullable enable`, `roslyn analyzers` | `xmldoc`, `docfx` |
| Dart | `dart:mirrors` (limitado), `analyzer` package | `dart analyze`, `dart_code_metrics` | `dartdoc` |
| Swift | `swift-syntax`, `sourcekit-lsp` | `swift build --strict-concurrency` | `swift-docc`, `jazzy` |
| Kotlin | `kotlin-compiler-embeddable`, `detekt` | `kotlinc`, `detekt` | `dokka` |

#### 1.1.4 Detección de Patrones Arquitectónicos

Identificar automáticamente patrones por firma de código:

| Patrón | Firma detectable |
|--------|-----------------|
| **MVC** | `models/`, `views/`, `controllers/` + imports desde `controllers` a `models` |
| **MVVM** | `models/`, `viewmodels/`, `views/` + bindings/delegates + Reactividad (RxSwift, LiveData, StateFlow) |
| **Clean Architecture** | `entities/`, `usecases/`, `interfaces/`, `infrastructure/` con regla de dependencia invertida |
| **VIPER** (iOS) | `View`, `Interactor`, `Presenter`, `Entity`, `Router` como protocolos por módulo |
| **BLoC** (Flutter) | `blocs/`, `events/`, `states/` + `BlocProvider` + Streams |
| **Redux/Flux** | `store/`, `actions/`, `reducers/`, `selectors/` + `dispatch()` calls |
| **Hexagonal (Ports & Adapters)** | `ports/` (interfaces) + `adapters/` (implementaciones) + inyección de dependencias |
| **Layered** | imports solo hacia abajo: API → Service → Repository → DB |
| **Event-Driven** | `events/`, `handlers/` + decoradores/annotations de evento + message broker |
| **CQRS** | `commands/` + `queries/` separados, sin solapamiento de imports |
| **Plugin System** | `BasePlugin`/`ABC` + `registry` + discovery dinámico de módulos |
| **Microkernel** | Core mínimo + plugins vía sistema de extensiones |
| **Pipe & Filter** | Encadenamiento de funciones con firma `(input) → output` |
| **Service Locator** | Registry/Singleton con `get()` o `resolve()` que devuelve instancias |
| **Composable Architecture** | `use*()` hooks/composables que encapsulan estado + efectos + ciclo de vida |

### 1.2 Criterios de Salida de la Fase 1

- [ ] Árbol de módulos clasificado al 100% (sin archivos sin categorizar)
- [ ] Grafo de dependencias completo (todos los imports resueltos)
- [ ] Catálogo de contratos públicos (todas las firmas de funciones/clases exportadas)
- [ ] Patrón arquitectónico principal identificado con ≥90% de confianza
- [ ] Módulos huérfanos o dead code identificados y marcados
- [ ] Dependencias circulares detectadas y documentadas

### 1.3 Herramientas Concretas — Fase 1

| Herramienta | Lenguajes | Función |
|-------------|-----------|---------|
| **pydeps** | Python | Grafo de dependencias + visualización |
| **radon** | Python | Complejidad ciclomática + métricas |
| **vulture** | Python | Detección de dead code |
| **pyreverse** | Python | Diagramas UML de clases/paquetes |
| **interrogate** | Python | Cobertura de docstrings |
| **madge** | JS/TS | Grafo de dependencias con detección de circulares |
| **dependency-cruiser** | JS/TS | Reglas de dependencia configurables por patrón |
| **ts-morph** | TS | Manipulación programática de AST |
| **eslint-plugin-import** | JS/TS | Orden y validación de imports |
| **react-docgen** | React | Extrae props, tipos y documentación de componentes |
| **storybook** | React/Vue/Svelte | Catálogo visual de componentes + docs generados |
| **vue-docgen-api** | Vue | Extrae props, slots y eventos de componentes |
| **goda** | Go | Análisis de dependencias entre paquetes |
| **go-callvis** | Go | Visualización de grafo de llamadas |
| **cargo-modules** | Rust | Estructura de módulos + dependencias |
| **cargo-udeps** | Rust | Dependencias no usadas |
| **cargo-geiger** | Rust | Detección de unsafe code |
| **jdeps** | Java | Analizador de dependencias de clases |
| **archunit** | Java | Tests de reglas arquitectónicas |
| **NetArchTest** | C# | Tests de reglas arquitectónicas |
| **dart_code_metrics** | Dart/Flutter | Complejidad, métricas, anti-patrones |
| **swift-ast** | Swift | Extracción de AST y contratos |
| **Graphviz/Dot** | Cualquiera | Renderizado de grafos (salida de cualquier analizador) |
| **Mermaid** | Cualquiera | Diagramas en markdown |
| **tree-sitter** | Cualquiera | AST universal para consultas estructurales |
| **ast-grep** | Cualquiera | Búsqueda estructural de código con patrones |

---

## 2. Fase 2 — Análisis Dinámico

**Objetivo:** Comprender el comportamiento en runtime: flujos de ejecución reales, contratos efectivos (no solo declarados), caminos críticos, tiempos de respuesta, y patrones de error no documentados.

### 2.1 Técnicas de Exploración

#### 2.1.1 Trazado de Ejecución (Instrumentación)

Instrumentar los puntos de entrada (endpoints HTTP, comandos CLI, event handlers) para registrar:

```
[timestamp] [trace_id] [module:function] ENTER {params} → EXIT {return_value|exception} ({duration_ms}ms)
```

**Niveles de traza:**
- **Nivel 1 (Request/Response):** Solo bordes del sistema (API gateway, CLI main)
- **Nivel 2 (Service boundary):** Entrada/salida de cada servicio/use-case
- **Nivel 3 (Full trace):** Cada función, útil para módulos críticos

**Implementación por framework:**
| Framework | Instrumentación |
|-----------|----------------|
| FastAPI | Middleware de tracing con `trace_id` en headers |
| Express | `app.use(tracingMiddleware)` |
| Next.js | Middleware en `middleware.ts` + `instrumentation.ts` |
| Spring Boot | Micrometer + Sleuth |
| .NET | `System.Diagnostics.Activity` |
| Go net/http | Middleware de handler |
| CLI | Decorador/context manager en `main()` |
| React Native | `react-native-performance`, Flipper plugin |
| Flutter | `Sentry`, `Firebase Performance`, `flutter --trace-startup` |
| iOS (Swift) | `os_log`, `swift-log`, Instruments |
| Android (Kotlin) | `Timber`, `android.os.Trace`, Android Profiler |

#### 2.1.2 Análisis de Logs en Runtime

Extraer patrones de logs para identificar caminos de error no documentados:

```regex
# Patrones de búsqueda
(ERROR|CRITICAL|FATAL|panic|fatal)  → caminos de fallo
(WARNING|WARN)                       → degradación parcial
(INFO.*start|INFO.*init)             → ciclo de vida
(DEBUG.*retry|DEBUG.*fallback)       → resiliencia
```

#### 2.1.3 Inspección de API (si es web/backend)

- **OpenAPI/Swagger:** Extraer la especificación generada automáticamente (`/openapi.json`, `/swagger.json`)
- **Validar contratos reales vs documentados:** Comparar parámetros declarados en código vs los extraídos en Fase 1
- **Probar endpoints con fuzzing suave:** Enviar payloads válidos, inválidos, límite para observar comportamiento real

#### 2.1.4 Pruebas Automatizadas como Especificación Ejecutable

Las pruebas existentes son documentación ejecutable. Analizarlas para:

- **Cobertura de caminos felices:** Cada endpoint/comando tiene al menos un test de éxito
- **Cobertura de caminos de error:** Fallos de red, timeouts, datos inválidos
- **Cobertura de edge cases:** Valores límite, nulos, vacíos, Unicode, overflow
- **Contratos implícitos en asserts:** Lo que los tests esperan define el contrato real

**Mapeo test → módulo → documento:**
```
tests/test_provider_epublibre.py → app/providers/books/epublibre.py → context/06-provider-strategies/epublibre.md
```

#### 2.1.5 Revisión de Código Asistida (Code Review Automatizada)

Ejecutar linters y analizadores estáticos avanzados para detectar:

| Categoría | Herramientas | Qué extraer para la documentación |
|-----------|-------------|-----------------------------------|
| Complejidad | `radon`, `eslint complexity`, `gocyclo` | Funciones que requieren documentación detallada |
| Anti-patrones | `bandit` (seguridad), `gosec`, `clippy::complexity` | Vulnerabilidades y malas prácticas como "NO HACER" |
| Deuda técnica | `sonarqube`, `codeclimate`, `debtcollector` | Issues conocidos para `context/{n}-known-issues.md` |
| Duplicación | `jscpd`, `copy-paste-detector` | Código repetido que merece un documento de patrón compartido |
| Convenciones | `eslint`, `pylint`, `gofmt`, `rustfmt` | Reglas de estilo a documentar en `styleguide.md` |

### 2.2 Criterios de Salida de la Fase 2

- [ ] Al menos 1 traza completa del flujo principal (happy path) por endpoint/comando
- [ ] Todos los endpoints/comandos listados con sus parámetros observados en runtime
- [ ] Caminos de error documentados (extraídos de logs, tests y código)
- [ ] Cobertura de test mapeada a módulos (qué módulos tienen test, cuáles no)
- [ ] Lista de anti-patrones detectados (para sección "Qué NO hacer" de AGENTS.md)
- [ ] OpenAPI/Swagger spec extraída si aplica

### 2.3 Herramientas Concretas — Fase 2

| Herramienta | Propósito | Lenguajes |
|-------------|-----------|-----------|
| **OpenTelemetry** | Trazado distribuido estándar | Todos |
| **FastAPI /openapi.json** | Spec automática | Python |
| **Swagger UI** | Exploración visual de API | Cualquiera con OpenAPI |
| **mitmproxy** | Proxy de interceptación HTTP | Cualquiera (tráfico HTTP) |
| **pytest --durations=10** | Identificar tests lentos = código complejo | Python |
| **cProfile / py-spy** | Perfilado de CPU | Python |
| **flamegraph-rs** | Visualización de llamadas | Rust |
| **pprof** | Perfilado de CPU/Mem | Go |
| **clinic.js** | Perfilado de Node.js | Node.js |
| **lighthouse** | Auditoría de rendimiento web | Web/SPA |
| **react-devtools** | Inspección de árbol de componentes | React |
| **flutter devtools** | Perfilado + inspector de widgets | Flutter |
| **logrus/zap/slog** | Structured logging | Go |
| **structlog / loguru** | Structured logging | Python |
| **pino / winston** | Structured logging | Node.js |
| **bandit** | Análisis de seguridad | Python |
| **gosec** | Análisis de seguridad | Go |
| **cargo-audit** | Análisis de seguridad | Rust |
| **npm audit** | Análisis de seguridad | Node.js |
| **trivy** | Escaneo de vulnerabilidades | Contenedores + dependencias |
| **SonarQube / SonarCloud** | Plataforma de calidad | Todos (via CI) |
| **CodeClimate** | Mantenibilidad + cobertura | Todos (via CI) |

---

## 3. Fase 3 — Síntesis y Generación de Documentación Agéntica

**Objetivo:** Producir la estructura `.{tool}/` (`.gemini/`, `.kilo/`, etc.) completa con todos los documentos agénticos, usando los datos recolectados en las fases anteriores.

### 3.1 Estructura de Documentación Estándar

```
.{tool}/
├── INDEX.md                         ← Mapa de casos de uso → documentos
├── AGENTS.md                        ← Visión general para agentes (stack, estructura, convenciones, anti-patrones)
├── styleguide.md                    ← Convenciones de código
└── context/
    ├── 01-architecture.md           ← Arquitectura global y flujo de datos
    ├── 02-configuration.md          ← Variables de configuración
    ├── 03-data-models.md            ← Modelos de datos compartidos
    ├── 04-{infra-layer}.md          ← Capa de infraestructura (HTTP client, DB, cache)
    ├── 05-{core-abstraction}.md     ← Abstracción central (BaseProvider, Plugin, etc.)
    ├── 06-{component}-strategies/   ← Documentos por instancia concreta
    │   ├── component-a.md
    │   ├── component-b.md
    │   └── ...
    ├── 07-{router-orchestrator}.md  ← Orquestador / Router
    ├── 08-{protocol-format}.md      ← Protocolo o formato de intercambio
    ├── 09-{mapping}.md              ← Mapeos y transformaciones
    ├── 10-{cross-cutting-a}.md      ← Servicio transversal A
    ├── 11-{cross-cutting-b}.md      ← Servicio transversal B
    ├── 12-{utility}.md              ← Utilidades destacadas
    ├── 13-api-endpoints.md          ← Endpoints documentados
    ├── 14-deployment.md             ← Guía de despliegue
    ├── 15-testing.md                ← Guía de testing
    ├── 16-known-issues.md           ← Bugs y problemas conocidos
    └── 17-adding-{component}.md     ← Guía para añadir nuevos componentes
```

### 3.2 Reglas de Decisión: Qué Documentos Crear

#### 3.2.1 Documentos Obligatorios (siempre se generan)

| Documento | Condición |
|-----------|-----------|
| `INDEX.md` | Siempre |
| `AGENTS.md` | Siempre |
| `01-architecture.md` | Siempre |
| `02-configuration.md` | Si hay `.env`, `config.*`, `settings.*` o similar |
| `03-data-models.md` | Si hay `>3` tipos/modelos/structs compartidos entre módulos |
| `15-testing.md` | Si hay tests |

#### 3.2.2 Documentos Condicionales (dependen del tipo de aplicación)

| Documento | Condición |
|-----------|-----------|
| `04-http-client.md` | Si hay capa de cliente HTTP propia |
| `04-database-layer.md` | Si hay capa de acceso a datos (ORM, migrations, queries) |
| `04-database-schema.md` | Si la BD tiene ≥5 entidades/tablas con relaciones no triviales |
| `05-providers-base.md` | Si hay sistema de plugins/providers (ABC + Registry) |
| `05-state-management.md` | Si hay store global (Redux, Zustand, Pinia, Bloc, Provider) |
| `05-component-catalog.md` | Si hay ≥10 componentes UI reutilizables (frontend SPA / móvil) |
| `06-strategies/` | Si hay >1 implementación concreta de la abstracción central |
| `06-screens/` | Si hay ≥5 pantallas/vistas/rutas en frontend o móvil |
| `07-smart-router.md` | Si hay lógica de routing no trivial |
| `07-navigation.md` | Si hay sistema de navegación multi-nivel (móvil: stacks, tabs, drawers) |
| `08-protocol.md` | Si hay protocolo de serialización (REST, gRPC, GraphQL, etc.) |
| `09-i18n.md` | Si hay ≥2 idiomas o sistema de localización |
| `10-domain-resolver.md` | Si hay resolución dinámica de recursos |
| `11-cache.md` | Si hay sistema de caché |
| `11-offline-support.md` | Si la app móvil funciona offline (SQLite local, WatermelonDB, etc.) |
| `12-{utility}.md` | Si hay utilidad compleja (>100 líneas, usada por >3 módulos) |
| `13-api-endpoints.md` | Si es web/backend (tiene endpoints) |
| `14-deployment.md` | Si hay Docker/CI/CD/app store deployment |
| `14-store-deployment.md` | Si hay despliegue en App Store / Google Play (móvil) |
| `15-testing.md` | Si hay tests |
| `16-known-issues.md` | Si se detectaron anti-patrones o hay issues abiertos en el tracker |
| `17-adding-{component}.md` | Si el sistema es extensible (plugins/providers/adapters) |

#### 3.2.3 Criterio de Fusión/Separación

| Regla | Acción |
|-------|--------|
| Dos módulos tienen `acoplamiento > 0.8` | Fusionar en un solo documento |
| Un documento supera las 300 líneas | Evaluar si se puede partir en sub-temas |
| Un módulo tiene `in_degree = 0` y `out_degree = 0` | No generar documento (posible dead code) |
| Un módulo tiene `out_degree > 10` | Documento prioritario, detallar todas las dependencias |

### 3.3 Plantillas de Documento

#### 3.3.1 Plantilla: `INDEX.md`

```markdown
# {PROJECT_NAME} — Índice de Documentación Agéntica

> **Para agentes de IA que trabajan en este proyecto.**
> Usa esta guía para determinar qué documentación consultar según tu tarea.

## Mapa de Casos de Uso → Documentación
[Generado a partir de la taxonomía de módulos y sus relaciones]

### 🆕 "Quiero crear un nuevo {component_type}"
1. `context/{n}-{abstraction}.md` — Interfaz, contrato, ciclo de vida
2. `context/{m}-adding-{component}.md` — Guía paso a paso
3. `context/{strategy-dir}/{ejemplo}.md` — Ejemplo de referencia
...

## Índice Completo de Documentos
[Tabla numerada de todos los documentos en context/]
```

#### 3.3.2 Plantilla: `AGENTS.md`

```markdown
# {PROJECT_NAME} — Guía para Agentes

## Visión General
[Propósito del proyecto en ≤3 frases + estadísticas clave]

## Stack Tecnológico
[Tabla: componente → tecnología → versión]

## Cómo Arrancar
[Comandos de desarrollo local + con contenedores]

## Estructura de Módulos
[Árbol de directorios comentado]

## Documentación Agéntica Disponible
[Tabla numerada de documentos con descripción de 1 línea]

## Convenciones Importantes
[Extraídas de Fase 1 (contratos) + Fase 2 (linting)]

## Qué NO Hacer
[Anti-patrones detectados en Fase 2]

## Endpoints Principales (si aplica)
[Tabla: método + ruta + descripción]

## Para Dónde Ir Según la Tarea
[Tabla: tarea → documento principal → documentos secundarios]
```

#### 3.3.3 Plantilla: documento `context/{n}-{topic}.md`

```markdown
# {NN} — {Título descriptivo}

## Propósito
[Párrafo: qué documenta, cuándo consultarlo]

## {Sección principal 1}
[Contenido extraído de análisis estático: contratos, firmas, dependencias]

## {Sección principal 2}
[Contenido extraído de análisis dinámico: flujos, trazas, comportamiento real]

## Archivos Relevantes
[Tabla: archivo → rol]
```

#### 3.3.4 Plantilla: documento de estrategia `context/{dir}/{component}.md`

```markdown
# Estrategia: {ComponentName}

## Propósito
[Qué hace este componente concreto]

## URLs / Recursos (si aplica)

## Requisitos Especiales
[Dependencias específicas, configuraciones, limitaciones]

## Constructor / Inicialización
[Fragmento de código clave + explicación]

## Estrategia de {operación_principal}
### 1. {Paso}
[Código + explicación]
### 2. {Paso}
...

## Manejo de Errores
[Cómo reacciona ante fallos]

## Diferencias con Otros {ComponentType}
[Tabla comparativa si hay >3 instancias]

## Trampas
[Cosas que pueden salir mal, edge cases]

## Archivos
- `ruta/al/archivo.py`
- `tests/test_archivo.py`
```

### 3.4 Criterios de Salida de la Fase 3

- [ ] `INDEX.md` generado con ≥1 mapa de caso de uso por cada documento context/
- [ ] `AGENTS.md` generado con todas las secciones obligatorias
- [ ] `styleguide.md` generado con convenciones extraídas del linting
- [ ] 100% de módulos con `PUBLIC_API` tienen al menos 1 documento asociado
- [ ] 100% de implementaciones concretas de una abstracción tienen documento de estrategia
- [ ] Cada documento referencia los archivos fuente que documenta
- [ ] Cada archivo fuente está referenciado en al menos 1 documento (o justificado como omitido)

### 3.5 Scripts de Generación Automática de Borradores

La Fase 3 produce documentación a partir de los datos crudos de Fase 1 y Fase 2. Para proyectos con >30 archivos fuente, es impracticable escribir cada documento manualmente. Los siguientes scripts generan borradores que el agente (o humano) refina posteriormente.

#### 3.5.1 Generador de `AGENTS.md` desde la Ficha Técnica

```python
#!/usr/bin/env python3
# scripts/gen_agents_md.py — Genera borrador de AGENTS.md desde Fase 0

import json, sys
from pathlib import Path

TEMPLATE = """# {name} — Guía para Agentes

## Visión General
{description}

**Estadísticas:** {stats}

## Stack Tecnológico
| Componente | Tecnología | Versión |
|------------|-----------|---------|
{stack_rows}

## Cómo Arrancar
{setup_commands}

## Estructura de Módulos
```
{tree}
```

{extra_sections}

## Convenciones Importantes
{conventions}

## Qué NO Hacer
{anti_patterns}

## Para Dónde Ir Según la Tarea
| Tarea | Documento principal |
|-------|-------------------|
{task_map}
"""

def generate(project_info: dict, module_tree: dict, conventions: dict) -> str:
    return TEMPLATE.format(
        name=project_info["name"],
        description=infer_description(module_tree),
        stats=format_stats(module_tree),
        stack_rows=format_stack_table(project_info),
        setup_commands=detect_setup_commands(project_info),
        tree=render_module_tree(module_tree),
        extra_sections=generate_extra_sections(project_info, module_tree),
        conventions=format_conventions(conventions),
        anti_patterns=format_anti_patterns(conventions),
        task_map=infer_task_document_map(module_tree),
    )
```

#### 3.5.2 Generador de `INDEX.md` desde el Grafo de Módulos

```python
#!/usr/bin/env python3
# scripts/gen_index_md.py — Genera INDEX.md desde taxonomía de módulos

def generate_index(doc_catalog: list[dict], module_graph: dict) -> str:
    """
    Genera el INDEX.md con mapa de casos de uso → documentos.

    doc_catalog: [{"id": "01", "file": "context/01-architecture.md", "topics": [...]}]
    module_graph: grafo de dependencias de Fase 1
    """
    use_cases = infer_use_cases(doc_catalog, module_graph)
    
    sections = ["# {name} — Índice de Documentación Agéntica\n"]
    sections.append("> **Para agentes de IA que trabajan en este proyecto.**\n")
    sections.append("## Mapa de Casos de Uso → Documentación\n")

    for uc in use_cases:
        sections.append(f"### {uc['emoji']} {uc['title']}")
        for i, doc in enumerate(uc['docs'], 1):
            sections.append(f"{i}. `{doc['path']}` — {doc['description']}")
        sections.append("")

    sections.append("## Índice Completo de Documentos\n")
    sections.append("| # | Documento | Descripción |")
    sections.append("|---|-----------|-------------|")
    for doc in sorted(doc_catalog, key=lambda d: d.get("id", "99")):
        sections.append(f"| **{doc['id']}** | `{doc['file']}` | {doc['description']} |")

    return "\n".join(sections)


def infer_use_cases(doc_catalog: list[dict], module_graph: dict) -> list[dict]:
    """
    Genera automáticamente casos de uso a partir de:
    - Tipo de aplicación (web → endpoints; móvil → pantallas; CLI → comandos)
    - Módulos con PUBLIC_API alta
    - Dependencias entre capas
    """
    use_cases = []
    
    # Caso 1: Si hay sistema extensible (ABC + Registry) → "Crear nuevo X"
    if has_plugin_system(module_graph):
        use_cases.append({
            "emoji": "🆕",
            "title": f'"Quiero crear un nuevo {get_component_name(module_graph)}"',
            "docs": find_docs_for_task(doc_catalog, ["abstraction", "adding", "example"])
        })
    
    # Caso 2: Si hay módulos con estrategias → "Depurar un X específico"
    if has_strategies(doc_catalog):
        use_cases.append({
            "emoji": "🐛",
            "title": '"Un componente específico está fallando"',
            "docs": find_docs_for_task(doc_catalog, ["strategy", "known-issues"])
        })
    
    # Caso 3: Si hay router/orquestador → "Entender cómo se rutean las peticiones"
    if has_router(module_graph):
        use_cases.append({
            "emoji": "🔍",
            "title": '"Quiero entender cómo se rutean las peticiones"',
            "docs": find_docs_for_task(doc_catalog, ["router", "architecture"])
        })
    
    # ... más casos inferidos automáticamente
    return use_cases
```

#### 3.5.3 Generador de Documentos de Estrategia desde Contratos

```python
#!/usr/bin/env python3
# scripts/gen_strategy_doc.py — Genera documento de estrategia para una implementación concreta

import ast, inspect
from pathlib import Path

STRATEGY_TEMPLATE = """# Estrategia: {class_name}

## Provider ID: `{instance_id}`

## Propósito
{auto_description}

## URLs / Recursos (si aplica)
{urls_section}

## Requisitos Especiales
{special_requirements}

## Constructor / Inicialización
```{language}
{constructor_code}
```

## Estrategia de {main_operation}
{operation_steps}

## Manejo de Errores
{error_handling}

## Diferencias con Otros {component_type}
{diff_table}

## Trampas
{pitfalls}

## Archivos
- `{source_file}`
- `{test_file}`
"""

def generate_strategy_doc(
    class_ast: ast.ClassDef,
    source_file: str,
    base_class_name: str,
    siblings: list[str],  # Otras implementaciones para la tabla comparativa
    contracts: dict,       # Contratos extraídos en Fase 1
) -> str:
    """
    Genera un borrador de documento de estrategia a partir de:
    - AST de la clase concreta
    - Contratos de la clase base (Fase 1)
    - Implementaciones hermanas para tabla comparativa
    """
    class_name = class_ast.name
    
    # Extraer métodos públicos y sus firmas
    methods = extract_public_methods(class_ast)
    
    # Inferir descripción a partir de docstring y nombre
    description = infer_description_from_code(class_ast)
    
    # Extraer fragmentos de código del constructor
    constructor = extract_constructor_code(class_ast, source_file)
    
    # Generar pasos de la operación principal a partir de AST
    main_op = find_main_operation(methods)
    operation_steps = extract_operation_flow(class_ast, main_op, source_file)
    
    # Detectar patrones de manejo de errores
    error_handling = detect_error_patterns(class_ast)
    
    # Construir tabla comparativa con siblings
    diff_table = build_diff_table(class_name, siblings, contracts)
    
    # Detectar posibles trampas (código con comentarios TODO/FIXME/HACK)
    pitfalls = detect_pitfalls(source_file)
    
    # Buscar archivo de test correspondiente
    test_file = find_test_file(source_file)
    
    return STRATEGY_TEMPLATE.format(
        class_name=class_name,
        instance_id=infer_instance_id(class_ast),
        auto_description=description,
        urls_section=extract_urls(class_ast) or "No aplica.",
        special_requirements=detect_special_requirements(class_ast),
        language=detect_language(source_file),
        constructor_code=constructor,
        main_operation=main_op,
        operation_steps=operation_steps,
        error_handling=error_handling,
        component_type=base_class_name,
        diff_table=diff_table,
        pitfalls=pitfalls or "No se detectaron trampas obvias.",
        source_file=source_file,
        test_file=test_file or f"tests/test_{Path(source_file).stem}.py",
    )
```

#### 3.5.4 Generador de Documentos de Pantalla/Vista (Frontend/Móvil)

```python
#!/usr/bin/env python3
# scripts/gen_screen_doc.py — Genera documento para una pantalla/vista en frontend o móvil

SCREEN_TEMPLATE = """# Pantalla: {screen_name}

## Ruta / Deep Link
`{route_path}`

## Propósito
{auto_description}

## Parámetros de Navegación
| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
{params_table}

## Estado Local
{local_state}

## Estado Global Consumido
{global_state}

## Acciones del Usuario
{user_actions}

## Llamadas a API
{api_calls}

## Navegación Saliente
| Destino | Condición |
|---------|-----------|
{outgoing_nav}

## Componentes Hijos
{child_components}

## Manejo de Errores
{error_handling}

## Estados de Carga
{loading_states}

## Archivos
- `{source_file}`
"""
```

#### 3.5.5 Orquestador de Generación (Script Principal)

```python
#!/usr/bin/env python3
# scripts/generate_all_docs.py — Orquesta la generación completa de Fase 3

"""
Uso:
  python scripts/generate_all_docs.py \\
    --project-info phase0_output.json \\
    --modules phase1_modules.json \\
    --contracts phase1_contracts.json \\
    --traces phase2_traces.json \\
    --out .gemini/
"""

import json, sys
from pathlib import Path
from gen_agents_md import generate as gen_agents
from gen_index_md import generate_index
from gen_strategy_doc import generate_strategy_doc
from gen_screen_doc import generate_screen_doc

def main():
    # 1. Cargar outputs de fases anteriores
    project_info = json.loads(Path("phase0_output.json").read_text())
    modules = json.loads(Path("phase1_modules.json").read_text())
    contracts = json.loads(Path("phase1_contracts.json").read_text())
    traces = json.loads(Path("phase2_traces.json").read_text())

    out_dir = Path(".gemini")
    out_dir.mkdir(exist_ok=True)
    (out_dir / "context").mkdir(exist_ok=True)

    # 2. Generar AGENTS.md
    agents_md = gen_agents(project_info, modules, contracts)
    (out_dir / "AGENTS.md").write_text(agents_md)
    print("✓ AGENTS.md generated")

    # 3. Generar styleguide.md desde convenciones de linting
    styleguide = gen_styleguide(contracts.get("conventions", {}))
    (out_dir / "styleguide.md").write_text(styleguide)
    print("✓ styleguide.md generated")

    # 4. Generar documentos context/ por cada módulo con PUBLIC_API
    doc_catalog = []
    for module in modules.get("public_api_modules", []):
        doc = gen_context_doc(module, contracts, traces)
        doc_file = out_dir / "context" / doc["filename"]
        doc_file.write_text(doc["content"])
        doc_catalog.append(doc)
        print(f"✓ {doc['filename']} generated")

    # 5. Generar documentos de estrategia por cada implementación concreta
    base_classes = find_base_classes(modules)
    for base_name, implementations in base_classes.items():
        if len(implementations) > 1:
            strategies_dir = out_dir / "context" / f"06-{base_name.lower()}-strategies"
            strategies_dir.mkdir(exist_ok=True)
            for impl in implementations:
                doc = generate_strategy_doc(
                    impl["ast"], impl["file"], base_name,
                    siblings=[i["name"] for i in implementations]
                )
                doc_file = strategies_dir / f"{impl['name'].lower()}.md"
                doc_file.write_text(doc)
                doc_catalog.append({"id": "06", "file": str(doc_file), "description": f"Estrategia de {impl['name']}"})
                print(f"✓ {doc_file} generated")

    # 6. Generar documentos de pantalla (si es frontend/móvil)
    screens = modules.get("screens", [])
    if len(screens) >= 5:
        screens_dir = out_dir / "context" / "06-screens"
        screens_dir.mkdir(exist_ok=True)
        for screen in screens:
            doc = generate_screen_doc(screen)
            doc_file = screens_dir / f"{screen['name'].lower()}.md"
            doc_file.write_text(doc)
            print(f"✓ screens/{screen['name'].lower()}.md generated")

    # 7. Generar INDEX.md al final (necesita el catálogo completo)
    index_md = generate_index(doc_catalog, modules.get("dependency_graph", {}))
    (out_dir / "INDEX.md").write_text(index_md)
    print("✓ INDEX.md generated")

    # 8. Estadísticas
    total_docs = len(list(out_dir.rglob("*.md")))
    print(f"\n📊 Generación completada: {total_docs} documentos")
    print(f"   Revisa {out_dir}/ y refina los borradores generados.")

if __name__ == "__main__":
    main()
```

#### 3.5.6 Plantilla de Documento para Catálogo de Componentes UI

```markdown
# Catálogo de Componentes UI

## Propósito
Inventario de todos los componentes reutilizables, sus props, estados y variantes visuales.

## Componentes Atómicos
| Componente | Props | Estados | Archivo |
|------------|-------|---------|---------|
| `Button` | `variant`, `size`, `disabled`, `loading` | default, hover, active, disabled, loading | `components/ui/Button.tsx` |
| ... | | | |

## Componentes Compuestos
| Componente | Compuesto de | Props | Archivo |
|------------|-------------|-------|---------|
| `SearchBar` | `Input` + `Button` + `Dropdown` | ... | `components/search/SearchBar.tsx` |
| ... | | | |

## Sistema de Diseño
[Referencia a tokens, temas, variables CSS/Tailwind]
```


---

## 4. Fase 4 — Validación de Completitud y Precisión

**Objetivo:** Verificar objetivamente que la documentación es completa, precisa y útil para agentes de IA.

### 4.1 Criterios de Completitud Estructural

| Métrica | Objetivo | Método de verificación |
|---------|----------|------------------------|
| **Cobertura de módulos** | `|módulos documentados| / |módulos totales| ≥ 0.95` | Script que cruza documentos con archivos fuente |
| **Cobertura de contratos** | `|APIs públicas documentadas| / |APIs públicas totales| ≥ 0.95` | AST extractor vs búsqueda en documentos |
| **Cobertura de flujos** | `|flujos trazados| ≥ |endpoints/commands| × 2` (happy + error) | Conteo manual/asistido de trazas |
| **Cobertura de dependencias** | `|dependencias documentadas| / |dependencias reales| ≥ 0.90` | Comparar grafo extraído vs referenciado |
| **Cobertura de estrategias** | `|implementaciones con estrategia| / |implementaciones totales| = 1.0` | 1 doc por cada clase concreta |

### 4.2 Criterios de Precisión

| Métrica | Objetivo | Método de verificación |
|---------|----------|------------------------|
| **Referencias rotas** | `0` referencias a archivos inexistentes | Script que resuelve cada path mencionado |
| **Firmas incorrectas** | `0` discrepancias firma declarada vs documentada | Comparar AST vs documentación |
| **URLs obsoletas** | `0` enlaces de doc que no coinciden con código actual | Extraer URLs de docs y validar contra código |
| **Dependencias invertidas** | `0` dependencias documentadas en dirección contraria | Validar dirección del grafo |
| **Versión de código** | Documentación registra el commit SHA del que deriva | Campo `derived_from_commit` en cada documento |

### 4.3 Criterios de Usabilidad Agéntica

| Métrica | Objetivo | Método de verificación |
|---------|----------|------------------------|
| **INDEX navegable** | Cada caso de uso listado lleva a ≥1 documento correcto | Test manual: simular 10 tareas de agente y verificar que INDEX guía correctamente |
| **Documentos autocontenidos** | Cada documento incluye referencias a archivos fuente y docs relacionados | Grep por patrones de referencia |
| **Anti-patrones documentados** | Sección "Qué NO hacer" cubre ≥80% de anti-patrones detectados | Comparar salida de linters vs contenido AGENTS.md |
| **Fragmentos de código actualizados** | Extractos de código ≤30 días de antigüedad (o marcados con versión) | Campo `code_snapshot_sha` por fragmento |

### 4.4 Script de Validación Automatizada

```python
# validate_docs.py — Ejecutar en CI para validar documentación agéntica

def validate():
    results = []
    
    # 1. Verificar que todos los archivos fuente están referenciados
    source_files = glob("app/**/*.py")
    doc_refs = extract_file_references(".gemini/")
    undocumented = source_files - doc_refs
    if undocumented:
        results.append(("WARN", f"Archivos no documentados: {undocumented}"))
    
    # 2. Verificar referencias rotas
    broken = [ref for ref in doc_refs if not Path(ref).exists()]
    if broken:
        results.append(("ERROR", f"Referencias rotas en docs: {broken}"))
    
    # 3. Verificar cobertura de estrategias
    providers = glob("app/providers/**/*.py")
    strategies = glob(".gemini/context/06-provider-strategies/*.md")
    provider_names = {extract_provider_id(p) for p in providers}
    strategy_names = {extract_strategy_name(s) for s in strategies}
    missing = provider_names - strategy_names
    if missing:
        results.append(("ERROR", f"Providers sin estrategia documentada: {missing}"))
    
    # 4. Verificar que cada endpoint tiene documentación
    # ...
    
    return results
```

### 4.5 Criterios de Salida de la Fase 4

- [ ] Todas las métricas de completitud ≥ objetivo definido
- [ ] 0 errores de referencias rotas
- [ ] 0 discrepancias de firma críticas
- [ ] Script de validación integrado en CI (opcional `--strict`)
- [ ] Documento de validación generado con hallazgos y recomendaciones

---

## 5. Fase 5 — Mantenimiento Autónomo (Auto-Actualización)

**Objetivo:** Garantizar que la documentación agéntica se mantiene sincronizada con el código fuente de forma automática y obligatoria tras cualquier cambio.

### 5.1 Ciclo de Detección → Clasificación → Actualización → Verificación

```
┌──────────────────────────────────────────────────────────────────┐
│                     GIT EVENT (push/merge)                        │
└─────────────────────────────┬────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  STEP 1: DETECCIÓN DE CAMBIOS                                    │
│  git diff --name-only HEAD~1 → lista de archivos modificados     │
└─────────────────────────────┬────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  STEP 2: CLASIFICACIÓN DEL CAMBIO                                │
│  Reglas que mapean patrones de archivo → documentos afectados    │
│                                                                  │
│  app/providers/books/*.py → context/06-provider-strategies/*.md  │
│  app/core/models.py       → context/03-data-models.md            │
│  app/api/*.py              → context/13-api-endpoints.md         │
│  config.py                 → context/02-configuration.md         │
│  Dockerfile                → context/14-deployment.md             │
│  tests/*                   → context/15-testing.md               │
│  app/scraping/*            → context/04-{infra}.md               │
│  *.md (doc)                → (no dispara actualización)          │
└─────────────────────────────┬────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  STEP 3: DISPARO DEL AGENTE DE ACTUALIZACIÓN                     │
│  CI ejecuta: kilo run "Actualiza la documentación agéntica..."   │
│  proporcionando: diff clasificado + docs afectados               │
└─────────────────────────────┬────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  STEP 4: VERIFICACIÓN POST-ACTUALIZACIÓN                         │
│  Ejecutar script validate_docs.py --strict                       │
│  Si falla → bloquear merge/PR                                    │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 Mecanismo de Detección

#### 5.2.1 Git Hook Local (`post-commit` / `post-merge`)

```bash
#!/bin/bash
# .githooks/post-commit → instalado vía .pre-commit-config.yaml o manual

CHANGED_FILES=$(git diff --name-only HEAD~1 2>/dev/null || git diff --name-only --cached)
SOURCE_FILES=$(echo "$CHANGED_FILES" | grep -E '\.(py|ts|js|go|rs|java|cs|rb|php)$' || true)

if [ -n "$SOURCE_FILES" ]; then
    echo "⚠️  Código modificado. La documentación agéntica debe actualizarse."
    echo "   Archivos: $SOURCE_FILES"
    echo "   Ejecuta: ./scripts/update-agentic-docs.sh"
fi
```

#### 5.2.2 CI Step Obligatorio (GitHub Actions)

```yaml
# .github/workflows/agentic-docs-check.yml
name: Agentic Docs Sync Check

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  check-docs-sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 2  # Necesario para git diff HEAD~1
      
      - name: Detect changed source files
        id: changes
        run: |
          CHANGED=$(git diff --name-only HEAD~1 | grep -E '\.(py|ts|js|go|rs|java|cs)$' || true)
          echo "files=$CHANGED" >> $GITHUB_OUTPUT
      
      - name: Classify affected docs
        if: steps.changes.outputs.files != ''
        id: classify
        run: |
          python scripts/classify_changes.py --files "${{ steps.changes.outputs.files }}"
      
      - name: Validate doc sync
        if: steps.changes.outputs.files != ''
        run: |
          python scripts/validate_docs.py --strict --check-sync
          # Si hay cambios de código sin cambios de doc → WARNING
          # Si es push a main → ERROR (bloquea)
      
      - name: Trigger doc update (main only)
        if: github.ref == 'refs/heads/main' && steps.changes.outputs.files != ''
        run: |
          ./scripts/update-agentic-docs.sh
          python scripts/validate_docs.py --strict
```

### 5.3 Tabla de Reglas de Clasificación (Cambio → Documento)

La tabla de clasificación se almacena como `.{tool}/doc-mapping.json` y es la fuente de verdad para el mapeo automático.

```json
{
  "version": "1.0",
  "project": "webtranslatorr",
  "rules": [
    {
      "id": "R001",
      "pattern": "app/providers/books/(.*)\\.py",
      "capture": "provider_name",
      "affected_docs": [
        "context/06-provider-strategies/{provider_name}.md",
        "context/05-providers-base.md"
      ],
      "severity": "high",
      "description": "Cambio en un provider de libros"
    },
    {
      "id": "R002",
      "pattern": "app/core/models\\.py",
      "affected_docs": [
        "context/03-data-models.md",
        "context/08-torznab-protocol.md"
      ],
      "severity": "critical",
      "description": "Cambio en modelos de datos compartidos"
    },
    {
      "id": "R003",
      "pattern": "app/api/.*\\.py",
      "affected_docs": [
        "context/13-api-endpoints.md",
        "context/01-architecture.md"
      ],
      "severity": "high",
      "description": "Cambio en endpoints de la API"
    },
    {
      "id": "R004",
      "pattern": "config\\.py",
      "affected_docs": [
        "context/02-configuration.md",
        "context/14-deployment.md"
      ],
      "severity": "medium",
      "description": "Cambio en configuración"
    },
    {
      "id": "R005",
      "pattern": "app/scraping/.*\\.py",
      "affected_docs": [
        "context/04-http-client.md"
      ],
      "severity": "medium",
      "description": "Cambio en capa de scraping/HTTP"
    },
    {
      "id": "R006",
      "pattern": "app/torznab/.*\\.py",
      "affected_docs": [
        "context/08-torznab-protocol.md",
        "context/09-categories.md"
      ],
      "severity": "high",
      "description": "Cambio en capa de protocolo Torznab"
    },
    {
      "id": "R007",
      "pattern": "Dockerfile|docker-compose\\.yml",
      "affected_docs": [
        "context/14-deployment.md"
      ],
      "severity": "medium",
      "description": "Cambio en configuración de despliegue"
    },
    {
      "id": "R008",
      "pattern": "tests/.*\\.py",
      "affected_docs": [
        "context/15-testing.md"
      ],
      "severity": "low",
      "description": "Cambio en tests (actualizar patrones de testing si es estructural)"
    },
    {
      "id": "R009",
      "pattern": "app/services/domain_.*\\.py",
      "affected_docs": [
        "context/10-domain-resolver.md"
      ],
      "severity": "medium",
      "description": "Cambio en resolución de dominios"
    },
    {
      "id": "R010",
      "pattern": "app/services/cache\\.py",
      "affected_docs": [
        "context/11-cache.md"
      ],
      "severity": "low",
      "description": "Cambio en sistema de caché"
    },
    {
      "id": "R011",
      "pattern": "app/routing/.*\\.py",
      "affected_docs": [
        "context/07-smart-router.md",
        "context/01-architecture.md"
      ],
      "severity": "high",
      "description": "Cambio en lógica de routing"
    },
    {
      "id": "R012",
      "pattern": "app/server\\.py|main\\.py",
      "affected_docs": [
        "context/01-architecture.md",
        "AGENTS.md"
      ],
      "severity": "high",
      "description": "Cambio en entry point o factory de la app"
    }
  ],
  "default_rule": {
    "affected_docs": ["INDEX.md"],
    "severity": "low"
  }
}
```

### 5.4 Tipos de Cambio y Estrategia de Actualización

| Tipo de cambio | Estrategia | Acción del agente |
|----------------|------------|-------------------|
| **Nuevo desarrollo** (nuevo provider, endpoint, módulo) | Creación | Generar nuevo documento de estrategia + actualizar ÍNDICE y AGENTS.md |
| **Evolutivo** (refactor, cambio de API, nuevo parámetro) | Actualización parcial | Actualizar solo las secciones afectadas del documento existente |
| **Corrección** (bug fix, cambio de lógica interna) | Actualización mínima | Actualizar sección "Trampas" o "Manejo de Errores" si cambió el comportamiento |
| **Parche** (cambio de URL, dominio, dependencia externa) | Actualización puntual | Actualizar URLs, configs, o la sección de "Requisitos Especiales" |
| **Eliminación** (deprecación, borrado de provider) | Eliminación | Eliminar documento de estrategia + actualizar referencias en otros docs |

### 5.5 Detección de Cambios Estructurales (Deep Diff)

No basta con detectar qué archivos cambiaron; hay que clasificar la profundidad del cambio:

```python
# scripts/classify_changes.py
def classify_change_depth(file_path: str, diff_content: str) -> ChangeDepth:
    """
    Analiza el diff para clasificar la profundidad del cambio.
    """
    added_lines = count_added(diff_content)
    removed_lines = count_removed(diff_content)
    
    # Detectar cambios estructurales
    if has_new_class_definition(diff_content):
        return ChangeDepth.NEW_COMPONENT  # → Crear documento
    if has_signature_change(diff_content):
        return ChangeDepth.CONTRACT_CHANGE  # → Actualizar contratos en docs
    if has_new_parameter(diff_content):
        return ChangeDepth.API_CHANGE  # → Actualizar API docs
    if added_lines > 50:
        return ChangeDepth.MAJOR_CHANGE  # → Revisar todo el documento
    if added_lines <= 10 and removed_lines <= 10:
        return ChangeDepth.MINOR_CHANGE  # → Actualización puntual
    
    return ChangeDepth.MODERATE_CHANGE  # → Actualizar secciones relevantes
```

### 5.6 Garantía de Actualización Obligatoria

Para asegurar que la documentación se actualiza sí o sí:

1. **CI bloqueante en `main`**: Si hay cambios en archivos fuente clasificados como `severity: critical` o `severity: high` y el PR no incluye cambios en los documentos correspondientes, el merge se bloquea.

2. **`post-merge hook` en `main`**: Tras merge a main, se dispara automáticamente un agente que actualiza la documentación y commitea los cambios.

3. **`AGENTS.md` como contrato**: El propio `AGENTS.md` declara la obligación:
   ```markdown
   > ⚠️ **REGLA OBLIGATORIA:** Todo cambio en archivos fuente DEBE ir acompañado
   > de la actualización de los documentos agénticos correspondientes.
   > Usa `scripts/classify_changes.py` para saber qué documentos actualizar.
   ```

4. **Badge en README**: Un badge que muestra el estado de sincronización:
   ```
   [![Docs Sync](https://img.shields.io/badge/docs-synced-brightgreen)](...)
   [![Docs Sync](https://img.shields.io/badge/docs-stale%20(3%20files)-red)](...)
   ```

### 5.7 Manejo de Conflictos en Auto-Actualización

Cuando el agente y un humano editan simultáneamente la documentación, se aplica un protocolo de resolución determinista:

#### Jerarquía de Fuente de Verdad
```
1. Código fuente (app/**/*.py, src/**/*.ts) — verdad canónica
2. doc-mapping.json — reglas de correspondencia código↔doc
3. Documentos agénticos (.{tool}/) — derivados del código
```

#### Protocolo de Resolución

| Escenario | Detección | Resolución |
|-----------|-----------|------------|
| **Agente actualiza doc tras merge, humano tenía cambios sin commit** | `git status --porcelain` muestra archivos modificados en `.{tool}/` no commiteados | El agente aborta la actualización. Emite warning en CI: "Doc has uncommitted human edits. Skipping auto-update." |
| **Agente y humano editan el mismo doc en ramas distintas** | Conflicto de merge detectado por git | Prevalece la versión que referencia archivos fuente más recientes (SHA de código más alto). El agente regenera la sección conflictiva desde el código actual. |
| **Agente quiere borrar un doc que el humano expandió** | `validate_docs.py` detecta archivos en `.{tool}/` sin correspondencia en `doc-mapping.json` | Los archivos no mapeados se consideran "manuales" y el agente no los toca. Se añaden a `.gitignore` de auto-actualización. |
| **Humano añade nuevo módulo pero no actualiza docs** | CI detecta `severity: high` sin cambios en docs | Bloquea el merge. El humano debe: (a) ejecutar `scripts/generate_all_docs.py` para generar borrador, o (b) añadir entrada manual en `doc-mapping.json`. |

#### Marcado de Secciones Protegidas

Los documentos agénticos pueden contener marcadores para secciones que el agente no debe sobrescribir:

```markdown
## Propósito
[Este párrafo fue escrito manualmente y tiene contexto que el agente no debe perder]

<!-- AGENT-PROTECTED-START -->
## Notas del Equipo
Esta sección contiene conocimiento tácito que el análisis automático no captura.
<!-- AGENT-PROTECTED-END -->

## Estrategia de Búsqueda
<!-- AGENT-MANAGED-START -->
[Esta sección es regenerada automáticamente desde el AST]
<!-- AGENT-MANAGED-END -->
```

El agente respeta los bloques `AGENT-PROTECTED` y solo actualiza los bloques `AGENT-MANAGED`. Si no hay marcadores, el agente asume que todo el documento es gestionable, excepto el bloque `## Propósito` que se preserva si tiene >50 palabras (heurística de contenido humano significativo).

### 5.8 Criterios de Salida de la Fase 5

- [ ] `.{tool}/doc-mapping.json` existe y cubre ≥90% de patrones de archivo fuente
- [ ] Script `classify_changes.py` implementado y funcional
- [ ] Script `validate_docs.py` implementado y funcional
- [ ] CI step `agentic-docs-check` activo en PRs y push a main
- [ ] Hook `post-commit` o `post-merge` configurado
- [ ] Sección "REGLA OBLIGATORIA" incluida en `AGENTS.md`
- [ ] Al menos 1 ciclo completo de detección → actualización → verificación ejecutado exitosamente

---

## A. Apéndices

### A.1 Resumen de Herramientas por Fase y Ecosistema

| Fase | Python | Node/TS | Go | Rust | JVM | .NET | Dart/Flutter | Swift/Kotlin |
|------|--------|---------|----|------|-----|------|--------------|---------------|
| **0. Descubrimiento** | `pipdeptree`, `pyproject.toml` | `npm ls`, `package.json` | `go mod graph` | `cargo metadata` | `mvn dependency:tree` | `dotnet list package` | `flutter pub deps` | `xcodebuild -list`, `gradlew tasks` |
| **1. Estático** | `pydeps`, `radon`, `vulture`, `pyreverse`, `ast` | `madge`, `dependency-cruiser`, `ts-morph`, `eslint`, `react-docgen`, `storybook` | `goda`, `go-callvis`, `staticcheck` | `cargo-modules`, `cargo-udeps`, `syn` | `jdeps`, `archunit`, `javaparser` | `NetArchTest`, `roslyn`, `ndepend` | `dart_code_metrics`, `dartdoc` | `swift-ast`, `periphery` |
| **2. Dinámico** | `pytest-cov`, `cProfile`, `bandit`, `OpenTelemetry` | `jest --coverage`, `clinic`, `npm audit`, `lighthouse`, `OTel` | `go test -cover`, `pprof`, `gosec`, `OTel` | `cargo-tarpaulin`, `cargo-audit`, `OTel` | `jacoco`, `jprofiler`, `sonarqube` | `coverlet`, `dotnet-trace`, `sonarqube` | `flutter test --coverage`, `flutter devtools` | `xctest`, `androidTest`, `Firebase Test Lab` |
| **3. Síntesis** | Plantillas Markdown + scripts de generación | Plantillas Markdown + scripts de generación | Plantillas Markdown + scripts de generación | Plantillas Markdown + scripts de generación | Plantillas Markdown + scripts de generación | Plantillas Markdown + scripts de generación | Plantillas Markdown + scripts de generación | Plantillas Markdown + scripts de generación |
| **4. Validación** | `scripts/validate_docs.py` | `scripts/validate_docs.js` | `scripts/validate_docs.go` | `scripts/validate_docs.rs` | `scripts/validate_docs.java` | `scripts/validate_docs.cs` | `scripts/validate_docs.dart` | `scripts/validate_docs.swift` |
| **5. Mantenimiento** | Git hooks + CI + `classify_changes.py` | Git hooks + CI + `classify_changes.ts` | Git hooks + CI + `classify_changes.go` | Git hooks + CI + `classify_changes.rs` | Git hooks + CI | Git hooks + CI | Git hooks + CI | Git hooks + CI |

### A.2 Glosario

| Término | Definición |
|---------|------------|
| **Documentación agéntica** | Documentación diseñada para ser consumida por agentes de IA (no solo humanos). Incluye INDEX navegable, contratos explícitos, fragmentos de código ejecutables, y anti-patrones. |
| **Contrato** | Interfaz pública de un módulo: parámetros, retorno, excepciones, pre/postcondiciones y efectos secundarios. |
| **Estrategia** | Documento que describe el comportamiento concreto de una implementación de un contrato (ej: `epublibre.md` para `BaseProvider`). |
| **INDEX** | Documento raíz que mapea tareas del agente a documentos específicos. |
| **Grafo de dependencias** | Representación dirigida de imports/dependencias entre módulos. |
| **Módulo huérfano** | Archivo sin imports entrantes ni salientes — candidato a dead code. |
| **Profundidad del cambio** | Clasificación structural del diff: NEW_COMPONENT, CONTRACT_CHANGE, API_CHANGE, MAJOR_CHANGE, MINOR_CHANGE. |
| **doc-mapping.json** | Archivo de reglas que mapea patrones de archivo fuente a documentos agénticos afectados. |

### A.3 Referencia: Ejemplo Real (WebTranslatorr)

Este proyecto implementa la metodología descrita. La estructura resultante es:

```
.gemini/
├── INDEX.md                          # 17 entradas de caso de uso → documento
├── AGENTS.md                         # Stack, estructura, convenciones, anti-patrones
├── styleguide.md                     # Async, type hints, naming, errores, logging
├── doc-mapping.json                  # (PENDIENTE de crear — Fase 5)
└── context/
    ├── 01-architecture.md            # Diagrama end-to-end + flujo de request
    ├── 02-configuration.md           # 30+ variables de entorno WTR_*
    ├── 03-data-models.md             # SearchResult, ProviderCapabilities, enums
    ├── 04-http-client.md             # HttpClient, rate limiting, cloudscraper
    ├── 05-providers-base.md          # BaseProvider (ABC), ProviderRegistry
    ├── 06-provider-strategies/       # 14 documentos (1 por provider)
    │   ├── ebookelo.md
    │   ├── epublibre.md
    │   ├── lectulandia.md
    │   └── ... (11 más)
    ├── 07-smart-router.md            # SmartRouter, keyword inference
    ├── 08-torznab-protocol.md        # Torznab/Newznab RSS XML spec
    ├── 09-categories.md              # CategoryMapper, Newznab IDs
    ├── 10-domain-resolver.md         # DomainResolver, estrategias
    ├── 11-cache.md                   # SearchCache TTLCache
    ├── 12-zip-extractor.md           # ZipExtractor on-the-fly
    ├── 13-api-endpoints.md           # 9 endpoints documentados
    ├── 14-deployment.md              # Docker, bare-metal, CI/CD
    ├── 15-testing.md                 # pytest, fixtures, asyncio, patrones
    ├── 16-known-issues.md            # Bugs conocidos, workarounds
    └── 17-adding-providers.md        # Guía paso a paso con template
```

- **Cobertura de módulos**: 20/20 (100%) — cada archivo fuente en `app/` está referenciado en al menos 1 documento
- **Cobertura de estrategias**: 14/14 providers tienen documento de estrategia
- **Tamaño total**: ~60 KB de documentación agéntica para ~350 KB de código fuente (ratio 1:6)
- **Pendiente**: Implementar Fase 5 (auto-actualización) para este proyecto

### A.4 Estimación de Esfuerzo por Tamaño de Proyecto

Tiempos orientativos (días-hombre/agente) para un proyecto de complejidad media. Proyectos con arquitectura atípica, multi-lenguaje, o sin tests pueden requerir +50%.

| Tamaño | Archivos fuente | Fase 0 | Fase 1 | Fase 2 | Fase 3 | Fase 4 | Fase 5 | Total |
|--------|----------------|--------|--------|--------|--------|--------|--------|-------|
| **XS** (script/CLI) | 5–20 | 0.5h | 2h | 1h | 3h | 1h | 2h | **~1.2 días** |
| **S** (microservicio) | 20–80 | 1h | 4h | 3h | 6h | 2h | 3h | **~2.5 días** |
| **M** (web/backend típico) | 80–300 | 2h | 8h | 6h | 12h | 4h | 4h | **~4.5 días** |
| **L** (monolito grande) | 300–1000 | 4h | 16h | 12h | 24h | 8h | 8h | **~9 días** |
| **XL** (monorepo multi-paquete) | 1000–5000 | 8h | 40h | 30h | 60h | 16h | 16h | **~21 días** |
| **XXL** (plataforma/ecosistema) | 5000+ | 16h | 80h | 60h | 120h | 24h | 24h | **~40 días** |

**Notas:**
- La Fase 0 siempre es la más rápida (<10% del total)
- La Fase 3 domina el esfuerzo total (35-40%) si se hace manual; con los scripts de 3.5 se reduce 60-70%
- La Fase 2 puede ser la más larga si el proyecto carece de tests (todo el análisis dinámico es manual)
- Para proyectos XL/XXL se recomienda aplicar Fase 0.4 (Estrategia B — documentación independiente por paquete) y tratar cada paquete como un proyecto S/M independiente
- El esfuerzo de Fase 5 es one-time setup + mantenimiento marginal (~10% mensual)

### A.5 Requisitos del Agente de IA para Ejecutar la Metodología

La metodología asume un agente con las siguientes capacidades:

| Capacidad | Mínimo | Recomendado |
|-----------|--------|-------------|
| **Ventana de contexto** | 128K tokens | 200K+ tokens (para proyectos L+) |
| **Acceso a shell** | Lectura/ejecución de comandos | + instalación de dependencias |
| **Acceso a archivos** | Lectura/escritura en el workspace | + acceso a `.git/` y configuración |
| **Herramientas AST** | Capacidad de ejecutar `ast`, `ts-morph`, etc. | + parseo directo en memoria |
| **Razonamiento** | Seguimiento de instrucciones multi-paso | + planificación autónoma de sub-tareas |
| **Generación de código** | Markdown + Python/JS básico | + comprensión del lenguaje del proyecto |

Para proyectos XXL, se recomienda usar agentes especializados por paquete (sub-agentes independientes) y un agente coordinador que consolide.
