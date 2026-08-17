# Plan de Integración: 8 Nuevos Proveedores para WebTranslatorr

## Resumen Ejecutivo

Este plan detalla la incorporación de 8 fuentes de libros y torrents a WebTranslatorr, agrupadas en tres categorías según su naturaleza: grandes repositorios académicos/generales, bibliotecas EPUB en español con WordPress, y trackers de torrent.

**Proveedores ya implementados (no requieren desarrollo nuevo):**
- **LibGen** (Library Genesis) → `app/providers/books/libgen.py` ✓
- **Z-Library** → `app/providers/books/zlibrary.py` ✓

**Proveedores a implementar (6 nuevos):**
- **Epubgratis** (epubgratis.org) → WordPress + HTML híbrido → Libros EPUB/PDF/MOBI
- **Ebiblioteca** (ebiblioteca.org) → Custom PHP, sin registro → Libros EPUB/PDF/DOC
- **Bajaebooks** (bajaebooks.info) → Custom HTML, sin registro → Libros EPUB/PDF
- **LeLibros** (lelibros.online) → Custom HTML, servidor propio → Libros EPUB/PDF/MOBI
- **DivxTotal** (divxtotal.wtf) → Torrent tracker → Series/Películas
- **EliteTorrent** (elitetorrent.com) → Torrent tracker → Series/Películas

---

## 1. ANÁLISIS INDIVIDUAL DE CADA SITIO

### 1.1 LibGen (Library Genesis) — YA IMPLEMENTADO
**Archivo:** `app/providers/books/libgen.py` (203 líneas)

| Aspecto | Detalle |
|---------|---------|
| **URL base** | `https://libgen.ee` (configurable via `WTR_LIBGEN_DOMAIN`) |
| **Búsqueda** | `GET /search.php?req={query}&lg_topic=libgen&open=0&view=simple&res=25&phrase=1&column=def` |
| **Resultados** | Tabla HTML (`table.c`) con columnas: autor, título, año, tamaño, extensión, MD5 |
| **ID interno** | MD5 hash de 32 caracteres hexadecimales |
| **Detalle** | `/book/index.php?md5={MD5}` — página con múltiples mirrors de descarga |
| **Descarga** | Construcción directa `/main/{XX}/{MD5}` + búsqueda de mirrors en la página de detalle |
| **Autenticación** | Ninguna requerida |
| **CAPTCHAs** | No detectados |
| **Cloudflare** | Parcial (usa `use_scraper=True`) |
| **Paginación** | No implementada (25 resultados) |
| **Tamaños** | Parseo KB/MB/GB a bytes |
| **Formatos** | pdf, epub, mobi, djvu, fb2, txt |
| **Estado** | ✓ Completo, operativo |

### 1.2 Z-Library — YA IMPLEMENTADO
**Archivo:** `app/providers/books/zlibrary.py` (248 líneas)

| Aspecto | Detalle |
|---------|---------|
| **URL base** | `https://z-library.sk` (dominio muy inestable, usa DomainResolver) |
| **Búsqueda** | 3 patrones de URL intentados secuencialmente: `/s/{query}/?language=es&ext=epub`, `/s/{query}?language=spanish&ext=epub`, `/search?q={query}&lang=es` |
| **Resultados** | Parseo dual: cards (`div[class*="book"]`, `div[class*="card"]`), fallback a enlaces `/book/{id}` |
| **ID interno** | ID numérico extraído de `/book/{id}` |
| **Detalle** | `/book/{id}` — página con botones de descarga |
| **Descarga** | 4 patrones URL intentados: `/book/{id}/download`, `/book/{id}`, `/d/{id}`, `/dl/{id}` + búsqueda de botones CSS |
| **Autenticación** | Ninguna para búsqueda (Z-Library puede requerir login en ciertos momentos) |
| **CAPTCHAs** | Ocasionalmente Cloudflare Turnstile |
| **Cloudflare** | Sí (`use_scraper=True`) |
| **Dominios** | Registrado en DomainResolver con patrón `z-library\.\w+|singlelogin\.\w+` |
| **Formatos** | epub, mobi, pdf, azw3, fb2, djvu, txt |
| **Estado** | ✓ Completo, operativo. Riesgo alto de caídas por cambios de dominio. |

**Recomendación para ambos:** Mantener los providers existentes. Añadir monitoreo de salud mejorado y ampliar paginación para LibGen.

### 1.3 Epubgratis (epubgratis.org)

