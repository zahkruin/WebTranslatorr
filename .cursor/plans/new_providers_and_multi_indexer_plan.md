# Plan: Nuevos Providers + Multi-Indexer para Readarr

## Objetivo

1. **Añadir 6 nuevos providers** de libros a WebTranslatorr
2. **Separar Readarr en indexers individuales**: que cada provider de WebTranslatorr
   sea un indexer independiente en Readarr, con su propio path Torznab

---

## Parte 1: Nuevos Providers

### Lista de nuevos providers

| Provider ID | Display Name | Dominio por defecto | Tipo |
|---|---|---|---|
| `epubflix1` | Epubflix1 | `https://epubflix1.com` | Ebooks (WordPress-like) |
| `libgen` | Library Genesis | `https://libgen.ee` | Ebooks (search.php/md5) |
| `booobook` | B00k.Bond | `https://es.booobook.bond` | Ebooks (WordPress-like) |
| `lectuepublibre5` | LectuEpubLibre5 | `https://lectuepublibre5.com` | Ebooks (WordPress-like) |
| `mundoepublibre1` | MundoEpubLibre1 | `https://mundoepublibre1.com` | Ebooks (WordPress-like) |
| `zlibrary` | Z-Library | `https://z-library.sk` | Ebooks (singlelogin/search) |

### Archivos a modificar/crear

1. **`config.py`** → Añadir settings `_ENABLED` y `_DOMAIN` para cada provider
2. **`app/providers/books/epubflix1.py`** → Nuevo provider
3. **`app/providers/books/libgen.py`** → Nuevo provider  
4. **`app/providers/books/booobook.py`** → Nuevo provider
5. **`app/providers/books/lectuepublibre5.py`** → Nuevo provider
6. **`app/providers/books/mundoepublibre1.py`** → Nuevo provider
7. **`app/providers/books/zlibrary.py`** → Nuevo provider
8. **`app/api/torznab.py`** → Registrar providers + añadir rutas multi-indexer
9. **`app/server.py`** → Registrar DomainConfig para cada provider
10. **`.env.example`** → Añadir variables de entorno

---

## Parte 2: Multi-Indexer (Un path por provider)

### Problema actual

- Readarr configura **1 solo indexer** apuntando a `http://webtranslatorr:9811/api`
- WebTranslatorr busca en **todos los providers simultáneamente** y mezcla resultados
- No se puede saber qué provider encontró qué resultado
- Si un provider falla, afecta a toda la búsqueda

### Solución propuesta

Añadir rutas por provider en la API Torznab:

| Endpoint | Comportamiento |
|---|---|
| `GET /api` | (Existente) Busca en todos los providers - **backward compatible** |
| `GET /api/{provider_id}?t=book&q=...` | **Nuevo** - Busca SOLO en ese provider |
| `GET /api/{provider_id}?t=caps` | **Nuevo** - Capabilities de ese provider individual |

### Ventajas

1. Readarr puede tener **N indexers** configurados, cada uno con un path distinto
2. Cada provider se prueba independientemente
3. Si un provider falla, los demás siguen funcionando
4. Readarr puede decidir qué resultados priorizar por indexer
5. Compatibilidad hacia atrás: el endpoint `/api` sigue funcionando

### Implementación

En `app/api/torznab.py`:
- Añadir ruta dinámica `GET /api/{provider_id}`
- Extraer lógica común a función `_handle_torznab_request(providers, params)`
- El endpoint `/api` actual llama a `_handle_torznab_request` con todos los providers
- El endpoint `/api/{provider_id}` llama con solo ese provider

---

## Orden de Implementación

1. `config.py` — Settings
2. Providers nuevos (6 archivos)
3. `app/api/torznab.py` — Registro + multi-indexer
4. `app/server.py` — Domain resolution
5. `.env.example` — Variables de entorno
6. Tests básicos
