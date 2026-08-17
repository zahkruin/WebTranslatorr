# Estrategia: HolaEbook

## Provider ID: `holaebook`

## Propósito

Documenta la estrategia de scraping para HolaEbook (`holaebook.com`), un sitio de libros electrónicos que sirve los archivos como ZIPs (requiere extracción on-the-fly).

## URLs del Sitio

| Componente | Patrón URL | Ejemplo |
|------------|------------|---------|
| Búsqueda (intento 1) | `/search?q={query}` | `https://holaebook.com/search?q=quijote` |
| Búsqueda (fallback) | `/?s={query}` | `https://holaebook.com/?s=quijote` |
| Detalle (intento 1) | `/libro/{id}.html` | `https://holaebook.com/libro/12345.html` |
| Detalle (fallback) | `/book/{id}/` | `https://holaebook.com/book/12345/` |
| Descarga | ZIP con EPUB dentro | El download proxy extrae el EPUB |

## Requisitos Especiales

- **ZIP wrapper:** `self.is_zipped = True` — los archivos se sirven como ZIP.
- **Extracción on-the-fly:** `ZipExtractor.extract_epub_from_memory()` en el download proxy.
- **Cloudscraper requerido:** `use_scraper=True`

## Constructor

```python
def __init__(self, http_client, domain_resolver=None):
    # ... domain resolution ...
    super().__init__(
        provider_id="holaebook",
        display_name="HolaEbook",
        base_url=domain,
        http_client=http_client,
        categories=[7000, 7020, 8000, 8010]
    )
    self.is_zipped = True  # HolaEbook descarga ZIPs
```

**IMPORTANTE:** El flag `is_zipped = True` es lo que activa la extracción automática en el download proxy.

## Estrategia de Búsqueda (`search()`)

### 1. Construir URL con fallback
```python
# Intento 1: /search?q=
resp = await self.http_client.get(search_url, use_scraper=True)
if resp.status_code == 404:
    # Fallback: /?s=
    search_url = f"{self.base_url}/?s={query_to_use}"
    resp = await self.http_client.get(search_url, use_scraper=True)
```

### 2. Selectores CSS
```python
soup.select('a[href*="/libro"], a[href*="/book"]')
```

### 3. Extracción de Internal ID
```python
# Extraer último segmento, eliminar .html
internal_id = [x for x in href.split('/') if x][-1].replace('.html', '')
```

### 4. Construcción de SearchResult
```python
SearchResult(
    title=title_text,
    guid=f"holaebook-{internal_id}",
    link=href if href.startswith('http') else f"{self.base_url}{href}",
    download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={internal_id}&fmt=epub",
    size_bytes=1000000,
    pub_date=datetime.now(),
    categories=[7020],
    description=f"Libro: {title_text}",
)
```

## Estrategia de Descarga (`get_download_url()`)

### Flujo con fallback:
```python
# Intento 1: /libro/{id}.html
detail_url = f"{self.base_url}/libro/{internal_id}.html"
resp = await self.http_client.get(detail_url, use_scraper=True)

# Fallback: /book/{id}/
if resp.status_code != 200:
    detail_url = f"{self.base_url}/book/{internal_id}/"
    resp = await self.http_client.get(detail_url, use_scraper=True)
```

### Búsqueda del enlace:
```python
for a in soup.find_all('a', href=True):
    text = a.get_text(strip=True).upper()
    if 'EPUB' in text or 'DESCARGAR' in text or 'DOWNLOAD' in text:
        href = a['href']
        if href.startswith('/'):
            return f"{self.base_url}{href}"
        return href
```

## Flujo Completo de Descarga (con ZIP)

1. `get_download_url()` devuelve la URL del ZIP
2. `download_proxy()` en `torznab.py` descarga el ZIP
3. Como `is_zipped = True`, `ZipExtractor.extract_epub_from_memory()` extrae el EPUB
4. El EPUB extraído se sirve al *Arr con Content-Type `application/epub+zip`

```
*Arr → /api/download → get_download_url() → URL del ZIP
     → http_client.download_file() → bytes del ZIP
     → ZipExtractor.extract_epub_from_memory() → bytes del EPUB
     → Response con Content-Type: application/epub+zip
```

## Manejo de Errores
- `search()`: 404 en `/search?q=` → intenta `/?s=`. Excepciones → log + return `[]`
- `get_download_url()`: Status != 200 → intenta `/book/`. Excepciones → log + return `None`

## Trampas
- **ZIP wrapper**: Si `is_zipped` no está activado, el *Arr recibe un ZIP en lugar de un EPUB y no puede importarlo.
- **Dos patrones de búsqueda**: La URL `/search?q=` puede no funcionar; el fallback `/?s=` es el patrón WordPress estándar.
- **Extensión .html**: Algunas URLs de detalle terminan en `.html`, otras no.

## Archivos
- `app/providers/books/holaebook.py`
- `app/utils/zip_extractor.py` (extracción on-the-fly)
- `app/api/torznab.py:317-321` (integración ZIP en download proxy)
- `tests/test_provider_holaebook.py`
