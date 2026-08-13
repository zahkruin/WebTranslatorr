# Estrategia: OceanOfPDF

## Provider ID: `oceanofpdf`

## Propósito

Documenta la estrategia de scraping para OceanOfPDF (`oceanofpdf.com`), un repositorio WordPress de libros en inglés. Estrategia híbrida: intenta la WordPress REST API primero para búsqueda estructurada, con fallback automático a scraping HTML si la API no está expuesta o no devuelve resultados.

## URLs del Sitio

| Componente | Patrón URL | Ejemplo |
|------------|------------|---------|
| Búsqueda (API) | `/wp-json/wp/v2/posts?search={query}` | `https://oceanofpdf.com/wp-json/wp/v2/posts?search=dune` |
| Búsqueda (HTML) | `/?s={query}` | `https://oceanofpdf.com/?s=dune` |
| Detalle (slug) | `/{slug}/` | `https://oceanofpdf.com/dune-frank-herbert/` |
| Detalle (ID numérico) | `/?p={id}` | `https://oceanofpdf.com/?p=12345` |
| Descarga | Enlaces directos a PDF/EPUB/MOBI/AZW3/FB2 | Variable |

## Requisitos Especiales

- **CMS WordPress:** Soporta tanto REST API como scraping HTML estándar de WordPress.
- **WordPressApiClient:** Usa `WordPressApiClient` para búsqueda vía REST API y modo browse.
- **Sin Cloudflare:** `use_scraper=False` — el sitio no tiene protección anti-bot.
- **Sin JS, sin login, sin CAPTCHA:** Acceso completamente abierto.
- **Idioma:** `query_language="en"` — todos los títulos están en inglés.
- **DomainResolver:** Soporta resolución dinámica de dominio.
- **REST API opcional:** La API puede no estar expuesta. El provider maneja el fallback transparentemente.

## Constructor

```python
def __init__(self, http_client, domain_resolver=None):
    domain = settings.OCEANOFPDF_DOMAIN
    if domain_resolver:
        active_domain = domain_resolver.get_current("oceanofpdf")
        if active_domain:
            domain = active_domain

    super().__init__(
        provider_id="oceanofpdf",
        display_name="OceanOfPDF",
        base_url=domain,
        http_client=http_client,
        categories=[7000, 7020, 8000, 8010],
        query_language="en",
    )

    # WordPress REST API client
    self._api = WordPressApiClient(
        http_client=http_client,
        base_url=domain,
        provider_id=self.provider_id,
        requires_scraper=False,
        per_page=20,
    )
```

## Capacidades

```python
def get_capabilities(self) -> ProviderCapabilities:
    return ProviderCapabilities(
        provider_id=self.provider_id,
        display_name=self.display_name,
        supported_categories=[7000, 7020, 8000, 8010],
        supported_search_params=["q", "author", "title"],
        supports_book_search=True,
    )
```

## Estrategia de Búsqueda (`search()`)

### Arquitectura híbrida API-first

```python
# Strategy 1: WordPress REST API (preferida)
if self._USE_API:
    try:
        api_results = await self._api.search(query_to_use, limit=limit, offset=offset)
        if api_results:
            return api_results  # Estructurados, con author, fecha, etc.
    except Exception as e:
        self.logger.warning(f"OceanOfPDF API fallback: {e}")

# Strategy 2: HTML scraping (fallback)
self.logger.info("OceanOfPDF: falling back to HTML scraping")
return await self._search_scrape(query_to_use, offset, limit)
```

### Strategy 1 — WordPress REST API (`WordPressApiClient`)

La API devuelve JSON estructurado con:
- `title.rendered` → título
- `link` → URL del post
- `id` → ID numérico de WordPress
- `date` → fecha de publicación
- `_embedded.author[0].name` → autor

El `WordPressApiClient` construye `SearchResult` directamente desde la respuesta JSON, eliminando HTML del título y extrayendo el autor.

### Strategy 2 — HTML Scraping (fallback)

