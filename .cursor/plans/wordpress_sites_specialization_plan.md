# Plan de Especialización: Integración WordPress sin API

> **Contexto**: Los 8 sitios WordPress integrados pueden tener su API REST deshabilitada.
> Este plan asume el peor caso y detalla, sitio por sitio, qué hace única a cada integración,
> qué nivel de adaptabilidad requiere, y cómo perfeccionar el scraping para cada uno.

**Fecha**: 2026-06-08
**Sitios analizados**: 8 sitios WordPress + 1 CMS propietario (B00k.Bond)

---

## 1. Taxonomía de Diferenciación entre Sitios WordPress

Aunque todos comparten base WordPress, difieren en dimensiones críticas que impiden una solución genérica:

| Dimensión | Variables | Ejemplos en el proyecto |
|-----------|-----------|------------------------|
| **URL de búsqueda** | `/?s=`, `/search/`, `/buscar/`, `/search?q=` | Lectulandia usa `/search/`, HolaEbook prueba `/search?q=` y `/?s=` |
| **URL de detalle** | `/book/`, `/libro/`, `/ebook/`, `/descargar/`, `.html` vs `/` | Espaebook tiene ambos patrones, HolaEbook usa `.html` |
| **Mecanismo de descarga** | Enlace directo, JS linkCode, redirect 302, ZIP wrapper, multi-step | Lectulandia tiene 3 pasos con JS, Ebookelo tiene redirect 302, HolaEbook ZIP |
| **Protección anti-bot** | Cloudflare, CAPTCHA, rate limiting, User-Agent filtering, ninguno | Anna's Archive y EpubLibre requieren cloudscraper |
| **Estructura HTML** | Temas WordPress distintos, selectores únicos | Cada sitio usa clases CSS y estructuras DOM diferentes |
| **Trampas y falsos positivos** | Enlaces de publicidad, navegación interna, categorías, tags | Ebookelo tiene profitablecpmgate, otros tienen /genre/, /autor/, /category/ |
| **Metadatos disponibles** | Autor, género, ISBN, formato, tamaño, año, idioma, sinopsis | Varían enormemente entre sitios |

---

## 2. Análisis Individual por Sitio

### 2.1 Ebookelo (`ww2.ebookelo.com`)

#### ¿Qué lo hace único?

1. **Ad-gate activo**: `profitablecpmgate.com` — el único provider con trampa publicitaria documentada
2. **Enriquecimiento vía página de detalle**: visita `/ebook/{id}/{slug}` para extraer autor, formatos, género, idioma
3. **4 formatos con prioridad**: EPUB > MOBI > PDF > Magnet
4. **Descarga con redirect 302**: `follow_redirects=False` + inspección del header Location
5. **URLs con slug**: las URLs incluyen slug textual (`/ebook/1828/el-quijote`), no solo ID
6. **Deduplicación por idioma**: el mismo libro en diferentes idiomas comparte `book_id`

#### Grado de adaptabilidad requerido: **MUY ALTO**

```
Ebookelo NO es un WordPress genérico. Requiere:
├── Manejo específico de ad-gate (2 sets de enlaces, ignorar profitablecpmgate)
├── Enriquecimiento costoso (1 request extra por resultado)
├── Lógica de selección de formato (prioridad EPUB > MOBI > PDF > Magnet)
├── Interceptación de redirects 302 sin seguirlos
├── Header Referer obligatorio en descarga
├── Deduplicación por book_id (mismo libro, diferente idioma)
└── Parseo de slugs desde URLs (no solo IDs numéricos)
```

#### Plan de mejora específico:

| Tarea | Prioridad | Esfuerzo | Impacto |
|-------|-----------|----------|---------|
| Auditar nuevos patrones de ad-gate | **Crítica** | 1h | Seguridad: evitar servir anuncios |
| Verificar WP REST API (`/wp-json/`) | Alta | 30min | Si disponible, elimina scraping de búsqueda |
| Limitar enriquecimiento a N=25 resultados | Alta | 30min | Reduce latencia ~60% |
| Paralelizar enriquecimiento con semáforo=5 | Alta | 1h | Reduce latencia ~40% |
| Cachear páginas de detalle (TTL 10min) | Alta | 1h | Evita re-requests en búsquedas repetidas |
| Extraer ISBN, año, sinopsis, páginas | Media | 1.5h | Mejores descripciones en Readarr |
| Verificar si hay nuevos formatos (AZW3, FB2) | Media | 30min | Más opciones de descarga |
| Tests de integración con HTML real | Media | 2h | Detección temprana de roturas |

