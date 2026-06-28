# Estrategia: Espaebook

## Provider ID: `espaebook`

## Propósito

Documenta la estrategia de scraping para Espaebook (`espaebook.cc`), un sitio WordPress de libros electrónicos en español con doble patrón de URL (`/libro/` y `/book/`).

## URLs del Sitio

| Componente | Patrón URL | Ejemplo |
|------------|------------|---------|
| Búsqueda | `/?s={query}` | `https://espaebook.cc/?s=quijote` |
| Detalle (intento 1) | `/libro/{id}/` | `https://espaebook.cc/libro/12345/` |
| Detalle (fallback) | `/book/{id}/` | `https://espaebook.cc/book/12345/` |
| Descarga | Variable (enlace en página de detalle) | Depende del libro |

## Requisitos Especiales

- **Cloudscraper requerido:** `use_scraper=True`
- **Doble patrón de URL:** El sitio puede usar `/libro/` o `/book/`. El provider intenta ambos.

## Constructor

```python
def __init__(self, http_client, domain_resolver=None):
    domain = settings.ESPAEBOOK_DOMAIN
    if domain_resolver:
        active_domain = domain_resolver.get_current("espaebook")
        if active_domain:
            domain = active_domain
    super().__init__(
        provider_id="espaebook",
        display_name="Espaebook",
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
soup.select('a[href*="/libro/"], a[href*="/book/"], h2.entry-title a')
```

### 3. Extracción de Internal ID
```python
# Intento 1: extraer de /libro/{id}/ o /book/{id}/
match = re.search(r'/(?:libro|book)/([^/]+)/?', href)
internal_id = match.group(1) if match else None

# Fallback: último segmento de la URL
if not internal_id:
    internal_id = [x for x in href.split('/') if x][-1]
```

### 4. Construcción de SearchResult
```python
SearchResult(
    title=title_text,
    guid=f"espaebook-{internal_id}",
    link=href if href.startswith('http') else f"{self.base_url}{href}",
    download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={internal_id}&fmt=epub",
    size_bytes=1000000,
    pub_date=datetime.now(),
    categories=[7020],
    description=f"Libro: {title_text}",
)
```

## Estrategia de Descarga (`get_download_url()`)

### Flujo con fallback de URL:
```python
detail_url = f"{self.base_url}/libro/{internal_id}/"
resp = await self.http_client.get(detail_url, use_scraper=True)

# Si 404, intentar con /book/
if resp.status_code == 404:
    detail_url = f"{self.base_url}/book/{internal_id}/"
    resp = await self.http_client.get(detail_url, use_scraper=True)
```

### Búsqueda del enlace de descarga:
```python
for a in soup.find_all('a', href=True):
    text = a.get_text(strip=True).upper()
    if 'EPUB' in text or 'DESCARGAR' in text:
        href = a['href']
        # Filtrar enlaces de navegación (género, autor, book)
        if '/genre/' not in href and '/autor/' not in href and '/book/' not in href:
            if href.startswith('/'):
                return f"{self.base_url}{href}"
            return href
```

## Manejo de Errores
- `search()`: Excepciones capturadas → log + return `[]`
- `get_download_url()`: 404 en `/libro/` → intenta `/book/`. Excepciones → log + return `None`

## Trampas / Problemas Conocidos

1. **Dos patrones de URL** — El sitio puede usar `/libro/{id}/` o `/book/{id}/`. El provider intenta ambos.
2. **Filtrado de enlaces de navegación** — Se excluyen enlaces con `/genre/`, `/autor/`, `/book/` para evitar falsos positivos.
3. **Fallback en internal_id** — Si el regex no captura, se usa el último segmento de la URL, lo que puede producir IDs incorrectos si la URL tiene query params.

## Archivos
- `app/providers/books/espaebook.py`
- `tests/test_provider_espaebook.py`
