# 13 — API Endpoints

## Propósito

Documenta todos los endpoints HTTP de WebTranslatorr, sus parámetros, respuestas, y cómo los consumen las aplicaciones *Arr (Readarr, Sonarr, Radarr).

Cuándo consultar: para entender el contrato de la API, depurar peticiones, o añadir nuevos endpoints.

---

## Endpoints

### `GET /api` — Torznab Multi-Provider

**Archivo:** `app/api/torznab.py:230-288`

Endpoint principal compatible con el estándar Torznab/Newznab. Busca en TODOS los providers registrados.

**URL en *Arr:**
```
http://webtranslatorr:9811/api?apikey=xxx
```

**Parámetros:**
| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `t` | string | No | Función: `caps`, `search`, `tvsearch`, `movie`, `book` |
| `q` | string | No | Query de búsqueda |
| `cat` | string | No | Categorías Newznab (comma-separated, ej: `7000,7020`) |
| `apikey` | string | Sí | API key de autenticación |
| `offset` | int | No | Offset de paginación (default: 0) |
| `limit` | int | No | Límite de resultados (default: 50, max: 100) |
| `imdbid` | string | No | IMDb ID (ej: `tt1234567`) |
| `tvdbid` | string | No | TVDB ID |
| `season` | string | No | Número de temporada |
| `ep` | string | No | Número de episodio |
| `author` | string | No | Autor (book-search) |
| `title` | string | No | Título (book-search) |

**Respuestas:**
- `200` — XML RSS 2.0 con resultados (Torznab/Newznab)
- `200` — XML de error (API key incorrecta, código 100)

**Flujo:**
1. Validar API key
2. Si `t=caps` → devolver capabilities XML (agregadas de todos los providers)
3. Si otro `t` → `SmartRouter.route(params)` → providers seleccionados
4. Búsqueda paralela en providers con caché
5. Merge, paginación, XML response

---

### `GET /api/{provider_id}` — Torznab Single-Provider (Multi-Indexer)

**Archivo:** `app/api/torznab.py:345-410`

Permite usar cada provider como un indexer independiente en las *Arr apps.

**URL en *Arr:**
```
http://webtranslatorr:9811/api/epublibre?apikey=xxx
http://webtranslatorr:9811/api/lectulandia?apikey=xxx
http://webtranslatorr:9811/api/libgen?apikey=xxx
http://webtranslatorr:9811/api/mejortorrent?apikey=xxx
```

**Parámetros:** Igual que `/api`, más:
| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `provider_id` | string | Sí (en path) | ID del provider (ej: `epublibre`, `mejortorrent`) |

**Provider IDs válidos:**
`ebookelo`, `epublibre`, `lectulandia`, `espaebook`, `holaebook`, `annasarchive`, `epubflix1`, `libgen`, `booobook`, `lectuepublibre5`, `mundoepublibre1`, `zlibrary`, `mejortorrent`, `dontorrent`

**Respuestas:**
- `200` — XML RSS 2.0 con resultados de ese provider
- `200` — XML de error si el provider no existe

**Ventajas del multi-indexer:**
- Readarr muestra cada provider como una fuente separada
- Se puede ver qué provider encontró cada resultado
- Se pueden deshabilitar providers individualmente desde Readarr

---

### `GET /api/download` — Download Proxy

**Archivo:** `app/api/torznab.py:291-342`

Endpoint de descarga. Las *Arr apps llaman a este endpoint cuando el usuario selecciona un resultado para descargar.

**Parámetros:**
| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `provider` | string | Sí | ID del provider |
| `id` | string | Sí | ID interno del contenido |
| `fmt` | string | No | Formato del archivo (default: `epub`) |

**Formatos soportados:**
| Formato | Content-Type |
|---------|-------------|
| `epub` | `application/epub+zip` |
| `mobi` | `application/x-mobipocket-ebook` |
| `pdf` | `application/pdf` |
| `torrent` | `application/x-bittorrent` |

**Flujo:**
1. Obtener provider del registry
2. `provider.get_download_url(internal_id)` → URL final
3. `http_client.download_file(final_url)` → bytes del archivo
4. Si `provider.is_zipped` → extraer EPUB del ZIP
5. Servir bytes con Content-Type y Content-Disposition

**Compatibilidad con Ebookelo:**
Para `provider=ebookelo`, el `id` se interpreta como `"{book_id}/{fmt}"`. Para otros providers, `id` es el internal_id directo y `fmt` se pasa como `**kwargs`.

---

### `GET /health` — Health Check

**Archivo:** `app/api/health.py`

**Respuesta:**
```json
{"status": "healthy", "service": "WebTranslatorr"}
```

---

### `GET /api/domains` — Estado de Dominios

**Archivo:** `app/api/domains.py:10-28`

Devuelve el estado actual de resolución de todos los dominios.

**Respuesta:**
```json
{
  "mejortorrent": {
    "url": "https://www42.mejortorrent.eu",
    "resolved_at": "2026-06-08T07:10:45+00:00",
    "source": "privtree",
    "healthy": true,
    "last_health_check": "2026-06-08T07:10:45+00:00"
  },
  ...
}
```

---

### `POST /api/domains/refresh` — Forzar Resolución Global

**Archivo:** `app/api/domains.py:31-43`

Fuerza la resolución inmediata de todos los dominios.

**Respuesta:**
```json
{
  "message": "Domain resolution complete",
  "domains": { ... }
}
```

---

### `POST /api/domains/refresh/{provider_id}` — Forzar Resolución Individual

**Archivo:** `app/api/domains.py:46-63`

Fuerza la resolución del dominio de un provider específico.

**Respuesta (éxito):**
```json
{
  "message": "Domain resolved for mejortorrent",
  "domain": "https://www42.mejortorrent.eu",
  "details": { ... }
}
```

