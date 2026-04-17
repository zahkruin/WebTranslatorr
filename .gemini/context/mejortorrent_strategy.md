# Estrategia de Scraping - MejorTorrent

## URLs del Sitio

| Componente | Patrón URL | Ejemplo |
|------------|------------|---------|
| Búsqueda | `/busqueda?q={query}` | `/busqueda?q=Infierno` |
| Búsqueda paginada | `/busqueda/page/{n}?q={query}` | `/busqueda/page/2?q=Infierno` |
| Película | `/pelicula/{id}/{slug}` | `/pelicula/30403/Infierno-bajo-cero` |
| Serie | `/serie/{id}/{id}/{slug}` | `/serie/126290/126290/El-ultimo-refugio` |
| Torrent película | `/torrents/peliculas/{filename}.torrent` | `/torrents/peliculas/...` |
| Torrent serie | `/torrents/series/{filename}.torrent` | `/torrents/series/...` |

## Hallazgos Clave

1. **Enlaces directos a .torrent**: No hay ad-gates ni pasos intermedios
2. **Un .torrent por episodio** para series
3. **Dominio variable**: El número de subdominio cambia (`www42`, `www43`, etc.)

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
    "DVDRip": 2030,       # Movies > SD
    "BluRay-1080p": 2040, # Movies > HD
    "MicroHD-1080p": 2040,
    "4K": 2045,           # Movies > UHD
    "HDTV": 5030,         # TV > SD
    "HDTV-720p": 5040,    # TV > HD
    "HDTV-1080p": 5040,   # TV > HD
}
```

## Series: Un Resultado por Episodio

```python
for i, tlink in enumerate(torrent_links, 1):
    ep_result = SearchResult(
        title=f"{result.title} - E{i:02d}",
        guid=f"{result.guid}-e{i:02d}",
        download_url=torrent_url,
        season=season_num,
        episode=i,
        ...
    )
```

## Resolución IMDb → Título Español

Para cuando Radarr envía `imdbid` en lugar de query:

```python
# Usar TMDB API
tmdb_url = f"https://api.themoviedb.org/3/find/{imdb_id}"
params = {
    "external_source": "imdb_id",
    "language": "es-ES",
    "api_key": TMDB_API_KEY,
}
```

## DonTorrent como Fallback

DonTorrent comparte el mismo esquema de IDs con MejorTorrent. Si MejorTorrent está caído, se puede intentar construir la URL de DonTorrent directamente:

```
MejorTorrent: /pelicula/30403/infierno-bajo-cero
DonTorrent:   /pelicula/30403/infierno-bajo-cero  (mismo ID!)
```