| Aspecto | Detalle |
|---------|---------|
| **URL base** | `https://www.epubgratis.org` (Cloudflare) |
| **Plataforma** | WordPress con tema personalizado `epubgratis-pro` |
| **WP REST API** | Expuesta en `/wp-json/` (confirmado por header `Link: <https://wvw.epubgratis.org/wp-json/>`) |
| **Búsqueda HTML** | `/?s={query}` (estándar WordPress) |
| **Búsqueda API** | `/wp-json/wp/v2/posts?search={query}&per_page=20` |
| **Resultados** | Cards de libros con portada, título, autor. Estructura de custom post type `epub_directory` (plugin detectado: `epub-directory`) |
| **Navegación** | Por autor (índice alfabético), género, colecciones, búsqueda por barra lateral |
| **Detalle** | Página individual del post con sinopsis expandible, metadatos, enlaces de descarga |
| **Descarga** | 2 tipos: enlaces públicos (sin registro) y privados (requieren registro). Links a servidores externos (ZippyShare, Uploaded, Cloud). Redirección con espera de 6 segundos + botón "CONTINUAR" |
| **Autenticación** | Registro gratuito para enlaces privados (plugin: `zm-ajax-login-register`) |
| **CAPTCHAs** | No detectados en el sitio principal. Uploaded (servidor externo) pide CAPTCHA. |
| **Cloudflare** | Sí |
| **Formatos** | EPUB (principal), PDF, MOBI |
| **Particularidades** | Usa plugin `epub-directory` que puede exponer CPT vía REST API. Tema custom con Foundation CSS. Enlaces de descarga ocultos tras toggle ("hacer click para mostrar"). |

**Estrategia de integración:**
1. **Enfoque híbrido WP API + HTML scraping** (mismo patrón que `Epubflix1Provider` y `LectuEpubLibre5Provider`)
2. Intentar primero `/wp-json/wp/v2/posts?search={query}&per_page=20&_embed`
3. Si la API falla o devuelve vacío, fallback a `/?s={query}` con HTML scraping
4. Para la descarga: parsear la página de detalle buscando enlaces públicos (evitar enlaces privados que requieren login)
5. Mapear el CPT `epub_directory` si está expuesto vía REST

**Clase propuesta:** `EpubgratisProvider(BaseProvider)` con `_use_wp_api` como flag interno.

### 1.4 Ebiblioteca (ebiblioteca.org)

| Aspecto | Detalle |
|---------|---------|
| **URL base** | `https://ebiblioteca.org` |
| **Plataforma** | PHP custom (no WordPress). Diseño tipo catálogo con IDs numéricos. |
| **Catálogo** | ~177,000 títulos |
| **Búsqueda** | Probablemente `GET /?search={query}` o similar. Tiene barra de búsqueda superior. |
| **Resultados** | Lista paginada: "Registros desde 1 hasta 10, de un total de 177.348". Vista en modo "Detalle" (cards con info) o "Lista" (solo nombres). Cada card muestra: título, autor, tamaño, género, fecha. |
| **Navegación** | Por novedades, favoritos, autores (alfabético), títulos, géneros (sidebar izquierda con categorías) |
| **Detalle** | Página con sinopsis extensa, biografía del autor, botones de descarga |
| **Descarga** | Varios botones de descarga que redirigen a páginas con anuncios → "Completar e ir a la página de descarga" → "Descargar". Archivo ZIP con PDF + EPUB + TXT dentro. |
| **Autenticación** | NO requiere registro |
| **CAPTCHAs** | No detectados |
| **Cloudflare** | No confirmado (hosting en OVH) |
| **Formatos** | EPUB, PDF, TXT (descargados como ZIP que contiene los 3) |

**Estrategia de integración:**
1. **HTML scraping puro** con BeautifulSoup
2. Construir URL de búsqueda (requiere investigación: probablemente query param o POST)
3. Parsear la tabla/lista de resultados con soporte para ambas vistas (detalle y lista)
4. Extraer IDs internos y metadatos (tamaño, género, fecha)
5. Para la descarga: navegar la cadena de redirección con anuncios, extraer enlace final al ZIP
6. Usar `ZipExtractor` existente (`app/utils/zip_extractor.py`) para extraer el EPUB del ZIP
7. Marcar con `is_zipped = True`

**Clase propuesta:** `EbibliotecaProvider(BaseProvider)` con `is_zipped = True`.

**Precaución:** La URL de búsqueda exacta y los selectores CSS deben determinarse mediante inspección directa del sitio. El dominio `ebiblioteca.org` podría tener variaciones regionales.

### 1.5 Bajaebooks (bajaebooks.info / bajaebooks.com)

