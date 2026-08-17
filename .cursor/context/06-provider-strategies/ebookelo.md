# Estrategia: Ebookelo

## Provider ID: `ebookelo`

## Propósito

Documenta la estrategia de scraping para Ebookelo (`ww2.ebookelo.com`), un sitio de libros electrónicos en español con un mecanismo de ad-gate (trampa publicitaria) que requiere manejo especial.

## URLs del Sitio

| Componente | Patrón URL | Ejemplo |
|------------|------------|---------|
| Búsqueda | `/search/{query}/page/{n}` | `/search/quijote/page/1` |
| Detalle | `/ebook/{id}/{slug}` | `/ebook/1828/el-quijote` |
| Descarga | `/download/{id}/{format}` | `/download/1828/epub` |
| Magnet | `/download/{id}/magnet` | `/download/1828/magnet` |

## Constructor

```python
def __init__(self, http_client: HttpClient, domain_resolver=None):
    base_url = settings.EBOOKELO_DOMAIN
    if domain_resolver:
        active_domain = domain_resolver.get_current("ebookelo")
        if active_domain:
            base_url = active_domain
    super().__init__(
        http_client=http_client,
        provider_id="ebookelo",
        display_name="Ebookelo",
        base_url=base_url,
        categories=[7000, 7020, 8000, 8010]
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
def _build_search_url(self, query: str, page: int = 1) -> str:
    return f"{self.base_url}/search/{quote_plus(query)}/page/{page}"
```

### 2. Parsing de Resultados

```python
for link in soup.select('a[href*="/ebook/"]'):
    href = link.get("href", "")
    parts = href.rstrip("/").split("/")
    book_id = parts[-2]
    slug = parts[-1]
    title = link.get_text(strip=True)
    
    result = SearchResult(
        title=title,
        guid=f"ebookelo-{book_id}",
        link=f"{self.base_url}/ebook/{book_id}/{slug}",
        download_url=f"/api/download?provider=ebookelo&id={book_id}&fmt=epub",
        seeders=100,
        peers=100,
        categories=[7000, 7020, 8000, 8010],
        extra_attrs={"booktitle": title},
    )
```

### 3. Enriquecimiento (visita página de detalle)

Ebookelo es uno de los pocos providers que enriquece los resultados:

```python
for result in results[:limit]:
    detail = await self._parse_book_detail(result.link)
    if detail.get("author"):
        result.author = detail["author"]
    if detail.get("formats"):
        fmt = self._select_best_format(detail["formats"])
        result.download_url = f"/api/download?provider=ebookelo&id={book_id}&fmt={fmt}"
```

### 4. Deduplicación

```python
seen = set()
unique = []
for r in results:
    if r.guid not in seen:
        seen.add(r.guid)
        unique.append(r)
return unique
```

El sitio puede listar el mismo libro en diferentes idiomas. Deduplicar por `book_id` (GUID).

## Trampa del Ad-Gate (profitablecpmgate.com)

**CRÍTICO**: La página de detalle tiene **dos sets** de botones de descarga:

### 1. Enlaces SUPERIORES (TRAMPA)
- Apuntan a `profitablecpmgate.com`
- Son publicidad
- **IGNORAR COMPLETAMENTE**
- Selector: `a[href*="profitablecpmgate"]`

### 2. Enlaces INFERIORES (REALES)
- Apuntan a `/download/{id}/{format}`
- Son los enlaces de descarga directa
- Usar estos exclusivamente
- Selector: `a[href*="/download/"]`

## Estrategia de Descarga (`get_download_url()`)

### Flujo de 4 pasos:

```python
async def get_download_url(self, internal_id: str) -> str:
    parts = internal_id.split("/", 1)
    book_id, fmt = parts if len(parts) == 2 else (parts[0], "epub")
    
    download_url = f"{self.base_url}/download/{book_id}/{fmt}"
    
    # 1. GET sin seguir redirects
    response = await self.http_client.get(
        download_url,
        follow_redirects=False,
        headers={"Referer": f"{self.base_url}/ebook/{book_id}/"}
    )
    
    # 2. Si 302 → Location es la URL del archivo
    if response.status_code in (301, 302, 303, 307, 308):
        location = response.headers.get("Location", "")
        if "profitablecpmgate" not in location:
            return location or download_url
    
    # 3. Si 200 con binario → es el archivo directo
    if response.status_code == 200:
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return download_url
        else:
            # 4. Si 200 con HTML → buscar URL real en el HTML
            soup = BeautifulSoup(response.text, "lxml")
            for link in soup.select("a[href]"):
                href = link.get("href", "")
                if "profitablecpmgate" in href:
                    continue
                if href.endswith(f".{fmt}") or "/download/" in href:
                    return normalize(href)
    
    return download_url
```

### Formatos Soportados

Prioridad: **EPUB > MOBI > PDF > Magnet**

```python
PREFERRED_FORMAT_ORDER = ["epub", "mobi", "pdf"]

def _select_best_format(self, formats: list[str]) -> str:
    for fmt in self.PREFERRED_FORMAT_ORDER:
        if fmt in formats:
            return fmt
    return formats[0] if formats else "epub"
```

### Parámetros de Página de Detalle

```python
async def _parse_book_detail(self, url: str) -> dict:
    # Autor
    author_link = soup.select_one('a[href*="/ebooks/autor/"]')
    # Formatos disponibles
    for dl_link in soup.select('a[href*="/download/"]'):
        fmt = href.rstrip("/").split("/")[-1]
        if fmt in ("epub", "mobi", "pdf", "magnet"):
            formats.append(fmt)
    # Género
    genre_link = soup.select_one('a[href*="/ebooks/genero/"]')
```

## Manejo de Errores
- `search()`: Excepciones capturadas → log + return `[]`
- `get_download_url()`: Excepciones capturadas → log + return `download_url` (URL original como fallback)

## Trampas / Problemas Conocidos

1. **profitablecpmgate.com** — Es una trampa de anuncios. NUNCA seguir esos enlaces.
2. **Redirect sin seguir** — `follow_redirects=False` es necesario para interceptar el 302 y verificar que no apunte a publicidad.
3. **Enriquecimiento costoso** — Visita la página de detalle de cada resultado. Esto añade latencia.
4. **Formatos en español** — Los nombres de formato en la URL pueden variar (epub vs epub-spanish).

## Archivos
- `app/providers/books/ebookelo.py`
- `tests/test_provider_ebookelo.py`
