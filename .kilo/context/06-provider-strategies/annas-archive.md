# Estrategia: Anna's Archive

## Provider ID: `annasarchive`

## Propósito

Documenta la estrategia de scraping para Anna's Archive (`annas-archive.gl`), un meta-buscador de libros que agrega resultados de Library Genesis, Z-Library y otras fuentes.

## URLs del Sitio

| Componente | Patrón URL | Ejemplo |
|------------|------------|---------|
| Dominio principal | Variable (resuelto dinámicamente) | `https://annas-archive.gl` |
| Mirrors | Hardcodeados como fallback | `.pk`, `.gd` |
| Búsqueda | `/search?q={query}&lang=es&ext=epub` | `https://annas-archive.gl/search?q=quijote&lang=es&ext=epub` |
| Detalle | `/md5/{md5_hash}` | `https://annas-archive.gl/md5/a1b2c3d4e5f6...` |
| Descarga | Variable (slow partner server, libgen mirrors) | Depende de la fuente |

La URL de búsqueda se construye con `urlencode(..., quote_via=quote_plus)` para manejar caracteres especiales y espacios correctamente.

## Resolución de Dominio

Anna's Archive cambia de dominio frecuentemente. El sistema usa dos mecanismos:

### ShadowLibrariesStrategy (prioridad máxima)

Escrapea `https://shadowlibraries.github.io/DirectDownloads/AnnasArchive/` (GitHub Pages, sin Cloudflare). Extrae enlaces que contengan `annas-archive`, limpia query params `?r=...` con `urlparse`, y valida cada candidato con HTTP HEAD. Es la primera estrategia en ejecutarse.

Selector: `soup.select('a[href*="annas-archive"]')`

### Mirrors hardcodeados (fallback)

Si ShadowLibraries falla, se usan mirrors configurados en `_DOMAIN_CONFIGS`:
- `https://annas-archive.gl`
- `https://annas-archive.pk`
- `https://annas-archive.gd`

Cada mirror se valida con `_validate_domain()` en el DomainResolver.

## Requisitos Especiales

- **Cloudscraper requerido:** `use_scraper=True` — Anna's Archive tiene protección Cloudflare fuerte.
- **FlareSolverr fallback:** Si cloudscraper falla y `FLARESOLVERR_URL` está configurado, se reintenta con FlareSolverr.
- **Rate limit reducido:** 0.5 req/s (en vez del default 2.0) para evitar detección anti-bot.
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

## Métodos Helper (NUEVOS)

### `_fetch(url, use_flaresolverr_fallback=True)`

Wrapper para todas las requests HTTP. Usa cloudscraper con `rate_limit=0.5`. Si falla y `FLARESOLVERR_URL` está configurado, reintenta con FlareSolverr.

```python
async def _fetch(self, url: str, use_flaresolverr_fallback: bool = True):
    try:
        return await self.http_client.get(url, use_scraper=True, rate_limit=0.5)
    except Exception:
        if use_flaresolverr_fallback and settings.FLARESOLVERR_URL:
            self.logger.warning("cloudscraper failed, falling back to FlareSolverr")
            try:
                return await self.http_client.get(url, use_flaresolverr=True, rate_limit=0.5)
            except Exception as e2:
                self.logger.error(f"FlareSolverr fallback also failed: {e2}")
        raise
```

### `_is_cloudflare_challenge(soup) → bool`

Detecta si la respuesta HTML es un challenge de Cloudflare en vez de contenido real:

```python
def _is_cloudflare_challenge(self, soup: BeautifulSoup) -> bool:
    title_text = (soup.title.get_text().lower() if soup.title else '')
    if 'just a moment' in title_text:
        return True
    if soup.select_one('#challenge-error-text, .cf-browser-verification, #cf-challenge-running'):
        return True
    return False
```

### `_extract_title(a_tag) → str | None`

Selector multicapa para extracción de títulos (4 capas):