| Aspecto | Detalle |
|---------|---------|
| **URL base** | `https://bajaebooks.info` (principal), `bajaebooks.com` (alternativo) |
| **Plataforma** | HTML estático/semi-estático con Plesk |
| **Catálogo** | ~31,000 títulos |
| **Búsqueda** | Barra de búsqueda superior (método exacto a investigar, probablemente `/?s={query}` o POST) |
| **Navegación** | Por autores (A-Z), géneros, series. Secciones: "Últimos agregados", "Más leídos hoy", "Más leídos semana", "Más leídos mes", "Más leídos siempre" |
| **Resultados** | Cards con portada, título, autor, género. Listados alfabéticos de autores y géneros. |
| **Detalle** | Página con sinopsis, portada, botón azul de descarga |
| **Descarga** | Click en botón azul → popup con anuncio → redirección a página de descarga. Mayoría EPUB, algunos PDF. |
| **Autenticación** | NO requiere registro para descargar. Registro solo para leer online. |
| **CAPTCHAs** | No detectados |
| **Cloudflare** | Sí (DNS cloudflare) |
| **HTTPS** | No implementado en bajaebooks.com (HTTP solamente). bajaebooks.info sí tiene HTTPS. |
| **Formatos** | EPUB (principal), PDF |

**Estrategia de integración:**
1. **HTML scraping puro** con BeautifulSoup
2. Preferir `bajaebooks.info` (HTTPS). Si no responde, fallback a `bajaebooks.com`.
3. Construir URL de búsqueda con query parameter
4. Parsear resultados de cards con selectores CSS específicos
5. Para la descarga: seguir la cadena de redirección (popup → página de descarga real)
6. Considerar que el sitio usa HTTP sin SSL en el dominio `.com` — verificar compatibilidad con el HttpClient

**Clase propuesta:** `BajaebooksProvider(BaseProvider)` con fallback multi-dominio.

### 1.6 LeLibros (lelibros.online)

| Aspecto | Detalle |
|---------|---------|
| **URL base** | `https://lelibros.online` (Cloudflare) |
| **Plataforma** | PHP/HTML custom. Sitio propio, sin plataforma estándar. |
| **Catálogo** | ~5,000 títulos |
| **Búsqueda** | Barra de búsqueda superior con placeholder "BUSQUE". Mecanismo interno a investigar (probable AJAX/live search). |
| **Resultados** | Grid de portadas con título y autor. Cada resultado enlaza a página de detalle. |
| **Navegación** | 3 categorías principales: "Literatura e ficción" (con 12 subgéneros), "Técnicos e académicos", "Vida práctica y otros". |
| **Detalle** | Página con portada grande (izquierda), metadatos (título, autor, editorial, género, páginas, valoración), sinopsis, 4 botones de descarga |
| **Descarga** | 4 botones directos: "Descargar en PDF", "Descargar en EPUB", "Descargar en MOBI", "Leer Online". Archivos en servidor propio (sin acortadores ni intermediarios). |
| **Autenticación** | NO requiere registro para descargar |
| **CAPTCHAs** | No detectados |
| **Cloudflare** | Sí |
| **Formatos** | EPUB, PDF, MOBI (descarga directa desde servidor propio) |
| **Particularidades** | Sitio bloqueado judicialmente en España (2020). Puede cambiar de dominio frecuentemente. Las descargas son directas sin publicidad. |

**Estrategia de integración:**
1. **HTML scraping puro** con BeautifulSoup
2. Requiere investigación de la URL de búsqueda (posible `/?s={query}` o endpoint AJAX)
3. Parsear grid de resultados — selectores CSS basados en la estructura observada
4. Para la descarga: el sitio tiene botones directos con URLs al archivo → **integración más limpia de todas**, sin redirecciones ni anuncios
5. Extraer el enlace del botón correspondiente al formato solicitado
6. Configurar DomainResolver por cambios frecuentes de dominio

**Clase propuesta:** `LeLibrosProvider(BaseProvider)` — probablemente el más simple de implementar de los nuevos.

**Nota legal:** Este sitio ha sido objeto de bloqueo judicial en España. El provider debe documentar que depende de la disponibilidad del dominio.

### 1.7 DivxTotal (divxtotal.wtf)