#### Selectores CSS a verificar:

```python
# ¿Siguen vigentes estos selectores?
SELECTORS = {
    "search_results": 'a[href*="/ebook/"]',
    "detail_author": 'a[href*="/ebooks/autor/"]',
    "detail_genre": 'a[href*="/ebooks/genero/"]',
    "detail_downloads": 'a[href*="/download/"]',       # Enlaces REALES (inferiores)
    "ad_gate_trap": 'a[href*="profitablecpmgate"]',     # Enlaces TRAMPA (superiores) — IGNORAR
    "detail_language": 'a[href^="/ebooks/"]',            # Enlace de idioma
}
```

---

### 2.2 EpubLibre (`epublibre.bid`)

#### ¿Qué lo hace único?

1. **Búsqueda**: `/?s={query}` (WordPress estándar)
2. **Deduplicación**: `seen_urls` por URL + filtro de título `'biblioteca'`
3. **Descarga**: busca enlaces con texto "EN EPUB" o "DESCARGAR" en página de detalle
4. **Cloudscraper requerido**: `use_scraper=True`
5. **Sin enriquecimiento**: no visita páginas de detalle durante la búsqueda

#### Grado de adaptabilidad requerido: **MEDIO**

```
EpubLibre es un WordPress relativamente estándar. Lo que requiere especialización:
├── Filtro de enlace de navegación 'biblioteca' (específico de este sitio)
├── Cloudscraper obligatorio (el sitio bloquea sin él)
├── Regex de internal_id: /book/([^/]+)/
├── Búsqueda de enlace de descarga por texto ("EN EPUB", "DESCARGAR")
└── Sin paginación implementada (solo primera página de resultados)
```

#### Plan de mejora específico:

| Tarea | Prioridad | Esfuerzo | Impacto |
|-------|-----------|----------|---------|
| Verificar WP REST API | Alta | 30min | Elimina scraping si está habilitada |
| Añadir paginación de resultados | Alta | 1h | Más resultados en búsquedas |
| Verificar si cloudscraper sigue siendo necesario | Media | 30min | Si no, reduce latencia |
| Añadir extracción de autor (visitar detalle) | Media | 1.5h | Mejor matching en Readarr |
| Implementar búsqueda por autor (`author` param) | Media | 1h | Readarr puede buscar por autor |
| Tests de integración | Media | 1.5h | Detección de roturas |

---

### 2.3 Lectulandia (`ww3.lectulandia.co`)

#### ¿Qué lo hace único?

1. **URL de búsqueda NO estándar**: `/search/{query}` en lugar de `/?s={query}`
2. **Descarga en 3 pasos con JavaScript**:
   - Paso 1: Página de detalle → encontrar enlace `download.php`
   - Paso 2: Seguir `download.php` → página intermedia con JS
   - Paso 3: Extraer `var linkCode = "..."` del JavaScript → construir URL final
3. **Cloudscraper requerido en los 3 pasos**
4. **Filtro de título**: excluye `'libros'` (enlace de navegación)

#### Grado de adaptabilidad requerido: **MUY ALTO**

```
Lectulandia tiene el mecanismo de descarga más complejo de todos los providers.
Requiere:
├── URL de búsqueda distinta a todos los demás WordPress
├── Flujo de descarga de 3 pasos con estado entre requests
├── Extracción de variable JavaScript (linkCode) con regex
├── Construcción de URL final a partir del código extraído
├── Manejo de fallos en cada paso (sin download.php, sin linkCode, etc.)
└── Cloudscraper obligatorio en todos los pasos
```

#### Plan de mejora específico:

| Tarea | Prioridad | Esfuerzo | Impacto |
|-------|-----------|----------|---------|
| **Documentar formato exacto del JS con linkCode** | **Crítica** | 30min | Base para detección de cambios |
| **Añadir regex alternativos para linkCode** | **Crítica** | 1h | Resiliencia ante cambios de ofuscación |
| Implementar fallback si no hay download.php | Alta | 1h | Búsqueda directa de enlaces |
| Implementar fallback si no hay linkCode | Alta | 1h | Intentar descarga directa desde detalle |
| Cachear página intermedia download.php | Media | 30min | Evita re-requests |
| Añadir paginación de resultados | Media | 1h | Más resultados |
| Tests de integración con HTML real | Alta | 2h | El mecanismo es frágil, necesita tests |

