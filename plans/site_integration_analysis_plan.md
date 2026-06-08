# Plan de Análisis y Perfeccionamiento de Integraciones por Sitio

> **Objetivo**: Analizar en profundidad cada uno de los 14 sitios web integrados en WebTranslatorr para
> determinar si disponen de API oficial/pública, documentar sus capacidades, estudiar su estructura de
> datos, y definir las adaptaciones necesarias para que cada integración funcione de forma óptima,
> resiliente y mantenible.

**Fecha**: 2026-06-08
**Versión**: 1.0
**Proveedores a analizar**: 14 (12 libros + 2 vídeo)

---

## Índice

1. [Clasificación de Sitios](#clasificación-de-sitios)
2. [Fase 1: Auditoría de API por Sitio](#fase-1-auditoría-de-api-por-sitio)
3. [Fase 2: Ingeniería Inversa de Scraping](#fase-2-ingeniería-inversa-de-scraping)
4. [Fase 3: Análisis de Estructura de Datos](#fase-3-análisis-de-estructura-de-datos)
5. [Fase 4: Plan de Adaptación por Sitio](#fase-4-plan-de-adaptación-por-sitio)
6. [Fase 5: Hardening y Resiliencia](#fase-5-hardening-y-resiliencia)
7. [Fase 6: Validación y Monitoreo Continuo](#fase-6-validación-y-monitoreo-continuo)
8. [Cronograma y Recursos](#cronograma-y-recursos)

---

## Clasificación de Sitios

Los 14 sitios se clasifican en tres categorías según su infraestructura:

### Categoría A: Sitios con API conocida o probable (3 sitios)
| Sitio | Evidencia de API | Prioridad |
|-------|-----------------|-----------|
| **Anna's Archive** | API REST documentada, backend Elasticsearch, datos en formato AAC (JSON Lines + Zstandard), torrents de datos públicos | **Alta** |
| **Library Genesis** | API documentada (enlace "API" en homepage), endpoints REST, soporte para búsquedas programáticas | **Alta** |
| **Z-Library** | Sin API pública oficial; dominios personales por usuario, opera en Tor/I2P/clearnet. Posible API interna no documentada | **Media** |

### Categoría B: Sitios WordPress sin API (8 sitios)
| Sitio | Infraestructura | Prioridad |
|-------|----------------|-----------|
| **Ebookelo** | WordPress (personalizado), ad-gate | **Alta** |
| **EpubLibre** | WordPress, cloudscraper requerido | **Alta** |
| **Lectulandia** | WordPress, descarga JS linkCode | **Alta** |
| **Espaebook** | WordPress, doble patrón /libro/ /book/ | **Media** |
| **HolaEbook** | WordPress, archivos ZIP | **Media** |
| **Epubflix1** | WordPress estándar | **Media** |
| **LectuEpubLibre5** | WordPress estándar | **Baja** |
| **MundoEpubLibre1** | WordPress estándar | **Baja** |

### Categoría C: Trackers de torrent (2 sitios)
| Sitio | Infraestructura | Prioridad |
|-------|----------------|-----------|
| **MejorTorrent** | CMS propio, .torrent directos, IMDb→TMDB | **Alta** |
| **DonTorrent** | CMS propio, sin búsqueda GET, listados | **Media** |

### Categoría D: Sitios con estructura propietaria (1 sitio)
| Sitio | Infraestructura | Prioridad |
|-------|----------------|-----------|
| **B00k.Bond** | CMS desconocido, multi-patrón | **Media** |

---

## Fase 1: Auditoría de API por Sitio

Para cada sitio, determinar si dispone de API y, en caso afirmativo, documentarla exhaustivamente.

### 1.1 Metodología de Descubrimiento de API

Para cada sitio, ejecutar las siguientes verificaciones en orden:

```
Paso 1: Búsqueda de documentación oficial
├── Revisar homepage en busca de enlaces "API", "Developers", "Docs"
├── Buscar en Google: "site:{dominio} api documentation"
├── Buscar en GitHub: "{nombre_sitio} api"
├── Revisar robots.txt: ¿hay referencias a /api/?
└── Revisar el código fuente de la homepage en busca de endpoints JS

Paso 2: Sondeo de endpoints comunes
├── GET {base_url}/api
├── GET {base_url}/api/v1
├── GET {base_url}/api/search?q=test
├── GET {base_url}/api/docs
├── GET {base_url}/swagger.json
└── GET {base_url}/openapi.json

Paso 3: Análisis de tráfico de la web
├── Abrir DevTools Network tab
├── Realizar una búsqueda en el sitio
├── Identificar llamadas XHR/Fetch a endpoints internos
├── Inspeccionar payloads JSON
└── Documentar headers de autenticación

Paso 4: Verificación de API no oficiales
├── Buscar en ProgrammableWeb, RapidAPI, Postman Collections
├── Revisar proyectos open-source que integren el sitio
└── Verificar si Anna's Archive agrega datos del sitio vía API
```

### 1.2 Ficha de Auditoría por Sitio

Para cada sitio, completar:

| Campo | Descripción |
|-------|-------------|
| **¿Tiene API?** | Sí/No/Parcial |
| **URL base** | URL raíz de la API |
| **Autenticación** | None / API Key / OAuth2 / Token / Cookie |
| **Formato respuesta** | JSON / XML / HTML / Binario |
| **Rate limiting** | Límites conocidos |
| **Endpoints** | Lista de endpoints descubiertos |
| **Parámetros** | Parámetros aceptados por cada endpoint |
| **Códigos de error** | HTTP status codes documentados |
| **Cobertura funcional** | ¿Cubre búsqueda, descarga y metadatos? |

### 1.3 Anna's Archive — Auditoría de API

**Estado conocido**: API REST pública, backend Elasticsearch + MariaDB.

**Evidencia**:
- Anna's Archive usa Flask como backend y Elasticsearch para búsquedas (documentado en su blog)
- Publica datasets completos en formato AAC (Anna's Archive Containers) vía torrent
- Los datos usan JSON Lines comprimido con Zstandard
- El sitio es open source (CC0), código disponible en GitLab
- Tiene sistema de membresías con diferentes velocidades de descarga

**Tareas de auditoría**:
1. [ ] Clonar/revisar el repositorio GitLab de Anna's Archive para encontrar la API
2. [ ] Documentar endpoints de búsqueda: request/response format
3. [ ] Documentar endpoints de descarga: cómo obtener URLs directas
4. [ ] Verificar sistema de rate limiting por tipo de membresía
5. [ ] Documentar formato AAC para posible ingesta directa de datos
6. [ ] Evaluar si es mejor usar la API o seguir scrapeando (coste/beneficio)

**Endpoints esperados a documentar**:
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/search?q={query}&lang=es&ext=epub` | Búsqueda (ya usado vía scraping) |
| GET | `/md5/{hash}` | Detalle de libro |
| GET | `/d/{md5}/{filename}` | Descarga directa |
| ? | `/api/*` | Posibles endpoints de API REST |

### 1.4 Library Genesis — Auditoría de API

**Estado conocido**: API documentada en el propio sitio (enlace "API" en homepage).

**Evidencia**:
- La homepage de libgen.ee tiene un enlace explícito "API" en la sección OTHERS
- Libgen expone endpoints para búsqueda programática
- Soporta múltiples formatos de respuesta
- Tiene sistema de mirrors y dominios alternativos (*.lc, *.li, *.gs, *.vg, *.la, *.bz, *.gl)

**Tareas de auditoría**:
1. [ ] Acceder a la documentación de API en libgen.ee/api
2. [ ] Documentar todos los endpoints disponibles
3. [ ] Documentar parámetros de búsqueda avanzada (campos: md5, tth, sha1, sha256, doi, etc.)
4. [ ] Documentar formato de respuesta
5. [ ] Verificar rate limiting
6. [ ] Evaluar migración de scraping HTML → API REST

**Endpoints esperados**:
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET/POST | `/api/search?req={query}&column=def` | Búsqueda |
| GET | `/api/book?md5={hash}` | Detalle por MD5 |
| GET | `/api/download?md5={hash}` | Descarga |

### 1.5 Z-Library — Auditoría de API

**Estado conocido**: Sin API pública. Usa sistema de dominios personales por usuario.

**Evidencia**:
- Z-Library no abre su base de datos completa al público
- Opera en clearnet, Tor (.onion) e I2P
- Tras los arrests de 2022, implementó URLs personales por usuario
- Tiene clientes nativos para Android, Windows y Linux
- Anna's Archive mantiene un mirror completo de Z-Library

**Tareas de auditoría**:
1. [ ] Analizar los clientes nativos (Android/Windows) para descubrir API interna
2. [ ] Decompilar/revisar el cliente Android para encontrar endpoints
3. [ ] Capturar tráfico del cliente nativo con proxy MITM
4. [ ] Documentar cualquier API descubierta
5. [ ] Evaluar si usar el mirror de Anna's Archive en lugar de Z-Library directo

### 1.6 MejorTorrent — Auditoría de API

**Estado conocido**: Sin API. Sitio con búsqueda GET estándar.

**Tareas de auditoría**:
1. [ ] Revisar si hay endpoints XHR en las páginas de búsqueda/detalle
2. [ ] Verificar si existe `/api/` o endpoints JSON no documentados
3. [ ] Analizar si el sitio carga resultados vía AJAX

### 1.7 Sitios WordPress — Auditoría de API

**Estado conocido**: WordPress tiene API REST nativa en `/wp-json/wp/v2/`.

**Tareas de auditoría para los 8 sitios WordPress**:
1. [ ] Probar `GET {base_url}/wp-json/wp/v2/posts?search={query}` en cada sitio
2. [ ] Probar `GET {base_url}/wp-json/` para ver endpoints disponibles
3. [ ] Verificar si la API REST está habilitada o deshabilitada
4. [ ] Documentar formatos de respuesta si está disponible
5. [ ] Verificar si los custom post types (libros) se exponen vía API

**WordPress REST API estándar** (si está habilitada):
| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/wp-json/wp/v2/posts?search={q}` | Búsqueda de posts |
| GET | `/wp-json/wp/v2/posts/{id}` | Detalle de post |
| GET | `/wp-json/wp/v2/categories` | Categorías |
| GET | `/wp-json/wp/v2/media/{id}` | Medios/descargas |

### 1.8 Criterios de Éxito — Fase 1

- [ ] Ficha de auditoría completada para los 14 sitios
- [ ] Endpoints de API documentados donde existan (método, parámetros, autenticación, respuesta)
- [ ] Decisión documentada para cada sitio: **migrar a API** vs **mantener scraping** vs **solución híbrida**
- [ ] Para sitios con API: estimación de esfuerzo de migración
- [ ] Para sitios sin API: confirmación de que el scraping es la única opción

---

## Fase 2: Ingeniería Inversa de Scraping

Para sitios sin API (o donde la API no cubra todas las necesidades), estudiar en profundidad la estructura HTML y el flujo de obtención de datos.

### 2.1 Metodología de Análisis de Scraping

Para cada sitio que requiera scraping, ejecutar:

```
1. Documentar estructura de URLs
   ├── URL de búsqueda
   ├── URL de detalle
   ├── URL de descarga (directa o intermedia)
   └── Parámetros de paginación/filtrado

2. Analizar estructura HTML
   ├── Selectores CSS para resultados de búsqueda
   ├── Selectores CSS para metadatos (título, autor, formato, tamaño)
   ├── Selectores CSS para enlaces de descarga
   └── Estructura de paginación

3. Identificar mecanismos anti-bot
   ├── Cloudflare / DDoS-Guard / similares
   ├── CAPTCHAs
   ├── Rate limiting
   ├── User-Agent filtering
   └── JavaScript requerido (SPA, React, etc.)

4. Documentar flujo de descarga
   ├── Pasos intermedios (páginas redirect, JS linkCode)
   ├── Formatos de archivo disponibles
   ├── Headers requeridos (Referer, cookies)
   └── Manejo de errores y edge cases

5. Identificar trampas y falsos positivos
   ├── Enlaces de publicidad (profitablecpmgate.com en Ebookelo)
   ├── Enlaces de navegación interna (géneros, autores)
   └── Contenido duplicado
```

### 2.2 Ebookelo — Estudio de Scraping

**Complejidad**: Alta (ad-gate, enriquecimiento, múltiples formatos)

**Tareas**:
1. [ ] Documentar cambio de URLs si el sitio se ha rediseñado
2. [ ] Verificar que los selectores de ad-gate sigan vigentes
3. [ ] Probar todos los formatos de descarga (epub, mobi, pdf, magnet)
4. [ ] Documentar el comportamiento exacto del redirect 302 → Location
5. [ ] Verificar si hay nuevos patrones de profitablecpmgate
6. [ ] Analizar si la paginación funciona correctamente

### 2.3 EpubLibre — Estudio de Scraping

**Complejidad**: Media (WordPress + cloudscraper)

**Tareas**:
1. [ ] Verificar si el patrón de URL `/?s={query}` sigue vigente
2. [ ] Confirmar selectores: `a[href*="/book/"]`, filtro 'biblioteca'
3. [ ] Verificar que la detección de enlaces "EN EPUB" / "DESCARGAR" funciona
4. [ ] Probar con y sin cloudscraper para ver si sigue siendo necesario

### 2.4 Lectulandia — Estudio de Scraping

**Complejidad**: Alta (descarga en 3 pasos con JavaScript linkCode)

**Tareas**:
1. [ ] Verificar patrón de URL `/search/{query}` (sin ?s=)
2. [ ] Confirmar flujo de 3 pasos: detalle → download.php → linkCode → URL final
3. [ ] Verificar que el regex `var linkCode = ["']([^"']+)["'];` sigue funcionando
4. [ ] Documentar si han cambiado el mecanismo de ofuscación del linkCode
5. [ ] Probar con diferentes libros para verificar consistencia

### 2.5 Espaebook — Estudio de Scraping

**Complejidad**: Media (doble patrón /libro/ /book/)

**Tareas**:
1. [ ] Verificar ambos patrones de URL: `/?s=`, `/libro/`, `/book/`
2. [ ] Confirmar fallback 404 → intentar el otro patrón
3. [ ] Verificar filtrado de enlaces de navegación (/genre/, /autor/, /book/)
4. [ ] Comprobar si hay nuevos patrones de URL

### 2.6 HolaEbook — Estudio de Scraping

**Complejidad**: Media (ZIP wrapper, doble patrón de búsqueda)

**Tareas**:
1. [ ] Verificar ambos patrones: `/search?q=` y `/?s=`
2. [ ] Confirmar que los archivos siguen sirviéndose como ZIP
3. [ ] Probar extracción ZIP con varios libros
4. [ ] Verificar si el sitio ha cambiado a servir EPUBs directamente

### 2.7 Anna's Archive — Estudio de Scraping (si se mantiene)

**Complejidad**: Media-Alta (Tailwind CSS classes, cloudscraper fuerte)

**Tareas**:
1. [ ] Documentar clases Tailwind actuales usadas en resultados
2. [ ] Verificar selectores de descarga: `.js-download-link`, "Slow Partner Server"
3. [ ] Confirmar patrón de URL `/search?q=&lang=es&ext=epub`
4. [ ] Comparar scraping actual vs posible uso de API

### 2.8 MejorTorrent — Estudio de Scraping

**Complejidad**: Alta (enriquecimiento pesado, IMDb→TMDB, series por episodio)

**Tareas**:
1. [ ] Verificar patrón de búsqueda `/busqueda?q={query}`
2. [ ] Confirmar selectores de resultados
3. [ ] Verificar extracción de calidad del título `(DVDRip)`
4. [ ] Confirmar funcionamiento de IMDb→TMDB (requiere API key)
5. [ ] Verificar extracción de season/episode de nombres de torrent
6. [ ] Documentar si DonTorrent sigue compartiendo esquema de IDs

### 2.9 Library Genesis — Estudio de Scraping (si se mantiene)

**Complejidad**: Media (tabla HTML, columnas posicionales)

**Tareas**:
1. [ ] Verificar estructura de tabla `class='c'` (columnas fijas)
2. [ ] Confirmar índices de columna (1=autor, 2=título, 4=año, 6=tamaño, 7=extensión)
3. [ ] Verificar extracción de MD5
4. [ ] Confirmar URL de búsqueda con parámetros
5. [ ] Comparar scraping actual vs posible uso de API

### 2.10 Nuevos Providers — Estudio de Scraping

**Sitios**: Epubflix1, B00k.Bond, LectuEpubLibre5, MundoEpubLibre1, Z-Library

**Tareas comunes**:
1. [ ] Verificar estructura actual de cada sitio (pueden haber cambiado desde la implementación)
2. [ ] Confirmar selectores CSS
3. [ ] Documentar patrones de URL reales
4. [ ] Identificar mecanismos anti-bot

### 2.11 Criterios de Éxito — Fase 2

- [ ] Para cada sitio scrapeado: documentación actualizada de estructura HTML
- [ ] Selectores CSS verificados y funcionales
- [ ] Flujos de descarga probados end-to-end
- [ ] Mecanismos anti-bot identificados y documentados
- [ ] Edge cases y trampas documentados

---

## Fase 3: Análisis de Estructura de Datos

Para cada sitio, documentar la estructura completa de los datos que se extraen.

### 3.1 Metodología

```
1. Identificar todos los campos de datos disponibles
   ├── Campos actualmente extraídos por el provider
   ├── Campos disponibles en la página pero no extraídos
   └── Campos disponibles vía API pero no usados

2. Documentar el esquema de datos del sitio
   ├── Tipos de datos (string, int, datetime, etc.)
   ├── Formatos específicos (ISBN, MD5, IMDb ID)
   └── Valores posibles / enumeraciones

3. Mapear al modelo SearchResult
   ├── Correspondencia directa (title → title)
   ├── Transformación necesaria (calidad → categorías Newznab)
   └── Campos no mapeables (oportunidades de extra_attrs)
```

### 3.2 Ficha de Estructura de Datos por Sitio

Para cada sitio, completar:

| Campo en el sitio | Tipo | Ejemplo | Campo SearchResult | Transformación |
|-------------------|------|---------|-------------------|----------------|
| Título del libro | string | "El Quijote" | `title` | Directa |
| URL del libro | string | "/book/123/" | `link` | Concatenar con base_url |
| Autor | string | "Cervantes" | `author` | Directa |
| Formato | string | "EPUB" | `download_url` (fmt) | Mapear a extensión |
| Tamaño | string | "2.5 MB" | `size_bytes` | Parsear a int |
| Fecha | string | "2024-01-15" | `pub_date` | Parsear a datetime |
| Categoría/Género | string | "Novela" | `categories`, `extra_attrs` | Mapear a Newznab |
| Idioma | string | "Español" | `extra_attrs["language"]` | Directa |
| Portada | URL | "/img/123.jpg" | No mapeado actualmente | — |
| Sinopsis | texto largo | "..." | `description` | Directa (truncar si es muy larga) |
| ISBN | string | "978-3-16-..." | `extra_attrs["isbn"]` | Directa |
| Valoración | float | 4.5 | No mapeado actualmente | — |

### 3.3 Oportunidades de Enriquecimiento

Identificar metadatos NO extraídos actualmente que podrían añadirse:

| Sitio | Metadato disponible | No extraído actualmente | Utilidad |
|-------|-------------------|------------------------|----------|
| Ebookelo | Idioma, sinopsis | Parcial (solo autor y género) | Mejor descripción en *Arr |
| Lectulandia | ISBN, editorial | No | Búsqueda más precisa |
| LibGen | ISBN, DOI, editorial, serie | Parcial | Metadatos ricos |
| MejorTorrent | IMDb (a veces), reparto | IMDb (extraído en detalle) | Matching en Radarr |
| Z-Library | ISBN, DOI, año, editorial | Parcial | Búsqueda más precisa |

### 3.4 Criterios de Éxito — Fase 3

- [ ] Ficha de estructura de datos completada para los 14 sitios
- [ ] Todos los campos mapeados a SearchResult o extra_attrs
- [ ] Oportunidades de enriquecimiento identificadas y priorizadas
- [ ] Campos no mapeables documentados con justificación

---

## Fase 4: Plan de Adaptación por Sitio

Para cada sitio, definir las adaptaciones necesarias para que la integración funcione de forma perfecta.

### 4.1 Categorización de Adaptaciones

| Tipo | Descripción | Ejemplo |
|------|-------------|---------|
| **Migrar a API** | Sustituir scraping HTML por llamadas API REST | LibGen: scraping tabla HTML → API JSON |
| **Mejorar scraping** | Refinar selectores, añadir fallbacks | EpubLibre: añadir selectores alternativos |
| **Añadir enriquecimiento** | Extraer más metadatos de la página de detalle | Ebookelo: extraer ISBN, idioma |
| **Robustecer descarga** | Mejorar flujo de descarga (retries, mirrors) | Anna's Archive: probar múltiples mirrors |
| **Optimizar rendimiento** | Reducir requests, cachear, paralelizar | MejorTorrent: limitar enriquecimiento |
| **Manejar anti-bot** | Rotar IPs, adaptar delays, usar sesiones | Z-Library: implementar login persistente |

### 4.2 Plan de Adaptación — Anna's Archive

**Decisión**: **Migrar a API** (prioridad alta)

**Justificación**: Anna's Archive tiene API REST y publica datos estructurados. El scraping actual con cloudscraper es frágil y lento.

**Tareas**:
1. [ ] Documentar API de búsqueda (endpoint, parámetros, respuesta JSON)
2. [ ] Implementar `AnnaArchiveApiClient` que use la API en lugar de scraping HTML
3. [ ] Mapear respuesta JSON → `SearchResult`
4. [ ] Implementar descarga vía API (si existe) o mantener scraping para descargas
5. [ ] Evaluar ingesta directa de datos AAC (torrent) para búsquedas offline
6. [ ] Mantener cloudscraper como fallback si la API no está disponible

**Esfuerzo estimado**: 5-8 horas
**Impacto**: Elimina dependencia de cloudscraper, mejora velocidad, añade metadatos

### 4.3 Plan de Adaptación — Library Genesis

**Decisión**: **Migrar a API** (prioridad alta)

**Justificación**: Libgen tiene API documentada. El scraping actual de tablas HTML con índices de columna fijos es frágil.

**Tareas**:
1. [ ] Documentar API completa (endpoints, parámetros de búsqueda avanzada)
2. [ ] Implementar `LibgenApiClient`
3. [ ] Mapear respuesta JSON → `SearchResult`
4. [ ] Aprovechar campos avanzados: md5, tth, sha1, doi, issn
5. [ ] Implementar descarga vía API
6. [ ] Mantener scraping como fallback

**Esfuerzo estimado**: 4-6 horas
**Impacto**: Elimina dependencia de estructura de tabla HTML, añade búsqueda avanzada

### 4.4 Plan de Adaptación — Z-Library

**Decisión**: **Solución híbrida** (prioridad media)

**Justificación**: Z-Library no tiene API pública pero tiene clientes nativos que pueden revelar endpoints internos. El scraping es complejo por los cambios de dominio y el sistema de login.

**Tareas**:
1. [ ] Analizar cliente Android para descubrir API interna
2. [ ] Si se descubre API: implementar `ZLibraryApiClient`
3. [ ] Si no: implementar sistema de login persistente para scraping
4. [ ] Evaluar usar el mirror de Anna's Archive como fuente alternativa
5. [ ] Implementar rotación de User-Agent y delays para evitar detección

**Esfuerzo estimado**: 8-12 horas
**Impacto**: Mejora significativa en fiabilidad si se descubre API

### 4.5 Plan de Adaptación — Ebookelo

**Decisión**: **Mejorar scraping** (prioridad media)

**Justificación**: No tiene API. El scraping actual es sólido pero puede mejorarse.

**Tareas**:
1. [ ] Añadir extracción de ISBN, idioma, sinopsis en enriquecimiento
2. [ ] Implementar caché de páginas de detalle para reducir requests
3. [ ] Mejorar manejo del ad-gate: verificar nuevos patrones de profitablecpmgate
4. [ ] Añadir soporte para múltiples páginas de resultados
5. [ ] Implementar rate limiting adaptativo
6. [ ] Mejorar deduplicación por idioma

**Esfuerzo estimado**: 3-4 horas
**Impacto**: Más metadatos, menos requests, mejor experiencia en *Arr

### 4.6 Plan de Adaptación — MejorTorrent

**Decisión**: **Optimizar rendimiento** (prioridad alta)

**Justificación**: El enriquecimiento visita la página de detalle de CADA resultado, causando latencia.

**Tareas**:
1. [ ] Limitar enriquecimiento a N resultados (ej: primeros 25)
2. [ ] Paralelizar enriquecimiento con `asyncio.gather` y semáforo de concurrencia
3. [ ] Cachear páginas de detalle
4. [ ] Extraer metadatos adicionales: IMDb (ya se hace), reparto, duración
5. [ ] Verificar extracción de season/episode con nuevos patrones de torrent
6. [ ] Implementar health check rápido del dominio antes de buscar

**Esfuerzo estimado**: 4-6 horas
**Impacto**: Reducción significativa de latencia en búsquedas

### 4.7 Plan de Adaptación — Lectulandia

**Decisión**: **Robustecer descarga** (prioridad alta)

**Justificación**: La descarga en 3 pasos con JS linkCode es frágil.

**Tareas**:
1. [ ] Documentar formato exacto del JavaScript que contiene linkCode
2. [ ] Añadir regex alternativos para diferentes formatos de ofuscación
3. [ ] Implementar fallback: si falla linkCode, buscar enlaces directos
4. [ ] Verificar si hay API de WordPress REST disponible
5. [ ] Añadir logs detallados para depuración

**Esfuerzo estimado**: 2-3 horas
**Impacto**: Mayor tasa de éxito en descargas

### 4.8 Plan de Adaptación — WordPress (varios)

**Decisión**: **Verificar API WordPress REST + mejorar scraping**

**Sitios**: EpubLibre, Espaebook, HolaEbook, Epubflix1, LectuEpubLibre5, MundoEpubLibre1

**Tareas comunes**:
1. [ ] Verificar `/wp-json/wp/v2/posts?search={q}` en cada sitio
2. [ ] Si la API está disponible: implementar cliente WordPress REST
3. [ ] Si no: añadir selectores alternativos y fallbacks
4. [ ] Documentar diferencias entre sitios WordPress
5. [ ] Unificar lógica común en un `WordPressBookProvider` base

**Esfuerzo estimado**: 6-10 horas (total para los 6 sitios)
**Impacto**: Si la API está disponible, eliminación de scraping para esos sitios

### 4.9 Plan de Adaptación — DonTorrent

**Decisión**: **Reevaluar viabilidad** (prioridad baja)

**Justificación**: Sin búsqueda GET y sin enriquecimiento, el provider actual es muy limitado.

**Tareas**:
1. [ ] Verificar si el sitio ha añadido búsqueda GET
2. [ ] Si no: implementar enriquecimiento básico (visitar página de detalle)
3. [ ] Evaluar si merece la pena mantener este provider
4. [ ] Considerar marcar como "solo fallback" explícitamente

**Esfuerzo estimado**: 2-3 horas

### 4.10 Criterios de Éxito — Fase 4

- [ ] Plan de adaptación definido para cada uno de los 14 sitios
- [ ] Decisión API vs scraping documentada y justificada
- [ ] Estimación de esfuerzo para cada adaptación
- [ ] Priorización por impacto/ esfuerzo

---

## Fase 5: Hardening y Resiliencia

Estrategias transversales para que todas las integraciones sean robustas.

### 5.1 Sistema de Health Check por Provider

Cada provider debe implementar `is_healthy()` con una verificación real:

```python
async def is_healthy(self) -> bool:
    """Verifica: 1) dominio accesible, 2) búsqueda de prueba funciona"""
    try:
        # 1. Health check básico (HEAD al dominio)
        resp = await self.http_client.head(self.base_url)
        if resp.status_code >= 400:
            return False
        
        # 2. Búsqueda de prueba (query que siempre devuelve resultados)
        results = await self.search("test", categories=self.categories, limit=1)
        return len(results) > 0
    except Exception:
        return False
```

### 5.2 Sistema de Fallback en Cascada

Para providers con mirrors o fuentes alternativas:

```
Provider principal
    │
    ├── ¿Funciona? → Usar
    │
    └── ¿Falló?
        ├── Intentar mirror 1
        ├── Intentar mirror 2
        └── Intentar provider alternativo (ej: DonTorrent como fallback de MejorTorrent)
```

### 5.3 Rate Limiting Adaptativo

Ajustar rate limiting basado en respuestas del servidor:

```python
# Si el servidor responde 429 → reducir tasa
# Si el servidor responde rápido → aumentar tasa gradualmente
# Mantener tasa base configurable por provider
```

### 5.4 Rotación de User-Agent por Tipo de Sitio

| Tipo de sitio | User-Agents recomendados |
|---------------|------------------------|
| WordPress | Chrome/Firefox desktop |
| Cloudflare protegido | Chrome mobile + cloudscraper |
| Sin protección | Cualquiera |
| API | Application-specific (ej: `WebTranslatorr/1.0`) |

### 5.5 Validación de Respuestas

Antes de parsear, validar que la respuesta es HTML válido:

```python
# Verificar que no es página de error/captcha
if len(resp.text) < 500:
    logger.warning(f"Respuesta sospechosamente corta: {len(resp.text)} bytes")
    return []

# Verificar que contiene elementos esperados
if 'book' not in resp.text.lower() and 'libro' not in resp.text.lower():
    logger.warning("La respuesta no parece contener resultados de libros")
    return []
```

### 5.6 Criterios de Éxito — Fase 5

- [ ] `is_healthy()` implementado para los 14 providers
- [ ] Sistema de fallback definido para providers críticos
- [ ] Validación de respuestas implementada
- [ ] Rate limiting adaptativo configurado

---

## Fase 6: Validación y Monitoreo Continuo

### 6.1 Tests Automatizados de Integración

Para cada provider, crear tests que verifiquen:

```python
@pytest.mark.integration  # Marcados para ejecución periódica, no en CI
@pytest.mark.asyncio
async def test_PROVIDER_search_returns_results():
    """Verifica que el provider real devuelve resultados para una query conocida."""
    http_client = HttpClient()
    provider = PROVIDER(http_client)
    results = await provider.search("test query", categories=[7020])
    assert len(results) > 0
    assert all(isinstance(r, SearchResult) for r in results)

@pytest.mark.asyncio
async def test_PROVIDER_download_url_resolves():
    """Verifica que get_download_url devuelve una URL válida."""
    # ...
```

### 6.2 Health Check Periódico

Configurar un cron/endpoint que ejecute health checks de todos los providers y alerte si alguno falla:

```
GET /api/domains/refresh  → Forzar resolución de dominios
GET /api/domains          → Verificar estado
GET /health/{provider_id}  → Health check individual
```

### 6.3 Monitoreo de Cambios en los Sitios

Para cada sitio, monitorear proactivamente cambios:

| Método | Descripción | Frecuencia |
|--------|-------------|------------|
| **Domain check** | Verificar que el dominio responde | Cada 30 min (ya implementado) |
| **Selector check** | Verificar que los selectores CSS siguen encontrando elementos | Diario |
| **Structure diff** | Comparar HTML de búsqueda con snapshot anterior | Semanal |
| **Result count** | Verificar que las búsquedas de prueba devuelven resultados | Diario |

### 6.4 Dashboards de Estado

Endpoint que muestre el estado de todas las integraciones:

```json
GET /api/status
{
  "providers": {
    "ebookelo": {
      "healthy": true,
      "last_check": "2026-06-08T09:00:00Z",
      "domain": "https://ww2.ebookelo.com",
      "avg_response_time_ms": 1200,
      "success_rate": 0.95
    },
    "epublibre": {
      "healthy": false,
      "last_check": "2026-06-08T09:00:00Z",
      "domain": "https://epublibre.bid",
      "error": "Connection timeout",
      "success_rate": 0.60
    }
  }
}
```

### 6.5 Criterios de Éxito — Fase 6

- [ ] Tests de integración para providers críticos (Ebookelo, EpubLibre, MejorTorrent, Anna's Archive)
- [ ] Health check periódico automatizado
- [ ] Sistema de alerta si un provider falla consistentemente
- [ ] Dashboard de estado de providers

---

## Cronograma y Recursos

### Priorización por Impacto

| Prioridad | Sitios | Esfuerzo total estimado |
|-----------|--------|------------------------|
| **Inmediata** (semana 1) | Anna's Archive (API), LibGen (API), MejorTorrent (optimizar) | 13-20 horas |
| **Alta** (semana 2) | Lectulandia (robustecer), Ebookelo (mejorar), WordPress REST (investigar) | 11-17 horas |
| **Media** (semana 3) | Z-Library (investigar API), WordPress varios, B00k.Bond | 16-25 horas |
| **Baja** (semana 4) | DonTorrent, Hardening transversal, Monitoreo | 10-15 horas |

### Herramientas Necesarias

| Herramienta | Uso |
|-------------|-----|
| **Burp Suite / mitmproxy** | Capturar tráfico HTTP/HTTPS para descubrir APIs |
| **Postman / Insomnia** | Probar endpoints de API |
| **jadx / apktool** | Decompilar cliente Android de Z-Library |
| **Browser DevTools** | Inspeccionar estructura HTML y llamadas XHR |
| **curl / httpie** | Sondeo rápido de endpoints |
| **BeautifulSoup + lxml** | Parsing HTML (ya en uso) |
| **pytest + pytest-asyncio** | Tests de integración |
| **Prometheus + Grafana** | Monitoreo (opcional, futuro) |

### Entregables por Fase

| Fase | Entregable | Formato |
|------|-----------|---------|
| 1 | Fichas de auditoría de API (14 sitios) | Markdown en `.gemini/context/06-provider-strategies/{sitio}.md` |
| 2 | Documentación de estructura HTML y flujos | Actualizar `06-provider-strategies/` |
| 3 | Mapeo de datos (campos fuente → SearchResult) | Tabla en cada ficha de provider |
| 4 | Plan de adaptación con tareas y esfuerzo | Este documento (actualizado) |
| 5 | Código de hardening implementado | PRs en `app/providers/` |
| 6 | Tests de integración y health checks | PRs en `tests/` y `app/api/` |

---

## Resumen de Decisiones Esperadas

| Sitio | Decisión probable | Motivo |
|-------|-------------------|--------|
| **Anna's Archive** | Migrar a API | API REST disponible, scraping frágil con Cloudflare |
| **Library Genesis** | Migrar a API | API documentada, scraping de tabla HTML frágil |
| **Z-Library** | Híbrido (investigar API) | Sin API pública, posible vía cliente nativo |
| **Ebookelo** | Mantener scraping, mejorar | Sin API, scraping maduro |
| **EpubLibre** | Investigar WP REST | WordPress puede tener API REST |
| **Lectulandia** | Mantener scraping, robustecer | Sin API, scraping funcional |
| **Espaebook** | Investigar WP REST | WordPress puede tener API REST |
| **HolaEbook** | Mantener scraping | Sin API, scraping funcional |
| **Epubflix1** | Investigar WP REST | Provider nuevo, verificar API |
| **LectuEpubLibre5** | Investigar WP REST | WordPress puede tener API REST |
| **MundoEpubLibre1** | Investigar WP REST | WordPress puede tener API REST |
| **B00k.Bond** | Mantener scraping, mejorar | CMS desconocido, scraping defensivo |
| **MejorTorrent** | Mantener scraping, optimizar | Sin API, scraping maduro pero pesado |
| **DonTorrent** | Reevaluar viabilidad | Provider muy limitado |