| Aspecto | Detalle |
|---------|---------|
| **URL base** | `https://divxtotal.wtf` (cambia frecuentemente: `.lol`, `.wtf`, `.io`, `.mov`, `.zip`, `.win`, `.wf`, `.pl`, `.cat`, `.fi`, `.dev`, `.ac`, `.re`, `.pm`, `.nl`) |
| **Tipo** | Torrent tracker — **VIDEO, no libros** |
| **Plataforma** | PHP custom con HTML server-side rendering |
| **Contenido** | Películas (21,655+), Series (7,088+), Series HD (2,865+) |
| **Búsqueda** | `GET /buscar/{query}/page/{n}` |
| **Resultados** | Tarjetas con imagen, título, tipo (película/serie), badges. Paginación con `<ul class="pagination">`. Total de resultados mostrado. |
| **Detalle** | `/pelicula/{id}/{slug}` o `/serie/{id}/{slug}` con metadatos completos |
| **Descarga** | Página de detalle contiene enlaces magnet y archivos `.torrent`. Información: tamaño, seeds, peers, calidad, idioma, fecha. |
| **Autenticación** | Ninguna requerida |
| **CAPTCHAs** | No detectados |
| **Cloudflare** | Sí (requiere `use_scraper=True` con bypass) |
| **Paginación** | 10 resultados por página. Navegación numérica. |
| **Particularidades** | Dominio extremadamente inestable (lista de 18+ dominios históricos). Usa CDN externo para imágenes (`images.weserv.nl`). |

**Estrategia de integración:**
1. **HTML scraping puro** con soporte para paginación
2. Mismo patrón que `MejorTorrentProvider` (331 líneas): búsqueda → enriquecimiento por página de detalle → extracción magnet/torrent
3. Construir URL: `{base}/buscar/{query}/page/{n}`
4. Parsear resultados de cards con selectores específicos
5. Extraer metadatos de calidad (HD/4K), tamaño, seeds, peers de la página de detalle
6. Resolver el magnet link o archivo .torrent (regex: `href=["\'].+?\.torrent["\']`)
7. **IMPORTANTE:** Al ser video, debe registrarse como `supports_movie_search=True, supports_tv_search=True`, NO como book provider
8. Registrar en SmartRouter como video provider
9. DomainResolver imperativo dada la inestabilidad extrema del dominio (18+ dominios históricos)

**Clase propuesta:** `DivxtotalProvider(BaseProvider)` en `app/providers/video/divxtotal.py`.

**Dependencia:** Requiere implementar soporte para magnet links y archivos .torrent en el sistema de descarga (actualmente el `download_proxy` asume descarga directa de archivos de libro).

### 1.8 EliteTorrent (elitetorrent.com)

| Aspecto | Detalle |
|---------|---------|
| **URL base** | `https://www.elitetorrent.com` |
| **Tipo** | Torrent tracker — **VIDEO, no libros** |
| **Plataforma** | Custom PHP |
| **Contenido** | Películas y Series en HD (4K, 1080p, 720p, MicroHD) |
| **Búsqueda** | `GET /?s={query}` — búsqueda WordPress-style |
| **Resultados** | Sistema de páginas con `<a class="pagina">`. Cards/items con enlace a detalle. Filtros por año de estreno, calidad, idioma. |
| **Detalle** | Página individual con metadatos: título, calidad, idioma, tamaño, fecha, seeds, peers |
| **Descarga** | Magnet link o archivo .torrent en la página de detalle |
| **Autenticación** | Ninguna requerida |
| **CAPTCHAs** | No detectados |
| **Cloudflare** | No confirmado |
| **Paginación** | Sistema con `paginacion` class, URLs `/page/{n}/?s={query}` |
| **Particularidades** | Catálogo con más de 10 años de trayectoria. Filtros avanzados por año, calidad e idioma en la interfaz. |

**Estrategia de integración:**
1. **HTML scraping puro** con soporte para paginación (máximo 2 páginas para no saturar)
2. Mismo patrón que `MejorTorrentProvider`
3. Construir URL de búsqueda: `{base}/?s={query}`
4. Determinar número de páginas desde `paginacion`
5. Para cada página: `{base}/page/{n}/?s={query}`
6. Parsear enlaces a `/peliculas/{slug}/` y `/series/{slug}/`
7. Visitar detalle para extraer: título, calidad, idioma, tamaño, seeds, peers, fecha, magnet/torrent
8. Mapeo de calidad → categorías Newznab (HD→2045, 4K→2045, etc.)
9. Extraer magnet link vía regex: `i=[-A-Za-z0-9+/]+={0,3}`
10. **IMPORTANTE:** Al ser video, debe registrarse como `supports_movie_search=True, supports_tv_search=True`

**Clase propuesta:** `EliteTorrentProvider(BaseProvider)` en `app/providers/video/elitetorrent.py`.

**Dependencia compartida con DivxTotal:** Implementar descarga de torrents/magnet en el sistema.

