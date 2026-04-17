# WebTranslatarr - Guía para Agentes

## Visión General

WebTranslatarr es un proxy Torznab universal que actúa como capa de traducción entre aplicaciones *Arr (Readarr, Sonarr, Radarr) y fuentes de contenido heterogéneas (Ebookelo para libros, MejorTorrent/DonTorrent para video).

El sistema NO es un indexer de torrents tradicional. Traduce fuentes de descarga directa (DDL) al formato Torznab.

## Stack Tecnológico

- **Framework**: FastAPI (Python 3.11+)
- **HTTP Client**: httpx con rate-limiting y retry
- **Parsing HTML**: BeautifulSoup4 + lxml
- **Configuración**: Pydantic Settings (.env)
- **Testing**: pytest

## Cómo Arrancar

```bash
# Desarrollo local
pip install -r requirements.txt
python main.py

# Con Docker
docker-compose up -d
```

El servidor escucha en `http://localhost:9117` (puerto estándar Jackett).

## Estructura de Módulos

```
app/
├── api/           # Endpoints FastAPI (torznab.py, health.py)
├── core/          # Modelos, enums, categorías, excepciones
├── providers/     # Implementaciones de providers
│   ├── books/     # EbookeloProvider
│   └── video/     # MejorTorrentProvider, DonTorrentProvider
├── routing/       # SmartRouter - enrutamiento por tipo de contenido
├── scraping/      # HttpClient, parser helpers
├── services/      # Download proxy, cache
└── torznab/       # Mapeo a XML (mapper.py, caps.py, errors.py)
```

## Convenciones Importantes

### Providers
- Heredar de `BaseProvider` (ABC)
- Implementar: `search()`, `get_download_url()`, `get_capabilities()`
- No interactuar directamente con formato Torznab - solo devolver `SearchResult`
- Usar `self.http_client` para requests (rate-limiting integrado)

### Categorías Newznab
- Libros: 7000, 7020, 8000, 8010 (Readarr busca en ambos rangos)
- Películas: 2000, 2030, 2040, 2045
- TV: 5000, 5030, 5040, 5045

## Qué NO Hacer

- **NUNCA seguir enlaces de profitablecpmgate.com** (trampa publicitaria de Ebookelo)
- No hardcodear URLs de providers - usar configuración
- No hacer requests síncronos - todo es async/await
- No parsear XML manualmente - usar ElementTree

## Endpoints Principales

| Endpoint | Descripción |
|----------|-------------|
| `GET /api?t=caps` | Capabilities del proxy |
| `GET /api?t=search&q=...` | Búsqueda genérica |
| `GET /api?t=book&q=...` | Búsqueda de libros |
| `GET /api?t=movie&imdbid=...` | Búsqueda de películas |
| `GET /api?t=tvsearch&q=...` | Búsqueda de series |
| `GET /api/download?provider=...&id=...` | Proxy de descarga |