```python
def _extract_title(self, a_tag) -> str | None:
    # Capa 1: h1-h4 (semántico)
    for h in ('h3', 'h2', 'h1', 'h4'):
        el = a_tag.find(h)
        if el: return el.get_text(strip=True)
    
    # Capa 2: Tailwind classes conocidas
    for sel in ('div.text-xl', 'div.font-bold', 'div.truncate', 'span.text-lg'):
        el = a_tag.select_one(sel)
        if el: return el.get_text(strip=True)
    
    # Capa 3: Cualquier div/span con texto sustancial
    for el in a_tag.find_all(['div', 'span']):
        text = el.get_text(strip=True)
        if len(text) >= 3: return text
    
    # Capa 4: Texto directo del <a>
    text = a_tag.get_text(strip=True)
    return text if len(text) >= 3 else None
```

### `_find_download_url(soup) → str | None`

Selector multicapa para enlaces de descarga (5 capas):

```python
def _find_download_url(self, soup) -> str | None:
    # Capa 1: js-download-link con texto clave
    # Capa 2: js-download-link cualquiera
    # Capa 3: data-download / data-partner
    # Capa 4: Texto del enlace contiene keywords
    # Capa 5: href contiene /download/ o libgen.*
```

### `_normalize_link(href) → str`

Convierte URLs relativas a absolutas usando `self.base_url`.

## Estrategia de Búsqueda (`search()`)

### 1. Construir URL (con URL-encoding)
```python
params = urlencode({'q': query_to_use, 'lang': lang_code, 'ext': 'epub'}, quote_via=quote_plus)
search_url = f"{self.base_url}/search?{params}"
```

### 2. Selector de resultados
```python
soup.select('a[href*="/md5/"]')
```

### 3. Extracción del título
Usa `_extract_title()` multicapa (4 capas).

### 4. Detección de Cloudflare
Antes de parsear resultados, verifica `_is_cloudflare_challenge()`. Si detecta challenge, log error y retorna `[]`.

### 5. Construcción de SearchResult
```python
SearchResult(
    title=title_text,
    guid=f"annasarchive-{internal_id}",
    link=f"{self.base_url}{href}",
    download_url=f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={internal_id}&fmt=epub",
    size_bytes=1000000,
    pub_date=datetime.now(),
    categories=[7000, 7020, 8000, 8010],
    description=f"Libro: {title_text}",
)
```

## Estrategia de Descarga (`get_download_url()`)

Usa `_find_download_url()` multicapa con 5 niveles de fallback. También verifica `_is_cloudflare_challenge()` antes de parsear.

## is_healthy() (NUEVO — override)

```python
async def is_healthy(self) -> bool:
    try:
        resp = await self.http_client.get(self.base_url, use_scraper=True, rate_limit=0.5)
        if resp.status_code != 200:
            return False
        soup = BeautifulSoup(resp.text, 'lxml')
        return not self._is_cloudflare_challenge(soup)
    except Exception:
        return False
```

Usa cloudscraper explícitamente (el default `is_healthy()` usa HTTP simple que falla con Cloudflare). Verifica que la respuesta no sea un challenge.

## Manejo de Errores
- `search()`: Excepciones capturadas → log + return `[]`. CF challenge detectado → log error + return `[]`.
- `get_download_url()`: Excepciones capturadas → log + return `None`. CF challenge → return `None`.
- `browse()`: Igual que search().
- `is_healthy()`: Cualquier excepción → return `False`.

## Trampas / Problemas Conocidos

1. **Cloudflare fuerte** — Anna's Archive tiene protección anti-bot agresiva. Sin cloudscraper, las requests fallan. FlareSolverr es el fallback.
2. **Las clases CSS pueden cambiar** — Los selectores multicapa (4 para títulos, 5 para downloads) minimizan el impacto.
3. **MD5 como ID** — Los IDs son hashes largos. Asegurarse de no truncarlos.
4. **"Slow Partner Server" puede no estar disponible** — El fallback multicapa a otros mirrors es necesario.
5. **Dominio cambia frecuentemente** — ShadowLibrariesStrategy + mirrors hardcodeados como fallback.

## Archivos
- `app/providers/books/annas_archive.py`
- `tests/test_provider_annas_archive.py`