---

## 2. ESTRATEGIA DE INTEGRACIÓN UNIFICADA

### 2.1 Arquitectura de Abstracción

WebTranslatorr ya posee una arquitectura de abstracción sólida. La integración se alinea con los patrones existentes sin requerir cambios estructurales:

```
Capa Torznab (torznab.py)
    ↓
SmartRouter (smart_router.py)
    ↓
ProviderRegistry (registry.py)
    ↓
BaseProvider (ABC) ← Todos los providers heredan de aquí
    ├── BookProviders (buscan en sites de libros)
    │   ├── EpubgratisProvider    ← NUEVO (híbrido WP API + HTML)
    │   ├── EbibliotecaProvider   ← NUEVO (HTML scraping + ZIP)
    │   ├── BajaebooksProvider    ← NUEVO (HTML scraping + redirección)
    │   └── LeLibrosProvider      ← NUEVO (HTML scraping + descarga directa)
    └── VideoProviders (buscan en trackers de torrent)
        ├── DivxtotalProvider     ← NUEVO (HTML scraping + magnet/torrent)
        └── ElitetorrentProvider  ← NUEVO (HTML scraping + magnet/torrent)
```

### 2.2 Infraestructura Compartida Reutilizada

Los 6 nuevos providers aprovecharán infraestructura existente sin duplicar:

| Componente | Uso | Archivo |
|-----------|-----|---------|
| `HttpClient` con cloudscraper | Todos los providers | `app/scraping/http_client.py` |
| `WordPressApiClient` | Epubgratis (híbrido) | `app/scraping/wp_api_client.py` |
| `DomainResolver` + estrategias | DivxTotal, LeLibros, Z-Library | `app/services/domain_resolver.py` |
| `ZipExtractor` | Ebiblioteca (ZIP con EPUB+PDF+MOBI) | `app/utils/zip_extractor.py` |
| `SearchCache` (TTLCache) | Todos automáticamente | `app/services/cache.py` |
| `BaseProvider.normalize_query()` | Todos | `app/providers/base.py` |
| `BaseProvider._combine_query()` | Todos | `app/providers/base.py` |
| `SmartRouter` | Automático por tipo de contenido | `app/routing/smart_router.py` |

### 2.3 Estrategia de Descarga de Torrents (Nuevo)

DivxTotal y EliteTorrent devuelven magnet links y archivos .torrent, no archivos de libro directos. Se requiere una extensión al sistema de descarga actual:

**Opción recomendada:** Devolver el archivo `.torrent` o magnet link directamente al cliente *Arr.

Implementación en `app/api/torznab.py` → `download_proxy()`:
1. Añadir detección de `return_torrent = True` en el provider
2. Si el provider retorna un magnet link (string `magnet:?...`), devolverlo como `302 Redirect`
3. Si retorna un archivo `.torrent`, descargarlo y devolverlo con `Content-Type: application/x-bittorrent`
4. Modificar `SearchResult.download_url` para incluir el magnet link directamente (permitiendo al cliente *Arr manejarlo)

Alternativa más simple (sin modificar download_proxy):
- Incluir `magnet_uri` en el `SearchResult` y construir el `download_url` como el enlace al `.torrent`
- Configurar `info_hash` y `seeders/peers` para compatibilidad Torznab completa
- El cliente *Arr descargará el archivo .torrent, que es manejable con el sistema actual

### 2.4 Patrones de Implementación por Categoría

#### Patrón A: WordPress Híbrido (Epubgratis)

```python
class EpubgratisProvider(BaseProvider):
    def __init__(self, http_client, domain_resolver=None):
        # Inicialización estándar + WordPressApiClient opcional
        self._wp_client = None  # Se inicializa lazy

    async def search(self, query, ...):
        # 1. Intentar WP REST API
        results = await self._search_wp_api(query)
        if results:
            return results
        # 2. Fallback a HTML scraping
        return await self._search_html(query)

    async def _search_wp_api(self, query):
        # GET /wp-json/wp/v2/posts?search={query}&per_page=20&_embed
        # Parsear JSON → SearchResult
        # Mismo patrón que Epubflix1Provider

    async def _search_html(self, query):
        # GET /?s={query}
        # BeautifulSoup: selectores para custom post type epub_directory
        # Parsear cards con portada, título, autor
```

#### Patrón B: HTML Scraping Puro (Ebiblioteca, Bajaebooks, LeLibros)