#### Regex de linkCode a verificar y expandir:

```python
# Actual (puede romperse si cambian el JS):
LINKCODE_REGEX_1 = r'var linkCode = ["\']([^"\']+)["\'];'

# Alternativos a implementar:
LINKCODE_REGEX_2 = r'linkCode\s*=\s*["\']([^"\']+)["\']'        # Sin var
LINKCODE_REGEX_3 = r'let linkCode = ["\']([^"\']+)["\'];'       # let en vez de var
LINKCODE_REGEX_4 = r'const linkCode = ["\']([^"\']+)["\'];'     # const en vez de var
LINKCODE_REGEX_5 = r'window\.linkCode\s*=\s*["\']([^"\']+)["\']' # window.linkCode
LINKCODE_REGEX_6 = r'["\']linkCode["\']\s*:\s*["\']([^"\']+)["\']' # JSON-like
```

---

### 2.4 Espaebook (`espaebook.cc`)

#### ¿Qué lo hace único?

1. **Doble patrón de URL**: `/libro/{id}/` y `/book/{id}/` — intenta ambos
2. **404 fallback**: si `/libro/{id}/` devuelve 404, intenta `/book/{id}/`
3. **Selectores múltiples**: `a[href*="/libro/"], a[href*="/book/"], h2.entry-title a`
4. **Filtrado de falsos positivos en descarga**: excluye `/genre/`, `/autor/`, `/book/`
5. **Fallback en internal_id**: si el regex falla, usa el último segmento de la URL

#### Grado de adaptabilidad requerido: **ALTO**

```
Espaebook requiere manejo de dualidad de URLs en búsqueda Y descarga:
├── Dos patrones de URL de detalle (/libro/ y /book/)
├── Fallback 404 → intentar el otro patrón
├── Dos patrones de URL en búsqueda (selectores múltiples)
├── Filtrado agresivo de enlaces de navegación en descarga
└── Fallback en extracción de internal_id (regex → último segmento)
```

#### Plan de mejora específico:

| Tarea | Prioridad | Esfuerzo | Impacto |
|-------|-----------|----------|---------|
| Verificar si el sitio consolidó a un solo patrón | Alta | 30min | Simplificaría el código |
| Añadir extracción de autor y género | Media | 1.5h | Mejor matching |
| Mejorar fallback de internal_id (evitar query params) | Media | 1h | IDs más fiables |
| Tests con ambos patrones de URL | Media | 1.5h | Cobertura de edge cases |
| Verificar WP REST API | Baja | 30min | Posible eliminación de scraping |

---

### 2.5 HolaEbook (`holaebook.com`)

#### ¿Qué lo hace único?

1. **ZIP wrapper**: `self.is_zipped = True` — los libros se sirven como ZIP
2. **Doble patrón de búsqueda**: `/search?q={query}` (intento 1) → `/?s={query}` (fallback 404)
3. **Doble patrón de detalle**: `/libro/{id}.html` (intento 1) → `/book/{id}/` (fallback)
4. **Extensión .html**: algunas URLs de detalle terminan en `.html`
5. **Extracción on-the-fly**: el download proxy extrae el EPUB del ZIP en memoria
6. **Texto de descarga**: busca "EPUB", "DESCARGAR", "DOWNLOAD" (multilingüe)

#### Grado de adaptabilidad requerido: **ALTO**

```
HolaEbook es único por el ZIP wrapper + múltiples fallbacks:
├── ZIP wrapper con extracción on-the-fly (único en el proyecto)
├── Doble fallback tanto en búsqueda como en descarga
├── Extensión .html que debe eliminarse al construir URLs
├── Búsqueda multilingüe de enlaces de descarga
└── El flujo ZIP → EPUB depende del download proxy, no del provider
```

#### Plan de mejora específico:

| Tarea | Prioridad | Esfuerzo | Impacto |
|-------|-----------|----------|---------|
| Verificar si el sitio sigue sirviendo ZIPs | **Crítica** | 30min | Si cambió a EPUBs directos, simplificar |
| Probar extracción ZIP con 10+ libros | Alta | 1h | Verificar tasa de éxito |
| Añadir soporte para MOBI/PDF dentro del ZIP | Media | 1h | Más formatos disponibles |
| Verificar si el patrón `/search?q=` sigue vigente | Media | 30min | Eliminar fallback si ya funciona |
| Documentar estructura exacta del ZIP | Media | 30min | Para debugging |

