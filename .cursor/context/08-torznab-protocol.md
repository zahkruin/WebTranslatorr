# 08 — Protocolo Torznab/Newznab

## Propósito

Documenta el protocolo Torznab/Newznab que WebTranslatorr implementa: endpoints, formato XML RSS 2.0, namespaces, atributos requeridos por las *Arr apps, y cómo se genera el XML desde los `SearchResult`.

Cuándo consultar: para depurar el XML que reciben las *Arr apps, modificar el formato de respuesta, o entender los atributos Torznab.

---

## Especificación del Protocolo

Torznab es una extensión del estándar Newznab (usado por indexers de Usenet) adaptada para torrents. WebTranslatorr lo implementa para fuentes DDL (Direct Download Link), simulando seeders/peers.

### Endpoints que las *Arr Apps Esperan

| Parámetro `t` | Endpoint | Usado por | Descripción |
|---------------|----------|-----------|-------------|
| `caps` | `/api?t=caps` | Todos | Capacidades del indexer |
| `search` | `/api?t=search&q=...` | Todos | Búsqueda genérica |
| `book` | `/api?t=book&q=...&author=...` | Readarr | Búsqueda de libros |
| `movie` | `/api?t=movie&imdbid=...` | Radarr | Búsqueda de películas |
| `tvsearch` | `/api?t=tvsearch&q=...&season=...&ep=...` | Sonarr | Búsqueda de series |

### Parámetros de Búsqueda

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `q` | string | Query de búsqueda |
| `cat` | string | Categorías Newznab (comma-separated) |
| `offset` | int | Offset de paginación |
| `limit` | int | Límite de resultados (max 100) |
| `imdbid` | string | IMDb ID (ej: `tt1234567`) |
| `tvdbid` | string | TVDB ID |
| `season` | string | Número de temporada |
| `ep` | string | Número de episodio |
| `author` | string | Autor (book-search) |
| `title` | string | Título (book-search) |

---

## Formato XML de Respuesta

### Estructura RSS 2.0

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:torznab="http://torznab.com/schemas/2015/feed"
     xmlns:newznab="http://www.newznab.com/DTD/2010/feeds/attributes/">
  <channel>
    <title>WebTranslatorr</title>
    <description>Universal Torznab Proxy</description>
    <link>http://localhost:9811</link>
    <newznab:response offset="0" total="25"/>
    <item>
      <title>Título del libro</title>
      <guid>ebookelo-1828</guid>
      <link>https://ebookelo.com/ebook/1828/titulo</link>
      <description>Libro: Título del libro</description>
      <pubDate>Mon, 08 Jun 2026 07:00:00 +0000</pubDate>
      <enclosure url="http://localhost:9811/api/download?provider=ebookelo&id=1828&fmt=epub"
                 length="1000000"
                 type="application/x-bittorrent"/>
      <torznab:attr name="category" value="7000"/>
      <torznab:attr name="category" value="7020"/>
      <torznab:attr name="size" value="1000000"/>
      <torznab:attr name="seeders" value="100"/>
      <torznab:attr name="peers" value="100"/>
    </item>
  </channel>
</rss>
```

### Namespaces

| Namespace | URI | Uso |
|-----------|-----|-----|
| `torznab` | `http://torznab.com/schemas/2015/feed` | Atributos de torrent/indexer |
| `newznab` | `http://www.newznab.com/DTD/2010/feeds/attributes/` | Atributos de respuesta |

### Atributos Requeridos por las *Arr Apps

Cada `<item>` debe contener:

| Elemento/Atributo | Requerido | Descripción |
|-------------------|-----------|-------------|
| `<title>` | Sí | Título del contenido |
| `<guid>` | Sí | ID único (formato: `"{provider}-{id}"`) |
| `<link>` | Sí | URL de la página de detalle |
| `<enclosure url="..." length="..." type="..."/>` | Sí | URL de descarga (el *Arr descarga de aquí) |
| `torznab:attr name="category"` | Sí | Categoría Newznab (puede haber varias) |
| `torznab:attr name="size"` | Sí | Tamaño en bytes |
| `torznab:attr name="seeders"` | Recomendado | Seeders (simulado para DDL) |
| `torznab:attr name="peers"` | Recomendado | Peers (simulado para DDL) |
| `<pubDate>` | Recomendado | Fecha de publicación (RFC 822) |
| `torznab:attr name="imdbid"` | Películas | IMDb ID |
| `torznab:attr name="tvdbid"` | Series | TVDB ID |
| `torznab:attr name="season"` | Series | Temporada |
| `torznab:attr name="episode"` | Series | Episodio |