```python
class EbibliotecaProvider(BaseProvider):
    is_zipped = True  # ⚡ Flag para ZipExtractor

    async def search(self, query, ...):
        url = f"{self.base_url}/?search={quote_plus(query_normalizada)}"
        resp = await self.http_client.get(url, use_scraper=True)
        return self._parse_results(resp.text)

    def _parse_results(self, html):
        # Parsear tabla/lista con detalles (título, autor, tamaño, género, fecha)
        # Cada resultado → SearchResult con download_url proxy

    async def get_download_url(self, internal_id):
        # 1. GET página de detalle
        # 2. Encontrar botón de descarga
        # 3. Seguir redirección (posiblemente múltiples pasos)
        # 4. Retornar URL final del ZIP
```

#### Patrón C: Torrent Tracker (DivxTotal, EliteTorrent)

```python
class DivxtotalProvider(BaseProvider):
    def get_capabilities(self):
        return ProviderCapabilities(
            provider_id="divxtotal",
            display_name="DivxTotal",
            supported_categories=[2000, 2010, 2020, 2030, 2040, 2045, 2050, 5000, 5030, 5040],
            supported_search_params=["q", "imdb_id", "tvdb_id", "season", "episode"],
            supports_movie_search=True,  # ⚡
            supports_tv_search=True,     # ⚡
            supports_book_search=False,  # ⚡
        )

    async def search(self, query, ...):
        url = f"{self.base_url}/buscar/{quote_plus(query)}/page/1"
        resp = await self.http_client.get(url, use_scraper=True)
        # Parsear primera página, determinar total de páginas
        # Enriquecer resultados con páginas de detalle (concurrente, semáforo=3)
        # Extraer magnet links, tamaño, seeds, peers

    async def get_download_url(self, internal_id):
        # internal_id = slug de la película/serie
        # GET página de detalle → extraer magnet link o .torrent URL
        # Retornar URL directa
```

---

## 3. PLAN DE IMPLEMENTACIÓN (FASES)

### Fase 1: Libros Estándar (3 providers) — Prioridad ALTA
**Tiempo estimado:** 4-6 horas por provider

1. **LeLibrosProvider** — El más simple (descarga directa, sin anuncios)
2. **BajaebooksProvider** — Complejidad media (redirección con anuncios)
3. **EpubgratisProvider** — Complejidad media-alta (híbrido WP API + HTML)

### Fase 2: Libros con ZIP + Torrents (3 providers) — Prioridad ALTA
**Tiempo estimado:** 5-8 horas por provider

4. **EbibliotecaProvider** — HTML scraping + extracción ZIP
5. **DivxtotalProvider** — Torrent tracker (requiere soporte magnet/torrent)
6. **EliteTorrentProvider** — Torrent tracker (requiere soporte magnet/torrent)

### Fase 3: Mejoras a Providers Existentes — Prioridad MEDIA
**Tiempo estimado:** 2-3 horas

- Ampliar paginación en LibGen
- Mejorar detección de Cloudflare en Z-Library

### Artefactos por cada provider:

| Artefacto | Ubicación |
|-----------|-----------|
| Clase provider | `app/providers/books/{nombre}.py` o `app/providers/video/{nombre}.py` |
| Configuración | `config.py` (+2 entradas: `_ENABLED` + `_DOMAIN`) |
| Registro | `app/api/torznab.py` → `_init_providers()` |
| DomainResolver | `app/server.py` → `lifespan()` |
| Variables de entorno | `.env.example` (+2 líneas) |
| Tests | `tests/test_{nombre}_provider.py` |

---

## 4. CONFIGURACIÓN Y REGISTRO

### 4.1 Nuevas entradas en `config.py`

```python
# Fase 1 - Book providers
EPUBGRATIS_ENABLED: bool = True
EPUBGRATIS_DOMAIN: str = "https://www.epubgratis.org"
EBIBLIOTECA_ENABLED: bool = True
EBIBLIOTECA_DOMAIN: str = "https://ebiblioteca.org"
BAJAEBOOKS_ENABLED: bool = True
BAJAEBOOKS_DOMAIN: str = "https://bajaebooks.info"
LELIBROS_ENABLED: bool = True
LELIBROS_DOMAIN: str = "https://lelibros.online"

# Fase 2 - Torrent providers (video)
DIVXTOTAL_ENABLED: bool = True
DIVXTOTAL_DOMAIN: str = "https://divxtotal.wtf"
ELITETORRENT_ENABLED: bool = True
ELITETORRENT_DOMAIN: str = "https://www.elitetorrent.com"
```

### 4.2 Registro en `app/server.py` (DomainResolver)

