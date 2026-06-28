# Estrategia: DonTorrent

## Provider ID: `dontorrent`

## Propósito

Documenta la estrategia de scraping para DonTorrent (`dontorrent.reisen`, dominio variable), un sitio de torrents de películas y series en español. Sirve como **fallback** de MejorTorrent.

## URLs del Sitio

| Componente | Patrón URL | Ejemplo |
|------------|------------|---------|
| Listado películas | `/peliculas` | `https://dontorrent.reisen/peliculas` |
| Listado películas HD | `/peliculas/hd` | `https://dontorrent.reisen/peliculas/hd` |
| Listado películas 4K | `/peliculas/4K` | `https://dontorrent.reisen/peliculas/4K` |
| Listado series | `/series` | `https://dontorrent.reisen/series` |
| Listado series HD | `/series/hd` | `https://dontorrent.reisen/series/hd` |
| Detalle película | `/pelicula/{id}/{slug}` | Mismo esquema que MejorTorrent |
| Detalle serie | `/serie/{id}/{slug}` | Mismo esquema que MejorTorrent |

## Requisitos Especiales

- **Sin búsqueda GET pública** — DonTorrent no tiene endpoint de búsqueda. En su lugar, navega listados.
- **Dominio altamente inestable** — Cambia semanalmente. Requiere `DomainResolver`.
- **IDs compartidos con MejorTorrent** — Usa el mismo esquema de IDs numéricos.
- **Deshabilitado por defecto** — `DONTORRENT_ENABLED=False`

## Constructor

```python
def __init__(self, http_client, domain_resolver=None):
    base_url = settings.DONTORRENT_DOMAIN
    if domain_resolver:
        active_domain = domain_resolver.get_current("dontorrent")
        if active_domain:
            base_url = active_domain
    super().__init__(
        http_client=http_client,
        provider_id="dontorrent",
        display_name="DonTorrent",
        base_url=base_url
    )
```

## Capacidades

```python
def get_capabilities(self) -> ProviderCapabilities:
    return ProviderCapabilities(
        provider_id=self.provider_id,
        display_name=self.display_name,
        supported_categories=[2000, 2030, 2040, 2045, 5000, 5030, 5040],
        supported_search_params=["q"],
        supports_tv_search=True,
        supports_movie_search=True,
    )
```

## Estrategia de Búsqueda (`search()`)

### Estrategia: Navegar listados + filtrar por query

Como DonTorrent no tiene endpoint de búsqueda, se navegan los listados de contenido y se filtra localmente:

```python
async def search(self, query, categories, **kwargs):
    results = []
    cat = categories[0] if categories else None
    
    # Scrapear listados según categoría
    if not cat or CategoryMapper.is_movie_category(cat):
        results.extend(await self._scrape_listings("/peliculas"))
        results.extend(await self._scrape_listings("/peliculas/hd"))
        results.extend(await self._scrape_listings("/peliculas/4K"))
    
    if not cat or CategoryMapper.is_tv_category(cat):
        results.extend(await self._scrape_listings("/series"))
        results.extend(await self._scrape_listings("/series/hd"))
    
    # Filtrar por query localmente
    if query:
        normalized = self.normalize_query(query)
        results = [
            r for r in results
            if normalized in self.normalize_query(r.title)
        ]
    
    # Paginación manual
    if offset:
        results = results[offset:]
    return results[:limit]
```

### Parsing de listados

```python
def _parse_results(self, html: str) -> list[SearchResult]:
    soup = BeautifulSoup(html, "lxml")
    results = []
    
    for link in soup.select('a[href*="/pelicula/"], a[href*="/serie/"]'):
        href = link.get("href", "")
        title = link.get_text(strip=True)
        
        match = re.search(r'/(pelicula|serie)/(\d+)/', href)
        if not match:
            continue
        
        content_type = match.group(1)
        item_id = match.group(2)
        
        categories = [2000, 2030] if content_type == "pelicula" else [5000, 5030]
        
        result = SearchResult(
            title=title,
            guid=f"dontorrent-{item_id}",
            link=f"{self.base_url}{href}" if href.startswith('/') else href,
            download_url="",
            size_bytes=0,
            pub_date=datetime.now(),
            categories=categories,
            seeders=50,
            peers=50,
        )
        results.append(result)
    
    return results
```

### Descarga

```python
async def get_download_url(self, internal_id: str) -> str:
    """El download_url ya es la URL directa."""
    return internal_id
```

Similar a MejorTorrent: devuelve el `internal_id` directamente (ya es la URL del .torrent).

## Diferencias con MejorTorrent

| Característica | MejorTorrent | DonTorrent |
|---------------|-------------|------------|
| Búsqueda GET | Sí (`/busqueda?q=`) | No (usa listados) |
| Enriquecimiento | Sí (visita detalle) | No (solo listados) |
| IMDb → TMDB | Sí | No |
| Episodios por serie | Sí (un result por .torrent) | No (result único) |
| Seeders simulados | 50 | 50 |
| Calidad mapeada | Sí (QUALITY_MAP) | No (usa defaults) |

## Uso como Fallback

DonTorrent comparte el esquema de IDs con MejorTorrent:

```
MejorTorrent: /pelicula/30403/infierno-bajo-cero
DonTorrent:   /pelicula/30403/infierno-bajo-cero  (mismo ID)
```

Si MejorTorrent está caído, se puede intentar DonTorrent con los mismos IDs.

## Trampas / Problemas Conocidos

1. **Sin búsqueda real** — Navega listados y filtra localmente. Si el contenido no está en las primeras páginas de listados, no se encuentra.
2. **Sin enriquecimiento** — No visita páginas de detalle, por lo que `download_url` queda vacío y no se pueden descargar archivos.
3. **Dominio muy inestable** — Cambia semanalmente. El `DomainResolver` es obligatorio.
4. **Deshabilitado por defecto** — Requiere `WTR_DONTORRENT_ENABLED=true` en `.env`.

## Archivos
- `app/providers/video/dontorrent.py`
- `tests/test_provider_dontorrent.py`