---

### 2.6 Epubflix1 (`epubflix1.com`)

#### ¿Qué lo hace único?

1. **Provider nuevo**: implementado en la expansión multi-indexer, sin historial de estabilidad
2. **Doble patrón de detalle**: `/book/` y `/libro/` (prueba ambos secuencialmente)
3. **Doble estrategia de descarga**:
   - Estrategia 1: buscar texto "EN EPUB", "DESCARGAR", "DOWNLOAD"
   - Estrategia 2: buscar enlaces directos a archivos (`.epub`, `.mobi`, etc.)
4. **Selectores múltiples en búsqueda**: `a[href*="/book/"], a[href*="/libro/"], h2.entry-title a, h3.entry-title a`

#### Grado de adaptabilidad requerido: **MEDIO-ALTO**

```
Epubflix1 es un WordPress con estrategia defensiva (múltiples fallbacks):
├── Sin conocimiento real de la estructura del sitio (provider nuevo)
├── Doble intento de path en detalle (prueba ambos)
├── Doble estrategia de búsqueda de enlaces de descarga
├── Sin tests
└── Sin historial de cambios del sitio
```

#### Plan de mejora específico:

| Tarea | Prioridad | Esfuerzo | Impacto |
|-------|-----------|----------|---------|
| **Verificar estructura real del sitio** | **Crítica** | 1h | Confirmar selectores y patrones |
| **Determinar cuál de los 2 paths es el correcto** | **Crítica** | 30min | Eliminar el fallback innecesario |
| **Crear tests con HTML real del sitio** | **Crítica** | 2h | Base para mantenimiento futuro |
| Verificar WP REST API | Alta | 30min | Si habilitada, simplifica drásticamente |
| Determinar qué metadatos adicionales existen | Media | 1h | Autor, género, formato, tamaño |
| Documentar estructura exacta | Alta | 1h | Para referencia futura |

---

### 2.7 LectuEpubLibre5 (`lectuepublibre5.com`)

#### ¿Qué lo hace único?

1. **Triple patrón de detalle**: `/book/`, `/libro/`, `/descargar/` (más paths que ningún otro)
2. **Filtrado de navegación**: excluye `/genre/` y `/autor/` en enlaces de descarga
3. **Doble búsqueda de enlace**: texto ("DESCARGAR") + extensión de archivo (`.epub`)
4. **Código casi idéntico a MundoEpubLibre1**: si uno falla, probablemente el otro también

#### Grado de adaptabilidad requerido: **MEDIO**

```
LectuEpubLibre5 comparte lógica con MundoEpubLibre1:
├── Triple path de detalle (el más alto de todos)
├── Filtrado de navegación más agresivo
├── Provider nuevo sin tests
└── Riesgo de fallo simultáneo con MundoEpubLibre1 (código duplicado)
```

#### Plan de mejora específico:

| Tarea | Prioridad | Esfuerzo | Impacto |
|-------|-----------|----------|---------|
| Verificar cuál de los 3 paths es el real | Alta | 30min | Eliminar paths innecesarios |
| **Extraer lógica común con MundoEpubLibre1** | Alta | 2h | Reducir duplicación, mantener una sola vez |
| Verificar WP REST API | Alta | 30min | Si habilitada, unificar con otros WP |
| Crear tests | Alta | 1.5h | Provider nuevo sin cobertura |
| Documentar diferencias reales con MundoEpubLibre1 | Media | 30min | Justificar o eliminar duplicación |

---

### 2.8 MundoEpubLibre1 (`mundoepublibre1.com`)

#### ¿Qué lo hace único?

1. **Código casi idéntico a LectuEpubLibre5**: mismos paths, mismos selectores, mismos fallbacks
2. **Provider nuevo sin tests**
3. **Triple patrón de detalle**: `/book/`, `/libro/`, `/descargar/`
4. **Filtrado de navegación**: excluye `/genre/` y `/autor/`

#### Grado de adaptabilidad requerido: **BAJO-MEDIO**

```
MundoEpubLibre1 es esencialmente un clon de LectuEpubLibre5:
├── Misma estrategia, diferentes dominios
├── Oportunidad de unificar en una clase base WordPress genérica
└── Si los sitios son realmente idénticos, el código duplicado es deuda técnica
```

#### Plan de mejora específico:

