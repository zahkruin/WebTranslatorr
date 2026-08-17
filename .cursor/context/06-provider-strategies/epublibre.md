# Estrategia: EpubLibre

## Provider ID: `epublibre`

## Propósito

Documenta la estrategia de scraping para EpubLibre (`epublibre.bid`), un sitio WordPress de libros electrónicos en español.

## URLs del Sitio

| Componente | Patrón URL | Ejemplo |
|------------|------------|---------|
| Búsqueda | `/?s={query}` | `https://epublibre.bid/?s=quijote` |
| Detalle | `/book/{slug}/` | `https://epublibre.bid/book/el-quijote/` |
| Descarga | Variable (enlace en página de detalle) | Depende del sitio |

## Requisitos Especiales

- **Cloudscraper requerido:** `use_scraper=True` — el sitio puede tener protección Cloudflare.
- **DomainResolver:** Soporta resolución dinámica de dominio (registrado en `app/server.py`).

## Constructor

```python
def __init__(self, http_client, domain_resolver=None):
    domain = settings.EPUBLIBRE_DOMAIN
    if domain_resolver:
        active_domain = domain_resolver.get_current("epublibre")
        if active_domain:
            domain = active_domain
    super().__init__(
        provider_id="epublibre",
        display_name="EpubLibre",
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
    guid=f"epublibre-{internal_id}",
    link=href if href.startswith('http') else f"{self.base_url}{href}",
    download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={internal_id}&fmt=epub",
    size_bytes=1000000,
    pub_date=datetime.now(),
    categories=[7020],
    description=f"Libro: {title_text}",
)
```

### 5. Deduplicación
- Usa `seen_urls = set()` para evitar duplicados por URL.
- Filtra `title_text.lower() == 'biblioteca'` (enlace de navegación).

## Estrategia de Descarga (`get_download_url()`)

### Flujo de 2 pasos:
1. Visitar página de detalle: `{base_url}/book/{internal_id}/`
2. Buscar enlaces con texto "EN EPUB" o "DESCARGAR"

```python
detail_url = f"{self.base_url}/book/{internal_id}/"
resp = await self.http_client.get(detail_url, use_scraper=True)
soup = BeautifulSoup(resp.text, 'lxml')

target_text = f"EN {fmt.upper()}"
for a in soup.find_all('a', href=True):
    text = a.get_text(strip=True).upper()
    if target_text in text or 'DESCARGAR' in text:
        href = a['href']
        if href.startswith('/'):
            return f"{self.base_url}{href}"
        return href
```

## Manejo de Errores
- `search()`: Excepciones capturadas → log + return `[]`
- `get_download_url()`: Excepciones capturadas → log + return `None`
- Si no se encuentra enlace de descarga → log warning + return `None`

## Diferencias con Otros Providers WordPress

| Característica | EpubLibre | Lectulandia | Espaebook |
|---------------|-----------|-------------|-----------|
| URL búsqueda | `/?s=` | `/search/` | `/?s=` |
| URL detalle | `/book/{id}/` | `/book/{id}/` | `/libro/{id}/` o `/book/{id}/` |
| Descarga | Enlace directo | download.php + linkCode JS | Enlace directo |
| Cloudscraper | Sí | Sí | Sí |

## Trampas
- El sitio puede requerir cloudscraper; si falla con httpx normal, usar `use_scraper=True`.
- La URL de búsqueda usa `?s=`, no `/search/` como otros WordPress.

## Archivos
- `app/providers/books/epublibre.py`
- `tests/test_provider_epublibre.py`