```python
# Fase 1
if settings.EPUBGRATIS_ENABLED:
    resolver.register_provider(DomainConfig(
        provider_id="epubgratis",
        default_domain=settings.EPUBGRATIS_DOMAIN,
        known_domain_pattern=r"epubgratis\.\w+",
    ))
# ... mismo patrón para ebiblioteca, bajaebooks, lelibros

# Fase 2 - Video providers con dominios inestables
if settings.DIVXTOTAL_ENABLED:
    resolver.register_provider(DomainConfig(
        provider_id="divxtotal",
        default_domain=settings.DIVXTOTAL_DOMAIN,
        privtree_path="@divxtotal",
        known_domain_pattern=r"divxtotal\.\w+",
    ))
if settings.ELITETORRENT_ENABLED:
    resolver.register_provider(DomainConfig(
        provider_id="elitetorrent",
        default_domain=settings.ELITETORRENT_DOMAIN,
        known_domain_pattern=r"elitetorrent\.\w+",
    ))
```

### 4.3 Registro en `app/api/torznab.py` (`_init_providers`)

```python
# Fase 1 - Book providers
if settings.EPUBGRATIS_ENABLED:
    from app.providers.books.epubgratis import EpubgratisProvider
    registry.register(EpubgratisProvider(http_client, resolver))

# Fase 2 - Video providers
if settings.DIVXTOTAL_ENABLED:
    from app.providers.video.divxtotal import DivxtotalProvider
    registry.register(DivxtotalProvider(http_client, resolver))
```

---

## 5. MANTENIMIENTO Y GESTIÓN DE CAMBIOS

### 5.1 Estrategia de Monitoreo de Salud

El sistema ya cuenta con `BaseProvider.is_healthy()` y `domain_check_loop()`. Extender:

1. **Health check semántico para cada provider:**
   - Book providers: verificar que la página de búsqueda con query vacío devuelva 200
   - Torrent providers: verificar que la página principal `/` devuelva 200

2. **Métricas en logs:**
   - Tasa de éxito de búsqueda por provider
   - Tasa de éxito de descarga por provider
   - Tiempo medio de respuesta

3. **Alertas proactivas:** Si un provider falla consistentemente (>3 health checks), loggear WARNING con detalles.

### 5.2 DomainResolver — Crítico para DivxTotal, Z-Library, LeLibros

DivxTotal tiene 18+ dominios históricos. Estrategia:

1. **Registrar todos los dominios conocidos** en el `known_domain_pattern`:
   ```
   r"divxtotal\.(wtf|lol|io|mov|zip|win|wf|pl|cat|fi|dev|ac|re|pm|nl)"
   ```

2. **Configurar privtree/Telegram** si existe canal oficial:
   - `privtree_path="@divxtotal"` para scraping de la landing page

3. **Aumentar frecuencia de health check** para providers con dominios inestables (cada 15 min en vez de 30 min)

### 5.3 Cambios en la Estructura HTML de los Sitios

**Estrategia de defensa en profundidad:**

1. **Múltiples selectores CSS por provider** (patrón ya usado en ZLibrary con 2 métodos):
   ```python
   # Intentar selector primario
   results = soup.select('div.book-card')
   if not results:
       # Fallback a selector secundario
       results = soup.select('article.post')
   ```

2. **Detección de cambios estructurales:**
   - Si 0 resultados tras búsqueda válida → loggear WARNING con sample HTML
   - Comparar estructura esperada vs recibida (nº de elementos, clases CSS principales)

3. **Versionado de selectores por provider:**
   - Mantener los selectores como constantes de clase, no hardcodeados
   - Documentar la fecha de último test exitoso

4. **Tests de integración con HTML congelado:**
   - Capturar HTML real de cada sitio
   - Guardar en `tests/fixtures/{provider}_search.html`, `{provider}_detail.html`
   - Tests unitarios validan parseo contra fixtures

### 5.4 Gestión de Errores Específica por Provider

```python
# Clasificación de errores de scraping
class ScrapingErrorSeverity(Enum):
    RETRYABLE = "retryable"      # Timeout, 429, 5xx → reintentar
    STRUCTURAL = "structural"    # HTML cambiado → alertar, no reintentar
    BLOCKED = "blocked"          # Cloudflare/CAPTCHA → esperar y reintentar
    GONE = "gone"                # Sitio caído/dominio expirado → deshabilitar
```

Implementar en cada provider:
```python
async def search(self, query, ...):
    try:
        resp = await self.http_client.get(url, use_scraper=True)
        if resp.status_code == 403:
            self.logger.error(f"Posible bloqueo en {self.provider_id}")
            raise ScrapingError("BLOCKED")
        # ...
    except ScrapingError as e:
        if e.severity == ScrapingErrorSeverity.STRUCTURAL:
            self.logger.critical(f"CAMBIO ESTRUCTURAL en {self.provider_id}: {e}")
        return []
```