| Tarea | Prioridad | Esfuerzo | Impacto |
|-------|-----------|----------|---------|
| **Comparar estructura HTML real vs LectuEpubLibre5** | Alta | 1h | Determinar si justifica código separado |
| **Evaluar unificación en clase base** | Alta | 2h | Reducir mantenimiento |
| Verificar WP REST API | Media | 30min | Mismo tratamiento que otros WP |
| Crear tests (o compartirlos con LectuEpubLibre5) | Media | 1h | Cobertura |

---

### 2.9 B00k.Bond (`es.booobook.bond`) — CMS propietario

#### ¿Qué lo hace único?

1. **CMS desconocido**: no es WordPress confirmado, puede ser otro CMS o custom
2. **Doble URL de búsqueda**: `/?s={query}` y `/search/{query}`
3. **5 selectores CSS diferentes**: el provider con más selectores de búsqueda
4. **Filtrado agresivo**: excluye `/genre/`, `/autor/`, `/category/`, `/tag/`, `/page/`, `#`
5. **Filtrado de títulos**: excluye 'inicio', 'home', 'biblioteca', 'contacto'
6. **Triple path de descarga**: `/book/`, `/libro/`, `/descargar/`
7. **Validación de respuesta**: verifica `resp.status_code == 200` antes de parsear

#### Grado de adaptabilidad requerido: **MUY ALTO**

```
B00k.Bond es el provider más defensivo y con más incertidumbre:
├── CMS desconocido (ni siquiera sabemos si es WordPress)
├── Múltiples intentos de URL de búsqueda
├── 5 selectores CSS + filtrado agresivo de falsos positivos
├── Filtrado de títulos de navegación
├── Triple path de descarga
└── Sin conocimiento real de la estructura (provider nuevo, sin tests)
```

#### Plan de mejora específico:

| Tarea | Prioridad | Esfuerzo | Impacto |
|-------|-----------|----------|---------|
| **Identificar el CMS real del sitio** | **Crítica** | 1h | WordPress, Joomla, Drupal, custom? |
| **Determinar URL de búsqueda correcta** | **Crítica** | 30min | Eliminar el fallback que no funciona |
| **Determinar paths de detalle reales** | **Crítica** | 30min | Reducir de 3 paths a 1 |
| **Verificar si tiene API (REST, GraphQL, etc.)** | **Crítica** | 1h | Podría tener API no-WordPress |
| Reducir selectores CSS a los que realmente funcionan | Alta | 1h | Simplificar código defensivo |
| Crear tests con HTML real | Alta | 2h | Provider nuevo sin cobertura |
| Documentar estructura real del sitio | Alta | 1h | Para referencia futura |

---

## 3. Estrategia de Adaptabilidad Progresiva

Para cada sitio WordPress, el orden de ataque debe ser:

```
Nivel 1: API (máxima fiabilidad, mínimo esfuerzo de mantenimiento)
├── Verificar WordPress REST API (/wp-json/wp/v2/)
├── Verificar API alternativa (GraphQL, endpoints JSON personalizados)
└── Si existe API → migrar a cliente API

Nivel 2: Scraping especializado (API no disponible)
├── Determinar el patrón UNO que realmente funciona (eliminar fallbacks innecesarios)
├── Documentar estructura HTML exacta  
├── Implementar selectores específicos para ESE sitio
├── Añadir health check real (búsqueda de prueba)
└── Crear tests con HTML capturado del sitio real

Nivel 3: Hardening (todos los sitios)
├── Rate limiting adaptativo por sitio
├── Rotación de User-Agent
├── Validación de respuestas (longitud, contenido esperado)
├── Detección de cambios (alertas si los selectores fallan)
└── Fallback a mirrors o providers alternativos
```

---

## 4. Matriz de Riesgo por Sitio

| Sitio | Riesgo de rotura | Motivo | Impacto si falla |
|-------|-----------------|--------|-----------------|
| **Ebookelo** | Medio-Alto | Ad-gate puede mutar; redirect 302 depende de headers | Readarr pierde el provider más completo |
| **Lectulandia** | **Alto** | JS linkCode es frágil; cualquier cambio en el JS lo rompe | Readarr pierde un provider único (descarga 3 pasos) |
| **B00k.Bond** | **Alto** | CMS desconocido; los selectores son guesswork | Falla sin previo aviso |
| **Epubflix1** | Medio-Alto | Provider nuevo, estructura no confirmada | Falla sin previo aviso |
| **HolaEbook** | Medio | ZIP wrapper; si cambian a EPUB directo, el código sobra | Funciona pero con complejidad innecesaria |
| **EpubLibre** | Medio | Cloudscraper puede no ser suficiente en el futuro | Provider caído |
| **Espaebook** | Medio-Bajo | Doble patrón; si unifican URLs, se simplifica | Sigue funcionando con fallback |
| **LectuEpubLibre5** | Bajo | Código duplicado con MundoEpubLibre1 | Si falla uno, falla el otro |
| **MundoEpubLibre1** | Bajo | Código duplicado con LectuEpubLibre5 | Si falla uno, falla el otro |