---

## TorznabMapper

**Archivo:** `app/torznab/mapper.py`

Convierte `SearchResult` → XML RSS 2.0.

### `results_to_xml(results, offset, total, channel_title) -> str`

Genera el XML RSS completo:

```python
@staticmethod
def results_to_xml(
    results: list,
    offset: int = 0,
    total: int = 0,
    channel_title: str = "WebTranslatorr"
) -> str:
```

### `_build_item(channel, result)`

Construye un `<item>` RSS a partir de un `SearchResult`:

1. `<title>`, `<guid>`, `<link>`, `<description>`
2. `<pubDate>` en formato RFC 822
3. `<enclosure>` con `url`, `length`, `type`
4. `<torznab:attr name="category">` por cada categoría
5. `<torznab:attr name="size">`
6. `<torznab:attr name="seeders">`, `<torznab:attr name="peers">` (si no son None)
7. `<torznab:attr name="infohash">`, `<torznab:attr name="magneturl">` (si existen)
8. `<torznab:attr name="imdbid">`, `<torznab:attr name="tvdbid">` (si existen)
9. `<torznab:attr name="season">`, `<torznab:attr name="episode">` (si existen)
10. `extra_attrs` como `<torznab:attr>` dinámicos

### Atributos Extra (extra_attrs)

El campo `extra_attrs: dict[str, str]` de `SearchResult` se serializa como atributos Torznab adicionales:

```python
for attr_name, attr_value in result.extra_attrs.items():
    SubElement(item, "torznab:attr", attrib={
        "name": attr_name, "value": attr_value
    })
```

Ejemplos de uso: `genre`, `quality`, `format`, `year`, `booktitle`.

---

## CapsGenerator

**Archivo:** `app/torznab/caps.py`

Genera el XML de capabilities (`/api?t=caps`):

```python
@staticmethod
def generate(providers: list[ProviderCapabilities]) -> str:
```

El XML incluye:
- **Server info:** versión, título, URL
- **Limits:** max y default de resultados
- **Searching:** qué tipos de búsqueda soporta (`search`, `book-search`, `tv-search`, `movie-search`)
- **Categories:** categorías y subcategorías disponibles

Las capabilities se agregan de todos los providers registrados.

---

## TorznabErrors

**Archivo:** `app/torznab/errors.py`

Genera XML de error estándar Torznab:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<error code="100" description="Incorrect API Key"/>
```

### Códigos de Error

| Código | Método | Significado |
|--------|--------|-------------|
| 100 | `incorrect_api_key()` | API key inválida |
| 101 | `account_suspended()` | Cuenta suspendida |
| 102 | `max_api_reached()` | Límite de API alcanzado |
| 103 | `max_download_reached()` | Límite de descargas alcanzado |
| 200 | `no_search_results()` | Sin resultados |
| 201 | `missing_search_param()` | Falta parámetro `q` |
| 202 | `invalid_category()` | Categoría inválida |
| 300 | `max_items_reached()` | Límite de items alcanzado |
| 500 | `server_error(msg)` | Error interno del servidor |

---

## Flujo de Generación de XML

```
1. SmartRouter.route(params) → lista de providers
2. asyncio.gather(provider.search() for each provider) → list[SearchResult]
3. Merge + paginación
4. TorznabMapper.results_to_xml(results, offset, total)
   ├── Crear <rss> root con namespaces
   ├── Crear <channel>
   ├── Añadir <newznab:response> con offset/total
   └── Por cada SearchResult → _build_item()
       ├── Campos básicos → <title>, <guid>, <link>, etc.
       ├── <enclosure> → URL de descarga
       ├── Categorías → <torznab:attr name="category">
       ├── Size, seeders, peers → <torznab:attr>
       ├── IMDb/TVDB/Season/Episode → <torznab:attr>
       └── extra_attrs → <torznab:attr> dinámicos
5. Response(content=xml, media_type="application/xml")
```

---

## Archivos Relevantes

| Archivo | Rol |
|---------|-----|
| `app/torznab/mapper.py` | SearchResult → XML RSS 2.0 |
| `app/torznab/caps.py` | Generación de capabilities XML |
| `app/torznab/errors.py` | Generación de errores XML |
| `app/api/torznab.py` | Endpoints que devuelven el XML |
| `app/core/models.py` | SearchResult (fuente de datos) |
| `context/09-categories.md` | Categorías Newznab |