---

## 6. PRUEBAS

### 6.1 Tests Unitarios por Provider

```python
# tests/test_epubgratis_provider.py
class TestEpubgratisProvider:
    async def test_search_parses_results(self):
        html = load_fixture("epubgratis_search.html")
        # Mock HttpClient, verificar SearchResult

    async def test_get_download_url_resolves(self):
        html = load_fixture("epubgratis_detail.html")
        # Mock HttpClient, verificar URL final

    async def test_search_handles_empty_results(self):
        # HTML sin resultados → retorna []

    async def test_search_handles_cloudflare_block(self):
        # HTTP 403 → retorna [] sin excepción
```

### 6.2 Fixtures HTML

```
tests/fixtures/
├── epubgratis_search.html
├── epubgratis_detail.html
├── ebiblioteca_search.html
├── ebiblioteca_detail.html
├── bajaebooks_search.html
├── lelibros_search.html
├── divxtotal_search.html
├── divxtotal_detail.html
├── elitetorrent_search.html
└── elitetorrent_detail.html
```

---

## 7. RIESGOS Y MITIGACIONES

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| DivxTotal cambia de dominio | Muy alta | Alto | DomainResolver con patrón amplio + 18 dominios históricos |
| Z-Library requiere login | Media | Alto | Detectar página de login y loggear WARNING, no reintentar |
| Ebiblioteca cambia estructura HTML | Media | Medio | Múltiples selectores CSS + tests con fixtures |
| LeLibros bloqueado judicialmente | Alta | Bajo | Documentado como limitación conocida. El provider retorna [] si no accesible. |
| Bajaebooks sin HTTPS | Alta | Bajo | Preferir dominio .info (HTTPS). Fallback a .com solo si es necesario. |
| Cloudflare bloquea scraping | Media | Alto | HttpClient ya usa cloudscraper. Añadir delays aleatorios entre requests. |
| Epubgratis enlaces privados requieren login | Alta | Bajo | Solo scrapeamos enlaces públicos. Si no hay, retornamos sin descarga. |
| Torrents sin seeds | Media | Medio | Solo incluir resultados con seeders > 0 (patrón de MejorTorrent). |
| Magnet links no soportados por *Arr | Baja | Medio | Incluir también enlace al archivo .torrent como fallback. |

---

## 8. MÉTRICAS DE ÉXITO

| Provider | Resultados esperados por búsqueda | Tiempo de respuesta | Tasa de descarga exitosa |
|----------|----------------------------------|---------------------|-------------------------|
| Epubgratis | 10-20 | <5s (API) / <8s (HTML) | >80% (enlaces públicos) |
| Ebiblioteca | 10-50 | <10s | >70% (navegación de anuncios) |
| Bajaebooks | 10-30 | <8s | >70% |
| LeLibros | 5-20 | <5s | >90% (descarga directa) |
| DivxTotal | 10-40 | <12s (enriquecimiento) | >80% |
| EliteTorrent | 10-30 | <12s (enriquecimiento) | >80% |

---

## 9. RESUMEN DE TAREAS DE IMPLEMENTACIÓN

### Inmediatas (Fase 1 + 2):
1. [ ] Crear `EpubgratisProvider` en `app/providers/books/epubgratis.py`
2. [ ] Crear `EbibliotecaProvider` en `app/providers/books/ebiblioteca.py`
3. [ ] Crear `BajaebooksProvider` en `app/providers/books/bajaebooks.py`
4. [ ] Crear `LeLibrosProvider` en `app/providers/books/lelibros.py`
5. [ ] Crear `DivxtotalProvider` en `app/providers/video/divxtotal.py`
6. [ ] Crear `EliteTorrentProvider` en `app/providers/video/elitetorrent.py`
7. [ ] Añadir configuración en `config.py` (12 entradas)
8. [ ] Registrar en `app/api/torznab.py` → `_init_providers()`
9. [ ] Registrar DomainResolver en `app/server.py` → `lifespan()`
10. [ ] Actualizar `.env.example` (12 líneas)
11. [ ] Implementar soporte magnet/torrent en `download_proxy()` si se requiere
12. [ ] Tests unitarios para cada provider (6 archivos)
13. [ ] Capturar y guardar fixtures HTML de cada sitio
14. [ ] Actualizar `.gemini/context/providers.md` con estrategias de los nuevos providers