**Respuesta (error):**
```json
{"error": "Provider 'xyz' not registered for domain resolution"}
```
(HTTP 404)

---

### `GET /api/domains/health/{provider_id}` — Health Check de Dominio

**Archivo:** `app/api/domains.py:66-83`

Ejecuta un health check del dominio actual de un provider.

**Respuesta:**
```json
{
  "provider_id": "mejortorrent",
  "healthy": true,
  "details": { ... }
}
```

---

### `GET /api/admin/providers` — Listar Providers (Admin)

**Archivo:** `app/api/admin.py`

Lista todos los providers con su configuración actual desde la base de datos, enriquecida con capabilities del registry.

**Autenticación:** Ninguna (panel de administración local).

**Respuesta:**
```json
{
  "providers": [
    {
      "provider_id": "ebookelo",
      "display_name": "Ebookelo",
      "enabled": true,
      "domain": "https://ww2.ebookelo.com",
      "capabilities": {
        "supports_book_search": true,
        "supports_movie_search": false,
        "supports_tv_search": false,
        "categories": [7000, 7020, 8000, 8010]
      }
    }
  ]
}
```

---

### `PUT /api/admin/providers/{provider_id}` — Actualizar Provider (Admin)

**Body:**
```json
{"enabled": false, "domain": "https://nuevo-dominio.com"}
```

Ambos campos son opcionales. Si `enabled` cambia, se recarga el registry automáticamente.

**Respuesta:** `{"status": "ok", "provider_id": "ebookelo"}`

---

### `POST /api/admin/providers/reload` — Recargar Registry (Admin)

Fuerza la recarga del registry desde la DB. Útil tras cambios de dominio o enable/disable.

**Respuesta:** `{"status": "reloaded", "provider_count": 16}`

---

### `GET /api/admin/settings` — Listar Settings (Admin)

**Respuesta:**
```json
{
  "settings": {
    "api_key": "my-secret-key",
    "external_url": "http://localhost:9811",
    "tmdb_api_key": "",
    "google_books_api_key": "",
    "http_proxy": ""
  }
}
```

---

### `PUT /api/admin/settings/{key}` — Actualizar Setting (Admin)

**Body:** `{"value": "nuevo-valor"}`

**Respuesta:** `{"status": "ok", "key": "api_key", "value": "nuevo-valor"}`

---

### `GET /api/admin/readarr` — Listar Instancias Readarr (Admin)

**Respuesta:**
```json
{
  "instances": [
    {"id": 1, "name": "Main Readarr", "url": "http://readarr:8787", "api_key": "...", "enabled": 1}
  ]
}
```

---

### `POST /api/admin/readarr` — Añadir Instancia Readarr (Admin)

**Body:** `{"name": "Main Readarr", "url": "http://readarr:8787", "api_key": "xxx"}`

**Respuesta (201):** `{"status": "created", "id": 1}`

---

### `PUT /api/admin/readarr/{id}` — Actualizar Instancia Readarr (Admin)

**Body:** `{"name": "New Name", "url": "http://nueva-url:8787", "api_key": "xxx", "enabled": true}`

Todos los campos son opcionales.

---

### `DELETE /api/admin/readarr/{id}` — Eliminar Instancia Readarr (Admin)

**Respuesta:** `{"status": "deleted", "id": 1}`

---

### `POST /api/admin/readarr/{id}/sync` — Sincronizar con Readarr (Admin)

Sincroniza los providers de libros activos como indexers Torznab en la instancia Readarr configurada. Crea indexers nuevos, actualiza existentes, y opcionalmente elimina huérfanos.

**Respuesta:**
```json
{
  "success": true,
  "created": 3,
  "updated": 12,
  "failed": 1,
  "deleted": 0,
  "details": [...]
}
```

---

### `POST /api/admin/readarr/{id}/test` — Test de Conexión Readarr (Admin)

Prueba conectividad con la instancia Readarr.

**Respuesta:**
```json
{"success": true, "message": "Connected", "version": "0.4.12.4567"}
```

---

## Códigos de Error Torznab

**Archivo:** `app/torznab/errors.py`

| Código | Significado | Cuándo |
|--------|------------|--------|
| 100 | Incorrect API Key | API key no coincide con `WTR_API_KEY` |
| 200 | No search results found | Búsqueda no devuelve resultados |
| 201 | Missing search parameter | Falta el parámetro `q` |
| 202 | Invalid category | Categoría no soportada |
| 500 | Server error | Error interno (provider caído, timeout, etc.) |

El error se devuelve como XML:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<error code="100" description="Incorrect API Key"/>
```

---

## Configuración en *Arr Apps

### Readarr (libros)
```
URL: http://webtranslatorr:9811/api
API Key: {WTR_API_KEY}
Categories: 7000,7020,8000,8010
```

### Radarr (películas)
```
URL: http://webtranslatorr:9811/api
API Key: {WTR_API_KEY}
Categories: 2000,2030,2040,2045
```

### Sonarr (series)
```
URL: http://webtranslatorr:9811/api
API Key: {WTR_API_KEY}
Categories: 5000,5030,5040,5045
```

---

## Archivos Relevantes

| Archivo | Rol |
|---------|-----|
| `app/api/torznab.py` | Endpoints Torznab y download |
| `app/api/health.py` | Health check |
| `app/api/domains.py` | Endpoints de dominios |
| `app/api/admin.py` | Endpoints de administración (providers, settings, Readarr) |
| `app/torznab/errors.py` | Códigos de error XML |
| `app/torznab/mapper.py` | Generación de XML de respuesta |
| `app/torznab/caps.py` | Generación de XML de capabilities |
