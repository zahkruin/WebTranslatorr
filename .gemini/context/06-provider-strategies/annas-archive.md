# Estrategia: Anna's Archive

## Provider ID: `annasarchive`

## Propósito

Documenta la estrategia de scraping para Anna's Archive (`annas-archive.org`), un meta-buscador de libros que agrega resultados de Library Genesis, Z-Library y otras fuentes.

## URLs del Sitio

| Componente | Patrón URL | Ejemplo |
|------------|------------|---------|
| Búsqueda | `/search?q={query}&lang=es&ext=epub` | `https://annas-archive.org/search?q=quijote&lang=es&ext=epub` |
| Detalle | `/md5/{md5_hash}` | `https://annas-archive.org/md5/a1b2c3d4e5f6...` |
| Descarga | Variable (slow partner server, libgen mirrors) | Depende de la fuente |

## Requisitos Especiales

- **Cloudscraper requerido:** `use_scraper=True` — Anna's Archive tiene protección Cloudflare fuerte.
- **MD5-based IDs:** Los IDs internos son hashes MD5 de 32 caracteres hexadecimales.
- **Descarga multi-source:** Los enlaces de descarga pueden apuntar a diferentes mirrors (libgen.li, IPFS, etc.).

## Constructor

```python
def __init__(self, http_client, domain_resolver=None):
    domain = settings.ANNASARCHIVE_DOMAIN
    if domain_resolver:
        active_domain = domain_resolver.get_current("annasarchive")
        if active_domain:
            domain = active_domain
    super().__init__(
        provider_id="annasarchive",
        display_name="Anna's Archive",
        base_url=domain,
        http_client=http_client,
        categories=[7000, 7020, 8000, 8010]
    )
```

## Estrategia de Búsqueda (`search()`)

### 1. Construir URL
```python
search_url = f"{self.base_url}/search?q={query_to_use}&lang=es&ext=epub"
```

Filtra por idioma español y extensión EPUB.

### 2. Selectores CSS
```python
soup.select('a[href*="/md5/"]')
```

### 3. Extracción del título
```python
title_div = a.find('h3') or a.select_one('div.text-xl, div.font-bold')
title_text = title_div.get_text(strip=True) if title_div else None
```

Usa Tailwind CSS classes (`text-xl`, `font-bold`) típicas del diseño de Anna's Archive.

### 4. Extracción de Internal ID (MD5)
```python
internal_id = href.split('/md5/')[-1]
```

No usa regex; simplemente toma todo después de `/md5/`.

### 5. Construcción de SearchResult
```python
SearchResult(
    title=title_text,
    guid=f"annasarchive-{internal_id}",
    link=f"{self.base_url}{href}",
    download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={internal_id}&fmt=epub",
    size_bytes=1000000,
    pub_date=datetime.now(),
    categories=[7020],
    description=f"Libro: {title_text}",
)
```

## Estrategia de Descarga (`get_download_url()`)

### Flujo de 2 pasos con prioridad:

### Paso 1: Buscar "Slow Partner Server" (preferido)
```python
for a in soup.select('a.js-download-link'):
    text = a.get_text(strip=True).lower()
    href = a.get('href', '')
    if 'slow partner server' in text or 'slow' in text or 'libgen' in text:
        if href.startswith('/'):
            return f"{self.base_url}{href}"
        return href
```

### Paso 2: Fallback — buscar cualquier enlace de descarga
```python
for a in soup.find_all('a', href=True):
    if '/download/' in a['href'] or 'libgen.li' in a['href']:
        href = a['href']
        if href.startswith('/'):
            return f"{self.base_url}{href}"
        return href
```

## Manejo de Errores
- `search()`: Excepciones capturadas → log + return `[]`
- `get_download_url()`:
  - Si no hay slow partner server → intenta fallback con `/download/` o `libgen.li`
  - Si no hay ningún enlace → log warning + return `None`

## Trampas / Problemas Conocidos

1. **Cloudflare fuerte** — Anna's Archive tiene protección anti-bot agresiva. Sin cloudscraper, las requests fallan.
2. **Las clases CSS pueden cambiar** — `text-xl`, `font-bold`, `js-download-link` son clases Tailwind que Anna's Archive puede cambiar. Si el scraping falla, revisar los selectores.
3. **MD5 como ID** — Los IDs son hashes largos. Asegurarse de no truncarlos.
4. **"Slow Partner Server" puede no estar disponible** — El fallback a otros mirrors es necesario.

## Archivos
- `app/providers/books/annas_archive.py`
- `tests/test_provider_annas_archive.py`