#### Construir URL
```python
search_url = f"{self.base_url}/?s={query_to_use}"
```

#### Selectores CSS (estándar WordPress)

```python
soup.select(
    "article.post h2.entry-title a, "
    "article.type-post h2.entry-title a, "
    "article.post .entry-title a, "
    "h2.entry-title a, h3.entry-title a, "
    "a[rel='bookmark']"
)
```

#### Filtrado de enlaces no-libro

Se excluyen sistemáticamente:
- URLs con `/category/`, `/tag/`, `/author/`, `/page/`
- URLs con `wp-content`, `wp-admin`, `wp-login`
- URLs de redes sociales (`facebook`, `twitter`, `instagram`)
- URLs con `javascript:`, `#comment`, `#respond`
- Títulos genéricos: `home`, `inicio`, `read more`, `leer más`, `contact`, `contacto`, `about`, `privacy policy`

#### Extracción de Internal ID

```python
@staticmethod
def _extract_internal_id(href: str, title: str) -> str:
    # 1. ID numérico desde query param: ?p=12345
    num_match = re.search(r"[?&]p=(\d+)", href)
    if num_match:
        return num_match.group(1)

    # 2. ID numérico al final del path: /12345/
    num_match = re.search(r"/(\d+)/?$", href.rstrip("/"))
    if num_match:
        return num_match.group(1)

    # 3. Slug del último segmento (limpiando query/fragment)
    path = href.rstrip("/").split("/")[-1]
    path = re.sub(r"[?#].*$", "", path)

    # 4. Fallback: slugify del título
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or title.replace(" ", "-").lower()
```

#### Extracción de Autor (desde HTML)

**Desde metadatos del contenedor:**

```python
def _extract_author_from_meta(parent_elem):
    # Selectores: .entry-author, .author, .byline .author, span.author, a.url.fn
    author_span = parent_elem.select_one(".entry-author, .author, .byline .author, span.author, a.url.fn")

    # Fallback: "by Author Name" en .entry-meta
    meta_div = parent_elem.select_one(".entry-meta, .post-meta")
    if meta_div:
        by_match = re.search(r"(?:by|By|por|Por)\s+([A-Z][\w\s.'\-]+?)(?:\s*(?:on|en|,|$|\.))", meta_text)
```

**Desde el título (fallback):**

```python
def _extract_author_from_title(title_text):
    # Patrones: "Title | Author", "Title – Author", "Title — Author", "Title by Author"
    # Si se detecta un autor, se limpia del título con _clean_title()
```

#### Construcción de SearchResult

```python
result = SearchResult(
    title=title_text,          # Limpio si se extrajo autor del título
    guid=f"oceanofpdf-{internal_id}",
    link=link_full,
    download_url=(
        f"{settings.EXTERNAL_URL}/api/download"
        f"?provider={self.provider_id}"
        f"&id={internal_id}"
        f"&fmt=epub"
    ),
    size_bytes=2000000,
    pub_date=datetime.now(),
    categories=[7000, 7020, 8000, 8010],
    description=f"Book: {title_text} | by {book_author}" if book_author else f"Book: {title_text}",
    author=book_author,
)
```

## Estrategia de Descarga (`get_download_url()`)

### Flujo multi-candidato con resolución de slug:

OceanOfPDF soporta dos formatos de `internal_id`: slug (del scraping HTML) o ID numérico (de la REST API). El provider construye múltiples URLs candidatas y las prueba secuencialmente:

```python
candidates: list[str] = []

# Si el ID es numérico → intentar resolver slug vía API
if internal_id.isdigit():
    candidates.append(f"{self.base_url}/?p={internal_id}")
    try:
        api_resp = await self.http_client.get(
            f"{self.base_url}/wp-json/wp/v2/posts/{internal_id}"
        )
        slug = post.get("slug", "")
        if slug:
            candidates.insert(0, f"{self.base_url}/{slug}/")
    except Exception:
        pass

# Siempre intentar slug-based
candidates.append(f"{self.base_url}/{internal_id}/")
candidates.append(f"{self.base_url}/{internal_id}")

# Deducplicar preservando orden
```

