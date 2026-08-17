# Estrategia: Epubflix1

## Provider ID: `epubflix1`

## Propósito

Documenta la estrategia de scraping para Epubflix1 (`epubflix1.com`), un sitio WordPress de libros electrónicos en español. Provider nuevo añadido en la expansión multi-indexer.

## URLs del Sitio

| Componente | Patrón URL | Ejemplo |
|------------|------------|---------|
| Búsqueda | `/?s={query}` | `https://epubflix1.com/?s=quijote` |
| Detalle (intento 1) | `/book/{slug}/` | `https://epubflix1.com/book/el-quijote/` |
| Detalle (fallback) | `/libro/{slug}/` | `https://epubflix1.com/libro/el-quijote/` |
| Descarga | Enlace directo o archivo con extensión | Variable |

## Constructor

```python
def __init__(self, http_client, domain_resolver=None):
    domain = settings.EPUBFLIX1_DOMAIN
    if domain_resolver:
        active_domain = domain_resolver.get_current("epubflix1")
        if active_domain:
            domain = active_domain
    super().__init__(
        provider_id="epubflix1",
        display_name="Epubflix1",
        base_url=domain,
        http_client=http_client,
        categories=[7000, 7020, 8000, 8010]
    )
```

## Estrategia de Búsqueda (`search()`)

### 1. Construir URL
```python
search_url = f"{self.base_url}/?s={query_to_use}"
```

### 2. Selectores CSS (múltiples)
```python
soup.select('a[href*="/book/"], a[href*="/libro/"], h2.entry-title a, h3.entry-title a')
```

### 3. Extracción de Internal ID
```python
match = re.search(r'/(?:book|libro)/([^/]+)/?', href)
internal_id = match.group(1) if match else None

# Fallback: último segmento de la URL
if not internal_id:
    internal_id = [x for x in href.rstrip('/').split('/') if x][-1]
```

## Estrategia de Descarga (`get_download_url()`)

### Doble intento de path + doble estrategia de búsqueda:

```python
for path_prefix in ['/book/', '/libro/']:
    detail_url = f"{self.base_url}{path_prefix}{internal_id}/"
    resp = await self.http_client.get(detail_url, use_scraper=True)
    soup = BeautifulSoup(resp.text, 'lxml')
    
    # Estrategia 1: Buscar texto "EN EPUB", "DESCARGAR", "DOWNLOAD"
    target_text = f"EN {fmt.upper()}"
    for a in soup.find_all('a', href=True):
        text = a.get_text(strip=True).upper()
        if target_text in text or 'DESCARGAR' in text or 'DOWNLOAD' in text:
            href = a['href']
            if href.startswith('/'):
                return f"{self.base_url}{href}"
            return href
    
    # Estrategia 2: Buscar enlaces directos a archivos
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.endswith(f'.{fmt}') or f'.{fmt}?' in href:
            if href.startswith('/'):
                return f"{self.base_url}{href}"
            return href
```

## Manejo de Errores
- `search()`: Excepciones capturadas → log + return `[]`
- `get_download_url()`: 
  - Itera sobre `/book/` y `/libro/` (si uno falla, intenta el otro)
  - Cada intento fallido → `continue` al siguiente path
  - Si todos fallan → log warning + return `None`

## Trampas / Problemas Conocidos

1. **Provider nuevo** — La estructura del sitio puede cambiar. Los selectores son conservadores e intentan múltiples patrones.
2. **Dos estrategias de descarga** — Primero busca texto "DESCARGAR", luego busca enlaces directos a archivos (`.epub`, `.mobi`).
3. **Sin tests** — Este provider no tiene archivo de tests aún.

## Archivos
- `app/providers/books/epubflix1.py`
- `config.py` — `EPUBFLIX1_ENABLED`, `EPUBFLIX1_DOMAIN`
