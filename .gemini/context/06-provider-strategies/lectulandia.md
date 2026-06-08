# Estrategia: Lectulandia

## Provider ID: `lectulandia`

## Propósito

Documenta la estrategia de scraping para Lectulandia (`ww3.lectulandia.co`), un sitio WordPress de libros electrónicos en español con un mecanismo de descarga de 3 pasos que involucra JavaScript.

## URLs del Sitio

| Componente | Patrón URL | Ejemplo |
|------------|------------|---------|
| Búsqueda | `/search/{query}` | `https://ww3.lectulandia.co/search/quijote` |
| Detalle | `/book/{id}/` | `https://ww3.lectulandia.co/book/12345/` |
| Descarga intermedia | `/download.php?...` | Página con JS que contiene `linkCode` |
| Descarga final | `/download/{code}` | URL construida a partir del `linkCode` |

## Requisitos Especiales

- **Cloudscraper requerido:** `use_scraper=True` en todas las peticiones.
- **Descarga en 3 pasos:** detalle → download.php → extraer linkCode de JS → URL final.

## Constructor

```python
def __init__(self, http_client, domain_resolver=None):
    domain = settings.LECTULANDIA_DOMAIN
    if domain_resolver:
        active_domain = domain_resolver.get_current("lectulandia")
        if active_domain:
            domain = active_domain
    super().__init__(
        provider_id="lectulandia",
        display_name="Lectulandia",
        base_url=domain,
        http_client=http_client,
        categories=[7000, 7020, 8000, 8010]
    )
```

## Estrategia de Búsqueda (`search()`)

### 1. Construir URL
```python
search_url = f"{self.base_url}/search/{query_to_use}"
```

**IMPORTANTE:** Lectulandia usa `/search/{query}` (sin `?s=`), a diferencia de otros WordPress.

### 2. Selectores CSS
```python
soup.select('a[href*="/book/"]')
```

### 3. Extracción de Internal ID
```python
match = re.search(r'/book/([^/]+)/', href)
internal_id = match.group(1) if match else None
```

### 4. Construcción de SearchResult
```python
SearchResult(
    title=title_text,
    guid=f"lectulandia-{internal_id}",
    link=f"{self.base_url}{href}" if href.startswith('/') else href,
    download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={internal_id}&fmt=epub",
    size_bytes=1000000,
    pub_date=datetime.now(),
    categories=[7020],
    description=f"Libro: {title_text}",
)
```

### 5. Deduplicación
- `seen_urls = set()` por URL
- Filtra `title_text.lower() == 'libros'` (enlace de navegación)

## Estrategia de Descarga (`get_download_url()`) — 3 Pasos

### Paso 1: Visitar página de detalle
```python
detail_url = f"{self.base_url}/book/{internal_id}/"
resp = await self.http_client.get(detail_url, use_scraper=True)
```

### Paso 2: Encontrar y seguir enlace download.php
```python
# Buscar /download.php? en la página de detalle
for a in soup.find_all('a', href=True):
    if '/download.php?' in a['href']:
        download_php_link = a['href']
        break

# Seguir el enlace intermedio
inter_url = self.base_url + download_php_link if download_php_link.startswith('/') else download_php_link
resp_inter = await self.http_client.get(inter_url, follow_redirects=True, use_scraper=True)
```

### Paso 3: Extraer linkCode del JavaScript
```python
# La página intermedia contiene JavaScript con el código real:
# var linkCode = "abc123";
m = re.search(r'var linkCode = ["\']([^"\']+)["\'];', resp_inter.text)
if m:
    code = m.group(1)
    final_url = f"{self.base_url}/download/{code}"
    return final_url
```

## Manejo de Errores
- `search()`: Excepciones capturadas → log + return `[]`
- `get_download_url()`:
  - Si no hay `download.php` → log warning + return `None`
  - Si no se puede extraer `linkCode` → log warning + return `None`
  - Excepciones → log error + return `None`

## Trampas / Problemas Conocidos

1. **El linkCode está en JavaScript inline** — Si el sitio cambia el nombre de la variable o la forma de embeber el código, el regex fallará.
2. **La URL de búsqueda es `/search/{query}`, NO `/?s={query}`** — Diferencia clave con EpubLibre/Espaebook.
3. **Requiere cloudscraper** — El sitio tiene protección anti-bot.

## Archivos
- `app/providers/books/lectulandia.py`
- `tests/test_provider_lectulandia.py`