### Búsqueda del enlace de descarga (`_find_download_link()`):

#### Strategy 1 — Extensiones de archivo directas:
```python
for a in soup.find_all("a", href=True):
    if href.lower().endswith((".epub", ".pdf", ".mobi", ".azw3", ".fb2")):
        return normalize(href)
```

#### Strategy 2 — Botones de descarga por texto:
```python
for a in soup.find_all("a", href=True):
    text = a.get_text(strip=True).lower()
    if any(w in text for w in (
        "download", "descargar", "descarga",
        "epub", "pdf", "mobi", "get book", "free download"
    )):
        # Saltar enlaces de login/register/comment
        if any(skip in href.lower() for skip in ("wp-login", "register", "login", "comment")):
            continue
        return normalize(href)
```

#### Strategy 3 — Href contiene "download":
```python
for a in soup.find_all("a", href=True):
    if "download" in href.lower() or "descargar" in href.lower():
        return normalize(href)
```

### Formatos Soportados

| Formato | Extensión | Prioridad |
|---------|-----------|-----------|
| EPUB | `.epub` | Default (`fmt=epub` en download_url) |
| PDF | `.pdf` | Bajo demanda |
| MOBI | `.mobi` | Disponible |
| AZW3 | `.azw3` | Disponible |
| FB2 | `.fb2` | Disponible |

## Modo Browse (`browse()`)

Usa WordPressApiClient para obtener los posts más recientes:

```python
async def browse(self, categories=None, *, offset=0, limit=50, **kwargs):
    return await self._api.list_recent(limit=limit, offset=offset)
```

Útil cuando Readarr hace sync sin query de búsqueda (`t=book` sin `q=`).

## Manejo de Errores

- **`search()` — API error:** Captura excepción del `WordPressApiClient`, loguea warning, y cae automáticamente en scraping HTML.
- **`search()` — Scraping error:** Excepción capturada → `self.logger.error()` + return `[]`
- **`get_download_url()` — ID numérico sin API:** Intenta resolver el slug vía API interna; si falla, continúa con URL slug-based.
- **`get_download_url()` — 404 en candidato:** `if resp.status_code == 404: continue` — prueba el siguiente candidato.
- **`get_download_url()` — Sin enlace:** Tras probar todas las URLs candidatas y estrategias → `self.logger.warning()` + return `None`
- **`browse()` — API error:** Captura excepción → `self.logger.warning()` + return `[]`

## Trampas / Problemas Conocidos

1. **La REST API puede no estar expuesta** — El provider maneja esto con fallback transparente a HTML scraping. Si las búsquedas empiezan a fallar, verificar si la API fue deshabilitada.
2. **Auto-extracción del autor del título** — Los títulos en OceanOfPDF suelen incluir el autor (`"Dune | Frank Herbert"`). El provider limpia el título y extrae el autor separadamente. Esto puede fallar si el formato cambia.
3. **Múltiples formatos de internal_id** — La descarga debe manejar tanto IDs numéricos (API) como slugs (scraping). El fallback con múltiples URLs candidatas es necesario.
4. **Falso positivo en enlaces de navegación** — El texto "download", "pdf", "epub" puede aparecer en enlaces de categoría o tags. Los filtros de exclusión (`/category/`, `/tag/`, etc.) son críticos.
5. **Selectores WordPress estándar** — Si OceanOfPDF cambia de tema o abandona WordPress, los selectores `article.post h2.entry-title a` y `a[rel='bookmark']` dejarán de funcionar.
6. **Per_page fijo en 20** — La paginación de la API usa `per_page=20`, lo que puede requerir múltiples requests para búsquedas con muchos resultados.

## Archivos

- `app/providers/books/oceanofpdf.py`
- `app/scraping/wp_api_client.py` (WordPressApiClient)
- `tests/test_provider_oceanofpdf.py`