---

## 5. Oportunidades de Unificación

A pesar de las diferencias, hay patrones comunes que pueden abstraerse:

### 5.1 WordPressBookProvider (clase base propuesta)

```python
class WordPressBookProvider(BaseProvider):
    """Base para providers WordPress de libros con configuración por sitio."""
    
    # Configuración por sitio (cada provider define la suya)
    SEARCH_URL_PATTERN: str = "/?s={query}"          # Patrón de URL de búsqueda
    DETAIL_URL_PATTERNS: list[str] = ["/book/{id}/"] # Patrones de URL de detalle
    RESULT_SELECTORS: list[str] = ['a[href*="/book/"]']
    DOWNLOAD_LINK_TEXT: list[str] = ["DESCARGAR", "EPUB", "DOWNLOAD"]
    REQUIRES_CLOUDSCRAPER: bool = True
    NAV_FILTER_PATTERNS: list[str] = []               # Patrones a excluir (/genre/, etc.)
    TITLE_FILTER: list[str] = []                      # Títulos a excluir (biblioteca, etc.)
    
    # Métodos comunes ya implementados por BaseProvider
    # search(), get_download_url() pueden tener implementación base
    # y permitir override para sitios con comportamientos únicos
```

### 5.2 Sitios que podrían unificarse

| Grupo | Sitios | Justificación |
|-------|--------|---------------|
| **WP Simple** | EpubLibre, Epubflix1 | WordPress con búsqueda `/?s=` y descarga directa |
| **WP Dual Path** | Espaebook, HolaEbook | WordPress con doble patrón de URL |
| **WP Defensivo** | LectuEpubLibre5, MundoEpubLibre1 | Código casi idéntico |
| **No unificable** | Ebookelo, Lectulandia, B00k.Bond | Demasiado únicos |

---

## 6. Plan de Ejecución (4 días)

### Día 1: Investigación de APIs WordPress
- [ ] Probar `/wp-json/wp/v2/posts?search=test` en los 8 sitios WordPress
- [ ] Documentar qué sitios tienen API habilitada
- [ ] Para sitios con API: capturar respuesta JSON de ejemplo
- [ ] Decidir migración a API vs mantener scraping para cada uno

### Día 2: Auditoría de sitios sin API
- [ ] Para sitios que requieran scraping: verificar estructura HTML actual
- [ ] Capturar HTML de búsqueda y detalle para cada sitio
- [ ] Verificar selectores CSS uno por uno
- [ ] Documentar diferencias con lo que el código espera

### Día 3: Implementación de mejoras críticas
- [ ] Ebookelo: auditar ad-gate, limitar enriquecimiento, cachear detalles
- [ ] Lectulandia: añadir regex alternativos de linkCode
- [ ] B00k.Bond: identificar CMS, reducir selectores
- [ ] Epubflix1: verificar estructura real, crear tests

### Día 4: Unificación y hardening
- [ ] Evaluar WordPressBookProvider base class
- [ ] Unificar LectuEpubLibre5 + MundoEpubLibre1
- [ ] Implementar health checks reales para WordPress sites
- [ ] Crear tests de integración con HTML capturado

---

## 7. Criterios de Éxito

- [ ] API WordPress REST verificada en los 8 sitios
- [ ] Selectores CSS de scraping verificados/actualizados en los sitios que requieran scraping
- [ ] Ebookelo: ad-gate auditado, enriquecimiento optimizado
- [ ] Lectulandia: regex de linkCode con alternativos implementados
- [ ] B00k.Bond: CMS identificado, estructura documentada
- [ ] LectuEpubLibre5 + MundoEpubLibre1: código duplicado unificado o justificado
- [ ] Tests con HTML real para los 4 providers más frágiles
- [ ] Documentación actualizada en `06-provider-strategies/` para cada sitio
