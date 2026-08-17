# Estrategia: MejorTorrent

## Provider ID: `mejortorrent`

## Propósito

Documenta la estrategia de scraping para MejorTorrent (`mejortorrent.eu`, dominio variable), un tracker de torrents de películas y series en español. Es el provider de video principal.

## URLs del Sitio

| Componente | Patrón URL | Ejemplo |
|------------|------------|---------|
| Búsqueda | `/busqueda?q={query}` | `/busqueda?q=Infierno` |
| Búsqueda paginada | `/busqueda/page/{n}?q={query}` | `/busqueda/page/2?q=Infierno` |
| Película | `/pelicula/{id}/{slug}` | `/pelicula/30403/Infierno-bajo-cero` |
| Serie | `/serie/{id}/{id}/{slug}` | `/serie/126290/126290/El-ultimo-refugio` |
| Torrent película | `/torrents/peliculas/{filename}.torrent` | Descarga directa |
| Torrent serie | `/torrents/series/{filename}.torrent` | Descarga directa |

## Hallazgos Clave

1. **Enlaces directos a .torrent**: No hay ad-gates ni pasos intermedios
2. **Un .torrent por episodio** para series
3. **Dominio variable**: El número de subdominio cambia (`www42`, `www43`, etc.)

## Capacidades

```python
def get_capabilities(self) -> ProviderCapabilities:
    return ProviderCapabilities(
        provider_id=self.provider_id,
        display_name=self.display_name,
        supported_categories=[2000, 2030, 2040, 2045, 5000, 5030, 5040, 5045],
        supported_search_params=["q", "season", "ep", "imdbid"],
        supports_tv_search=True,
        supports_movie_search=True,
    )
```

## Selectores CSS

```python
# Resultados de búsqueda
soup.select('a[href*="/pelicula/"], a[href*="/serie/"], a[href*="/documental/"]')

# Enlaces a .torrent en página de detalle
soup.select('a[href$=".torrent"]')

# Género
soup.select('a[href*="/genre/"]')

# Año
soup.select_one('a[href*="/year/"]')
```

## Extracción de Calidad

Del título del resultado: `"Infierno bajo cero (DVDRip)"`

```python
quality_match = re.search(r'\(([^)]+)\)\s*$', full_text)
quality = quality_match.group(1) if quality_match else "DVDRip"
```

## Mapeo de Calidades a Categorías Newznab

```python
QUALITY_MAP = {
    "DVDRip": 2030,        # Movies > SD
    "BluRay-1080p": 2040,  # Movies > HD
    "MicroHD-1080p": 2040,
    "4K": 2045,            # Movies > UHD
    "HDTV": 5030,          # TV > SD
    "HDTV-720p": 5040,     # TV > HD
    "HDTV-1080p": 5040,    # TV > HD
    "SAT-Rip": 5030,
    "WEB-DL": 2080,
    "WEBRip": 2080,
}
```

## Estrategia de Enriquecimiento

MejorTorrent visita la página de detalle de cada resultado para extraer:
- Enlaces .torrent
- Descripción
- Año
- Géneros
- IMDb ID (si está disponible)

### Series: Un Resultado por Episodio

```python
if is_series:
    episode_results = []
    for i, tlink in enumerate(torrent_links, 1):
        torrent_url = tlink.get("href", "")
        season_num, episode_num = self._extract_season_episode(torrent_url, i)
        
        ep_result = SearchResult(
            title=f"{result.title} - E{episode_num:02d}",
            guid=f"{result.guid}-e{episode_num:02d}",
            download_url=torrent_url,
            season=season_num,
            episode=episode_num,
            seeders=50,
            peers=50,
        )
```

### Extracción de Temporada/Episodio del Nombre del Torrent

```python
def _extract_season_episode(self, torrent_name: str, fallback_ep: int):
    patterns = [
        r'(\d+)x(\d+)',               # 01x01
        r'Temporada\s*(\d+).*?(\d+)', # Temporada 1 01
        r'Capitulo\s*(\d+)',          # Capitulo 01
        r'Episodio\s*(\d+)',          # Episodio 01
    ]
```

## Resolución IMDb → Título Español

Cuando Radarr envía `imdbid` en lugar de query, se usa la API de TMDB:

```python
async def _resolve_imdb_to_spanish_title(self, imdb_id: str) -> str:
    if not settings.TMDB_API_KEY:
        return imdb_id
    
    tmdb_url = f"https://api.themoviedb.org/3/find/{imdb_id}"
    params = {
        "external_source": "imdb_id",
        "language": "es-ES",
        "api_key": settings.TMDB_API_KEY,
    }
    resp = await self.http_client.get(tmdb_url, params=params)
    data = resp.json()
    
    if data.get("movie_results"):
        return data["movie_results"][0].get("title", "")
```

## Descarga Directa

```python
async def get_download_url(self, internal_id: str) -> str:
    """El download_url ya es la URL directa al .torrent."""
    return internal_id
```

MejorTorrent sirve archivos .torrent directamente. No se necesita un paso de resolución adicional.

## Datos Simulados para DDL

Como es un tracker real (no DDL), se pueden usar seeders/peers reales. Actualmente se simulan con valor fijo:

```python
seeders=50,
peers=50,
```

## DonTorrent como Fallback

DonTorrent comparte el mismo esquema de IDs con MejorTorrent:

```
MejorTorrent: /pelicula/30403/infierno-bajo-cero
DonTorrent:   /pelicula/30403/infierno-bajo-cero  (mismo ID!)
```

Si MejorTorrent está caído, se puede construir la URL de DonTorrent con el mismo ID.

## Trampas / Problemas Conocidos

1. **Dominio variable** — El subdominio cambia frecuentemente (www42, www43...). El `DomainResolver` es crítico.
2. **TMDB API Key opcional** — Sin `WTR_TMDB_API_KEY`, la resolución IMDb→título falla y se usa el IMDb ID como query.
3. **Enriquecimiento pesado** — Visita la página de detalle de CADA resultado. Con muchos resultados, añade latencia significativa.
4. **Extracción de season/episode** — Depende del formato del nombre del archivo .torrent. Si cambia, los patrones regex pueden fallar.
5. **Limit aplicado post-enriquecimiento** — El parsing inicial no tiene límite, lo que puede resultar en sobrecarga si hay muchos resultados.

## Archivos
- `app/providers/video/mejortorrent.py`
- `tests/test_provider_mejortorrent.py`
