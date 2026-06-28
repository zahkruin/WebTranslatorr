# Estrategia: LectuEpubLibre5

## Provider ID: `lectuepublibre5`

## Propósito

Documenta la estrategia de scraping para LectuEpubLibre5 (`lectuepublibre5.com`), un sitio WordPress de libros electrónicos en español. Provider nuevo añadido en la expansión multi-indexer.

## URLs del Sitio

| Componente | Patrón URL | Ejemplo |
|------------|------------|---------|
| Búsqueda | `/?s={query}` | `https://lectuepublibre5.com/?s=quijote` |
| Detalle | `/book/{slug}/` o `/libro/{slug}/` | Variable |
| Descarga | Enlace directo o archivo | Variable |

## Constructor

```python
def __init__(self, http_client, domain_resolver=None):
    domain = settings.LECTUEPUBLIBRE5_DOMAIN
    if domain_resolver:
        active_domain = domain_resolver.get_current("lectuepublibre5")
        if active_domain:
            domain = active_domain
    super().__init__(
        provider_id="lectuepublibre5",
        display_name="LectuEpubLibre5",
        base_url=domain,
        http_client=http_client,
        categories=[7000, 7020, 8000, 8010]
    )
```

## Estrategia de Búsqueda (`search()`)

### 1. URL
```python
search_url = f"{self.base_url}/?s={query_to_use}"
```

### 2. Selectores (múltiples)
```python
for selector in ['a[href*="/book/"]', 'a[href*="/libro/"]',
                 'h2.entry-title a', 'h3.entry-title a']:
    for a in soup.select(selector):
        # ...
```

### 3. Filtrado
```python
if title_text.lower() in ['biblioteca', 'inicio', 'home']:
    continue
```

### 4. Internal ID
```python
match = re.search(r'/(?:book|libro)/([^/]+)/', href)
internal_id = match.group(1) if match else None
if not internal_id:
    internal_id = [x for x in href.rstrip('/').split('/') if x][-1]
```

## Estrategia de Descarga (`get_download_url()`)

### Triple intento de path + doble búsqueda:

```python
for path_prefix in ['/book/', '/libro/', '/descargar/']:
    detail_url = f"{self.base_url}{path_prefix}{internal_id}/"
    resp = await self.http_client.get(detail_url, use_scraper=True)
    soup = BeautifulSoup(resp.text, 'lxml')
    
    # Búsqueda 1: Texto "EN EPUB", "DESCARGAR", "DOWNLOAD"
    for a in soup.find_all('a', href=True):
        text = a.get_text(strip=True).upper()
        if target_text in text or 'DESCARGAR' in text or 'DOWNLOAD' in text:
            # Filtrar enlaces de navegación
            if '/genre/' not in href and '/autor/' not in href:
                return normalize(href)
    
    # Búsqueda 2: Enlaces directos a archivos
    for a in soup.find_all('a', href=True):
        if href.endswith(f'.{fmt}') or f'.{fmt}?' in href:
            return normalize(href)
```

## Características

- **Filtrado de navegación**: Excluye `/genre/` y `/autor/` en enlaces de descarga.
- **Triple path**: Intenta `/book/`, `/libro/`, `/descargar/`.
- **Doble búsqueda**: Primero por texto, luego por extensión de archivo.

## Trampas

1. **Provider nuevo** — Sin tests, estructura del sitio puede variar.
2. **Filtrado de navegación** — Puede excluir enlaces legítimos si incluyen `/genre/` o `/autor/` en la URL.

## Archivos
- `app/providers/books/lectuepublibre5.py`
- `config.py` — `LECTUEPUBLIBRE5_ENABLED`, `LECTUEPUBLIBRE5_DOMAIN`
