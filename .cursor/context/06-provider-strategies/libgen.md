# Estrategia: Library Genesis

## Provider ID: `libgen`

## Propósito

Documenta la estrategia de scraping para Library Genesis (`libgen.ee`), un repositorio masivo de libros académicos y generales. A diferencia de los providers WordPress, Libgen usa una interfaz basada en tablas HTML.

## URLs del Sitio

| Componente | Patrón URL | Ejemplo |
|------------|------------|---------|
| Búsqueda | `/search.php?req={query}&lg_topic=libgen&open=0&view=simple&res=25&phrase=1&column=def` | URL compleja con múltiples parámetros |
| Detalle | `/book/index.php?md5={md5_hash}` | `https://libgen.ee/book/index.php?md5=a1b2c3...` |
| Descarga directa | `/main/{first2}/{md5}` | `https://libgen.ee/main/a1/a1b2c3...` |
| Descarga mirrors | Variables (libgen, cloudflare, IPFS) | Detectados en página de detalle |

## Constructor

```python
def __init__(self, http_client, domain_resolver=None):
    domain = settings.LIBGEN_DOMAIN
    if domain_resolver:
        active_domain = domain_resolver.get_current("libgen")
        if active_domain:
            domain = active_domain
    super().__init__(
        provider_id="libgen",
        display_name="Library Genesis",
        base_url=domain,
        http_client=http_client,
        categories=[7000, 7020, 8000, 8010]
    )
```

## Estrategia de Búsqueda (`search()`)

### 1. Construir URL

Libgen usa una URL de búsqueda compleja con múltiples parámetros:

```python
encoded_query = quote_plus(query_to_use)
search_url = (
    f"{self.base_url}/search.php"
    f"?req={encoded_query}"
    f"&lg_topic=libgen"
    f"&open=0"
    f"&view=simple"
    f"&res=25"
    f"&phrase=1"
    f"&column=def"
)
```

**Parámetros:**
| Parámetro | Valor | Significado |
|-----------|-------|-------------|
| `req` | query | Término de búsqueda |
| `lg_topic` | `libgen` | Buscar en LibGen (no en otras colecciones) |
| `view` | `simple` | Vista simplificada (más fácil de parsear) |
| `res` | `25` | Resultados por página |
| `phrase` | `1` | Búsqueda exacta |
| `column` | `def` | Columna por defecto |

### 2. Parsing de la tabla de resultados

Libgen devuelve resultados en una tabla HTML con clase `c`:

```python
table = soup.find('table', class_='c')
if not table:
    return []

rows = table.find_all('tr')[1:]  # Skip header row
for row in rows:
    cols = row.find_all('td')
    if len(cols) < 10:
        continue
    
    # Columna 2: Título
    title_td = cols[2]
    # Columna 1: Autor
    author_td = cols[1]
```

### 3. Extracción del MD5

```python
md5_link = title_td.find('a', href=lambda h: h and 'md5=' in h)
if md5_link:
    href = md5_link.get('href', '')
    md5_match = re.search(r'md5=([a-f0-9]{32})', href, re.IGNORECASE)
    if md5_match:
        md5 = md5_match.group(1).lower()
```

### 4. Extracción de metadatos adicionales

```python
# Columna 5: Año
year = cols[4].get_text(strip=True)
# Columna 7: Tamaño
size_text = cols[6].get_text(strip=True)
# Columna 8: Extensión
extension = cols[7].get_text(strip=True).lower()
```

### 5. Conversión de tamaño

```python
@staticmethod
def _parse_size(size_text: str) -> int:
    if 'kb' in size_text:
        return int(float(size_text.replace('kb', '').strip()) * 1024)
    elif 'mb' in size_text:
        return int(float(size_text.replace('mb', '').strip()) * 1024 * 1024)
    elif 'gb' in size_text:
        return int(float(size_text.replace('gb', '').strip()) * 1024 * 1024 * 1024)
    else:
        return int(float(size_text))
```

### 6. Construcción de SearchResult

```python
SearchResult(
    title=f"{title_text} - {author_text}",
    guid=f"libgen-{md5}",
    link=f"{self.base_url}/book/index.php?md5={md5}",
    download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={md5}&fmt={extension}",
    size_bytes=size_bytes,
    pub_date=datetime.now(),
    categories=[7020],
    description=f"Libro: {title_text} | Autor: {author_text} | Año: {year} | Formato: {extension}",
    author=author_text or None,
    extra_attrs={"format": extension, "year": year},
)
```

## Estrategia de Descarga (`get_download_url()`)

### Flujo multi-estrategia:

```python
detail_url = f"{self.base_url}/book/index.php?md5={internal_id}"
resp = await self.http_client.get(detail_url, use_scraper=True)
soup = BeautifulSoup(resp.text, 'lxml')

# Estrategia 1: Enlaces con 'libgen' + 'get'/'download'/'main'
for a in soup.find_all('a', href=True):
    href = a['href']
    if 'libgen' in href and ('get' in href or 'download' in href or 'main' in href):
        return normalize(href)

# Estrategia 2: Enlaces con texto 'epub'/'mobi'/'pdf'/'download'
for a in soup.find_all('a', href=True):
    text = a.get_text(strip=True).lower()
    if any(word in text for word in ['epub', 'mobi', 'pdf', 'download', fmt]):
        return normalize(href)

# Estrategia 3: Enlaces cloudflare/IPFS
for a in soup.find_all('a', href=True):
    if 'cloudflare' in a['href'] or 'ipfs' in a['href']:
        return normalize(href)

# Estrategia 4 (fallback): Construir URL directa
direct_url = f"{self.base_url}/main/{internal_id[:2]}/{internal_id}"
return direct_url
```

## Manejo de Errores
- `search()`: Si no hay tabla `class='c'` → return `[]`. Excepciones → log + return `[]`
- `get_download_url()`: Prueba 4 estrategias en orden. Si todas fallan → log warning + return `None`

## Trampas / Problemas Conocidos

1. **Estructura de tabla frágil** — Libgen usa índices de columna fijos (1=autor, 2=título, 5=año, 7=tamaño, 8=extensión). Si cambian el orden de las columnas, el parsing falla.
2. **MD5 de 32 caracteres** — El regex `[a-f0-9]{32}` asume hashes MD5 estándar.
3. **URL de búsqueda compleja** — Si Libgen cambia los nombres de los parámetros, la búsqueda fallará.
4. **Descarga directa como fallback** — La URL `/main/{first2}/{md5}` puede no funcionar para todos los libros.

## Archivos
- `app/providers/books/libgen.py`
- `config.py` — `LIBGEN_ENABLED`, `LIBGEN_DOMAIN`
