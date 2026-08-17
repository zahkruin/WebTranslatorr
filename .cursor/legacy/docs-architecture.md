# Arquitectura Técnica

## Diagrama de Flujo

```
┌─────────────┐     Torznab API      ┌──────────────────┐
│  Sonarr/    │ ───────────────────► │  WebTranslatorr  │
│  Radarr/    │                      │  (FastAPI)       │
│  Readarr    │ ◄──────────────────  │                  │
└─────────────┘     XML RSS          └────────┬─────────┘
                                              │
                          ┌───────────────────┼───────────────────┐
                          │                   │                   │
                          ▼                   ▼                   ▼
                   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
                   │  Ebookelo   │     │ MejorTorrent│     │ DonTorrent  │
                   │  Provider   │     │  Provider   │     │  Provider   │
                   └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
                          │                   │                   │
                          ▼                   ▼                   ▼
                   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
                   │ ww2.ebookelo│     │www42.mejor- │     │ dontorrent. │
                   │   .com      │     │torrent.eu   │     │   reisen    │
                   └─────────────┘     └─────────────┘     └─────────────┘
```

## Componentes Principales

### SmartRouter
Determina qué providers usar según:
- `t` parameter (book, movie, tvsearch)
- `cat` parameter (categorías Newznab)
- `imdbid`, `author` (parámetros específicos)

### ProviderRegistry
Registro central de providers disponibles. Patrón Service Locator.

### HttpClient
Wrapper de httpx con:
- Rotación de User-Agents
- Rate limiting por dominio
- Reintentos exponenciales

### TorznabMapper
Convierte `SearchResult` → XML RSS 2.0 con namespaces Torznab.

## Modelo de Datos

```
SearchResult
├── title, guid, link
├── download_url (ruta al proxy de descarga)
├── size_bytes, pub_date
├── categories (Newznab IDs)
├── author (libros)
├── imdb_id, tvdb_id, season, episode (video)
└── seeders, peers (simulados para DDL)
```

## Flujo de Descarga

1. *Arr recibe XML con `enclosure url="/api/download?provider=X&id=Y&fmt=Z"`
2. Usuario selecciona resultado en *Arr
3. *Arr hace GET al endpoint de descarga
4. WebTranslatorr resuelve URL final vía `provider.get_download_url()`
5. WebTranslatorr descarga archivo y lo sirve al *Arr
