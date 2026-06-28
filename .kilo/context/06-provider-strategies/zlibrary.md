# Estrategia: Z-Library

## Provider ID: `zlibrary`

## Propósito

Documenta la estrategia de scraping para Z-Library (`z-library.sk`), un repositorio masivo de libros electrónicos. Z-Library cambia frecuentemente de dominio y usa un layout de tarjetas (cards) moderno.

## URLs del Sitio

| Componente | Patrón URL | Ejemplo |
|------------|------------|---------|
| Búsqueda (intento 1) | `/s/{query}/?language=es&ext=epub` | `https://z-library.sk/s/quijote/?language=es&ext=epub` |
| Búsqueda (intento 2) | `/s/{query}?language=spanish&ext=epub` | `https://z-library.sk/s/quijote?language=spanish&ext=epub` |
| Búsqueda (fallback) | `/search?q={query}&lang=es` | `https://z-library.sk/search?q=quijote&lang=es` |
| Detalle | `/book/{id}` | `https://z-library.sk/book/1234567` |
| Descarga | `/book/{id}/download` o `/d/{id}` o `/dl/{id}` | Variable |

## Requisitos Especiales

- **Dominio inestable:** Z-Library cambia de dominio frecuentemente. Usar `DomainResolver`.
- **Múltiples patrones de URL:** Ha cambiado su estructura de URLs varias veces.
- **Cloudscraper requerido:** `use_scraper=True`

## Constructor

```python
def __init__(self, http_client, domain_resolver=None):
    domain = settings.ZLIBRARY_DOMAIN
    if domain_resolver:
        active_domain = domain_resolver.get_current("zlibrary")
        if active_domain:
            domain = active_domain
    super().__init__(
        provider_id="zlibrary",
        display_name="Z-Library",
        base_url=domain,
        http_client=http_client,
        categories=[7000, 7020, 8000, 8010]
    )
```

## Estrategia de Búsqueda (`search()`)

### 1. Construir URL con múltiples intentos

```python
search_urls = [
    f"{self.base_url}/s/{encoded_query}/?language=es&ext=epub",
    f"{self.base_url}/s/{encoded_query}?language=spanish&ext=epub",
    f"{self.base_url}/search?q={encoded_query}&lang=es",
]

for url in search_urls:
    try:
        resp = await self.http_client.get(url, use_scraper=True)
        if resp.status_code == 200 and len(resp.text) > 500:
            break
    except Exception:
        continue
```

### 2. Método 1: Card-based layout (moderno)

```python
for card in soup.select('div[class*="book"], div[class*="card"], article, div[class*="result"]'):
    link = card.find('a', href=True)
    href = link.get('href', '')
    
    # Extraer ID del libro
    book_id = None
    id_match = re.search(r'/book/(\d+)', href)
    if id_match:
        book_id = id_match.group(1)
    
    # Extraer título
    title_elem = card.find(['h2', 'h3', 'h4', 'h5', 'span', 'div'],
                           class_=re.compile(r'title|name|book', re.I))
    if not title_elem:
        title_elem = link
    title_text = title_elem.get_text(strip=True)
    
    # Extraer autor
    author_elem = card.find(['span', 'div', 'p', 'small'],
                            class_=re.compile(r'auth', re.I))
    author_text = author_elem.get_text(strip=True) if author_elem else ""
    
    # Extraer extensión
    ext_elem = card.find(['span', 'div', 'small'],
                         class_=re.compile(r'format|ext|type', re.I))
    extension = ext_elem.get_text(strip=True).lower() if ext_elem else "epub"
    extension = re.sub(r'[^a-z0-9]', '', extension)
    if extension not in ('epub', 'mobi', 'pdf', 'azw3', 'fb2', 'djvu', 'txt'):
        extension = 'epub'
```

### 3. Método 2: Fallback (búsqueda por enlaces `/book/`)

Si el método 1 no encuentra resultados:

```python
for a in soup.select('a[href*="/book/"]'):
    href = a.get('href', '')
    title_text = a.get_text(strip=True)
    
    id_match = re.search(r'/book/(\d+)', href)
    book_id = id_match.group(1) if id_match else None
```

### 4. Construcción de SearchResult

```python
SearchResult(
    title=f"{title_text} - {author_text}" if author_text else title_text,
    guid=f"zlibrary-{book_id}",
    link=href if href.startswith('http') else f"{self.base_url}{href}",
    download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={book_id}&fmt={extension}",
    size_bytes=1000000,
    pub_date=datetime.now(),
    categories=[7020],
    description=f"Libro: {title_text} | Autor: {author_text} | Formato: {extension}",
    author=author_text or None,
    extra_attrs={"format": extension},
)
```

## Estrategia de Descarga (`get_download_url()`)

### Múltiples patrones de URL de descarga:

```python
download_patterns = [
    f"{self.base_url}/book/{internal_id}/download",
    f"{self.base_url}/book/{internal_id}",
    f"{self.base_url}/d/{internal_id}",
    f"{self.base_url}/dl/{internal_id}",
]

for detail_url in download_patterns:
    resp = await self.http_client.get(detail_url, use_scraper=True)
    soup = BeautifulSoup(resp.text, 'lxml')
    
    # Estrategia 1: Enlaces con texto "download", "descargar", "epub"
    for a in soup.find_all('a', href=True):
        text = a.get_text(strip=True).lower()
        if any(word in text for word in ['download', 'descargar', 'epub', fmt]):
            return normalize(href)
    
    # Estrategia 2: Enlaces directos a archivos
    for a in soup.find_all('a', href=True):
        if href.endswith(f'.{fmt}') or f'/dl/{internal_id}' in href:
            return normalize(href)
    
    # Estrategia 3: Botones con clases download/btn
    for btn in soup.select('a[class*="download"], button[class*="download"], '
                           'a[class*="btn"], button[class*="btn"]'):
        href = btn.get('href') or btn.get('data-url') or btn.get('data-link')
        if href:
            return normalize(href)
```

## Manejo de Errores
- `search()`: Prueba 3 URLs de búsqueda. Si ninguna funciona → return `[]`
- `get_download_url()`: Prueba 4 patrones de URL + 3 estrategias de búsqueda por cada una

## Trampas / Problemas Conocidos

1. **Dominio altamente inestable** — Z-Library es el provider con más cambios de dominio. El `DomainResolver` es crítico.
2. **Múltiples layouts** — Z-Library ha tenido varios rediseños. El código intenta card-based (moderno) y link-based (antiguo).
3. **Validación de extensión** — Solo acepta formatos conocidos (`epub`, `mobi`, `pdf`, `azw3`, `fb2`, `djvu`, `txt`).
4. **Validación de respuesta** — Verifica `len(resp.text) > 500` para evitar páginas de error/bloqueo que devuelven 200.

## Archivos
- `app/providers/books/zlibrary.py`
- `config.py` — `ZLIBRARY_ENABLED`, `ZLIBRARY_DOMAIN`
