# Estrategia: BookSee

## Provider ID: `booksee`

## Propósito

Documenta la estrategia de scraping para BookSee (`en.booksee.org`), un repositorio de libros en inglés con 2.4M de títulos. HTML scraping puro, sin protecciones anti-bot. Sirve enlaces directos a PDF.

## URLs del Sitio

| Componente | Patrón URL | Ejemplo |
|------------|------------|---------|
| Búsqueda | `/?q={query}&page=1` | `https://en.booksee.org/?q=dune&page=1` |
| Detalle | `/book/{internal_id}/` | `https://en.booksee.org/book/12345/` |
| Descarga | Enlace directo a PDF en página de detalle | Variable |
| Homepage (browse) | `/` | `https://en.booksee.org/` |

## Requisitos Especiales

- **Sin Cloudflare:** `use_scraper=False` — el sitio no tiene protección anti-bot.
- **Sin JS, sin login, sin CAPTCHA:** Acceso completamente abierto.
- **Modo browse:** Implementa `browse()` usando el scraping de la homepage para soportar RSS y syncs sin query.
- **Idioma:** `query_language="en"` — todos los títulos están en inglés.
- **DomainResolver:** Soporta resolución dinámica de dominio.

## Constructor

```python
def __init__(self, http_client, domain_resolver=None):
    domain = settings.BOOKSEE_DOMAIN
    if domain_resolver:
        active_domain = domain_resolver.get_current("booksee")
        if active_domain:
            domain = active_domain

    super().__init__(
        provider_id="booksee",
        display_name="BookSee",
        base_url=domain,
        http_client=http_client,
        categories=[7000, 7020, 8000, 8010],
        query_language="en",
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

### 1. Construir URL

```python
combined_query = self._combine_query(query, author, title)
query_to_use = self.normalize_query(combined_query)
search_url = f"{self.base_url}/?q={query_to_use}&page=1"
```

Usa `_combine_query()` del BaseProvider para fusionar query, author y title en un solo string.

### 2. Selectores CSS (con fallback en cascada)

Los contenedores de resultados se seleccionan con múltiples intentos:

```python
book_containers = (
    soup.select("div.book-item")
    or soup.select("table.results tr")
    or soup.select("div.result-item")
    or soup.select("article.book")
    or soup.select("div[class*='book']")
)
```

Para cada contenedor, se extraen los siguientes campos:

| Campo | Selector primario | Fallbacks |
|-------|------------------|-----------|
| Título + enlace | `h3 a` | `h3`, `a.title`, `a[class*='title']`, `a[href*='/book/']` |
| Enlace detalle | Del elemento título (si es `<a>`) | `a[href*='/book/']` más cercano |
| Autor | `span.author` | `[class*='author']`, `span[itemprop='author']` |

### 3. Extracción de Internal ID

```python
@staticmethod
def _extract_internal_id(href: str) -> str | None:
    # Pattern: /book/{slug}/ o /book/{id}/
    match = re.search(r"/book/([^/?#]+)", href)
    if match:
        return match.group(1)

    # Fallback: último segmento del path
    parts = [p for p in href.rstrip("/").split("/") if p and p != "book"]
    if parts:
        return parts[-1]

    return None
```

### 4. Construcción de SearchResult

```python
result = SearchResult(
    title=title_text,
    guid=f"booksee-{internal_id}",
    link=link_full,
    download_url=(
        f"{settings.EXTERNAL_URL}/api/download"
        f"?provider={self.provider_id}&id={internal_id}&fmt=pdf"
    ),
    size_bytes=2000000,
    pub_date=datetime.now(),
    categories=[7000, 7020, 8000, 8010],
    description=description,
    author=author_text,
)
```

### 5. Deduplicación

Usa `seen_ids: set[str]` para deduplicar por `internal_id`. Los resultados se limitan a `min(limit, len(book_containers))`.

## Estrategia de Descarga (`get_download_url()`)

### Flujo de 1 paso (scrapeo de página de detalle):

```python
detail_url = f"{self.base_url}/book/{internal_id}/"
resp = await self.http_client.get(detail_url, use_scraper=False)
soup = BeautifulSoup(resp.text, "lxml")
```

### Estrategias de búsqueda del enlace PDF (en orden):

**Strategy 1 — Atributo `download`:**
```python
for a in soup.find_all("a", href=True, download=True):
    href = a["href"]
    # Normalizar URL relativa
    if href.startswith("/") and not href.startswith("//"):
        return f"{self.base_url}{href}"
    if href.startswith("http"):
        return href
```

**Strategy 2 — Extensión `.pdf`:**
```python
for a in soup.find_all("a", href=True):
    if ".pdf" in href.lower():
        # Normalizar y retornar
```

**Strategy 3 — Texto visible:**
```python
for a in soup.find_all("a", href=True):
    text = a.get_text(strip=True).lower()
    if any(w in text for w in ("download", "pdf", "get", "read")):
        # Saltar enlaces de navegación (/book/, /author/, /category/)
        # Normalizar y retornar
```

## Modo Browse (`browse()`)

Implementa el modo RSS/sync escrapeando la homepage:

```python
url = f"{self.base_url}/"
resp = await self.http_client.get(url, use_scraper=False)
for a in soup.select("a[href*='/book/']"):
    # Filtrar enlaces utilitarios: /category/, /author/, /tag/, /page/
    # Extraer internal_id, deduplicar, construir SearchResult
```

Útil cuando Readarr hace sync sin query de búsqueda (`t=book` sin `q=`).

## Manejo de Errores

- `search()`: Excepción capturada → `self.logger.error()` + return `[]`
- `get_download_url()`: Excepción capturada → `self.logger.error()` + return `None`
- Si no se encuentra enlace de descarga tras las 3 estrategias → `self.logger.warning()` + return `None`
- `browse()`: Excepción capturada → `self.logger.error()` + return `[]`

## Trampas / Problemas Conocidos

1. **Selectores genéricos** — BookSee no tiene marcado semántico predecible. Los selectores usan fallbacks en cascada (`div.book-item`, `table.results tr`, etc.) que pueden romperse si el sitio cambia su layout.
2. **Solo PDF** — A diferencia de otros providers, BookSee solo sirve PDFs. El `download_url` siempre usa `fmt=pdf`.
3. **BookSee menciona una API** — En la navegación del sitio se menciona una API. Si se descubre un endpoint JSON, priorizar sobre scraping HTML.
4. **~79 items por página** — La paginación devuelve ~79 resultados por página, lo que puede requerir múltiples requests para búsquedas con muchos resultados.
5. **Catálogo masivo** — 2.4M de títulos. Las búsquedas genéricas pueden devolver cientos de páginas de resultados.
6. **Autor no siempre disponible** — Si el selector de autor falla, `author=None` en SearchResult. El libro sigue siendo válido.

## Archivos

- `app/providers/books/booksee.py`
- `tests/test_provider_booksee.py`
