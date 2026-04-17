# Especificación Torznab/Newznab

## Endpoints

### t=caps
Devuelve las capabilities del indexer: categorías soportadas, tipos de búsqueda, parámetros.

### t=search
Búsqueda genérica. Parámetros:
- `q`: query string
- `cat`: categorías (comma-separated)
- `offset`, `limit`: paginación

### t=book
Búsqueda de libros. Parámetros adicionales:
- `author`: nombre del autor
- `title`: título del libro

### t=movie
Búsqueda de películas. Parámetros adicionales:
- `imdbid`: ID de IMDb (ej: tt1234567)

### t=tvsearch
Búsqueda de series. Parámetros adicionales:
- `tvdbid`: ID de TVDB
- `season`: número de temporada
- `ep`: número de episodio

## Formato XML RSS 2.0

Estructura base:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:torznab="..." xmlns:newznab="...">
  <channel>
    <title>WebTranslatarr</title>
    <description>...</description>
    <link>...</link>
    <newznab:response offset="0" total="10"/>
    <item>...</item>
  </channel>
</rss>
```

## Atributos Requeridos por los *Arr

Cada `<item>` debe tener:
- `title`: título del contenido
- `guid`: identificador único
- `link`: URL informativa
- `enclosure url="..." length="..." type="application/x-bittorrent"`: URL de descarga
- `torznab:attr name="category" value="..."`: categoría(s)
- `torznab:attr name="size" value="..."`: tamaño en bytes
- `torznab:attr name="seeders" value="..."`: seeders (simulado para DDL)
- `torznab:attr name="peers" value="..."`: peers (simulado para DDL)

## Namespaces

- `torznab`: http://torznab.com/schemas/2015/feed
- `newznab`: http://www.newznab.com/DTD/2010/feeds/attributes/
