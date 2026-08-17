# Estrategia: B00k.Bond

## Provider ID: `booobook`

## Propósito

Documenta la estrategia de scraping para B00k.Bond (`es.booobook.bond`), un sitio de libros electrónicos en español. Provider nuevo añadido en la expansión multi-indexer. Usa una estrategia de scraping defensiva con múltiples selectores y múltiples patrones de URL.

## URLs del Sitio

| Componente | Patrón URL | Ejemplo |
|------------|------------|---------|
| Búsqueda (intento 1) | `/?s={query}` | `https://es.booobook.bond/?s=quijote` |
| Búsqueda (intento 2) | `/search/{query}` | `https://es.booobook.bond/search/quijote` |
| Detalle | `/book/{slug}/` o `/libro/{slug}/` | Variable |
| Descarga | Enlace directo en página de detalle | Variable |

## Constructor

```python
def __init__(self, http_client, domain_resolver=None):
    domain = settings.BOOOBOOK_DOMAIN
    if domain_resolver:
        active_domain = domain_resolver.get_current("booobook")
        if active_domain:
            domain = active_domain
    super().__init__(
        provider_id="booobook",
        display_name="B00k.Bond",
        base_url=domain,
        http_client=http_client,
        categories=[7000, 7020, 8000, 8010]
    )
```

## Estrategia de Búsqueda (`search()`)

### 1. Construir URL con múltiples intentos

```python
search_urls = [
    f"{self.base_url}/?s={query_to_use}",
    f"{self.base_url}/search/{query_to_use}",
]

for url in search_urls:
    try:
        resp = await self.http_client.get(url, use_scraper=True)
        if resp.status_code == 200:
            break
    except Exception:
        continue
```

### 2. Selectores CSS (múltiples, defensivos)

```python
for selector in [
    'a[href*="/book/"]',
    'a[href*="/libro/"]',
    'h2.entry-title a',
    'h3.entry-title a',
    'article a[href*="/"]',
]:
    for a in soup.select(selector):
        # ...
```

### 3. Filtrado de enlaces de navegación

```python
# Skip navigation/utility links
if any(skip in href for skip in [
    '/genre/', '/autor/', '/category/', '/tag/', '/page/', '#'
]):
    continue

# Skip common site section titles
if title_text.lower() in ['inicio', 'home', 'biblioteca', 'contacto']:
    continue
```

### 4. Extracción de Internal ID

```python
match = re.search(r'/(?:book|libro)/([^/]+)/?', href)
internal_id = match.group(1) if match else None

if not internal_id:
    internal_id = [x for x in href.rstrip('/').split('/') if x][-1]
```

## Estrategia de Descarga (`get_download_url()`)

### Triple intento de path:

```python
for path_prefix in ['/book/', '/libro/', '/descargar/']:
    detail_url = f"{self.base_url}{path_prefix}{internal_id}/"
    # ...
```

### Doble estrategia de búsqueda de enlace:

```python
# Estrategia 1: Texto "EN EPUB", "DESCARGAR", "DOWNLOAD"
target_text = f"EN {fmt.upper()}"
for a in soup.find_all('a', href=True):
    text = a.get_text(strip=True).upper()
    if target_text in text or 'DESCARGAR' in text or 'DOWNLOAD' in text:
        return normalize(href)

# Estrategia 2: Enlaces directos a archivos
for a in soup.find_all('a', href=True):
    if href.endswith(f'.{fmt}') or f'.{fmt}?' in href:
        return normalize(href)
```

## Manejo de Errores
- `search()`: Prueba múltiples URLs de búsqueda. Si ninguna funciona → return `[]`
- `get_download_url()`: Itera sobre 3 paths. Cada intento fallido → `continue`

## Trampas

1. **Provider nuevo** — Estructura del sitio desconocida. Estrategia muy defensiva con muchos fallbacks.
2. **Múltiples URLs de búsqueda** — No se sabe cuál es el endpoint correcto, se prueban varios.
3. **Filtrado agresivo** — Descarta enlaces de navegación, categorías, tags, páginas, y anchors.
4. **Sin tests** — Este provider no tiene archivo de tests aún.

## Archivos
- `app/providers/books/booobook.py`
- `config.py` — `BOOOBOOK_ENABLED`, `BOOOBOOK_DOMAIN`
