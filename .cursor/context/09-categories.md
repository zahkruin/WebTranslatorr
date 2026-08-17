# 09 — Mapeo de Categorías Newznab

## Propósito

Referencia completa de los IDs de categoría Newznab estándar y cómo WebTranslatorr los usa para clasificar contenido (libros, películas, series) y enrutar peticiones.

Cuándo consultar: para entender el mapeo de categorías, añadir nuevas categorías, o depurar problemas de enrutamiento por categoría.

---

## Tabla Completa de Categorías

| ID Padre | Nombre | Subcategorías | Usado por |
|:--------:|:-------|:--------------|:---------:|
| **2000** | Movies | 2010 Foreign, 2030 SD, 2040 HD, 2045 UHD, 2050 BluRay, 2080 WEB-DL | Radarr |
| **5000** | TV | 5010 WEB-DL, 5020 Foreign, 5030 SD, 5040 HD, 5045 UHD, 5070 Anime | Sonarr |
| **7000** | Books | 7020 Ebook, 7030 Comics, 7040 Magazines | Readarr |
| **8000** | Books (alt) | 8010 Ebook, 8020 Comics, 8030 Magazines | Readarr |

---

## Detalle de Subcategorías

### Libros (7000-8999)

| ID | Nombre |
|:--:|:-------|
| 7000 | Books |
| 7020 | Ebook |
| 7030 | Comics |
| 7040 | Magazines |
| 8000 | Books (alt) |
| 8010 | Ebook (alt) |
| 8020 | Comics (alt) |
| 8030 | Magazines (alt) |

### Películas (2000-2999)

| ID | Nombre |
|:--:|:-------|
| 2000 | Movies |
| 2010 | Foreign |
| 2030 | SD (DVDRip, etc.) |
| 2040 | HD (BluRay 1080p, etc.) |
| 2045 | UHD (4K, etc.) |
| 2050 | BluRay |
| 2080 | WEB-DL |

### TV (5000-5999)

| ID | Nombre |
|:--:|:-------|
| 5000 | TV |
| 5010 | WEB-DL |
| 5020 | Foreign |
| 5030 | SD (HDTV, etc.) |
| 5040 | HD (HDTV 720p/1080p) |
| 5045 | UHD |
| 5070 | Anime |

---

## Rangos por Tipo de Contenido

| Tipo | Rango | Providers |
|------|-------|-----------|
| Libros | `7000-8999` | Todos los book providers |
| Películas | `2000-2999` | Video providers |
| TV | `5000-5999` | Video providers |
| Video (cualquiera) | `2000-5999` | Video providers |

---

## Notas Importantes

1. **Readarr busca en 7000 Y 8000 simultáneamente** — El proxy debe declarar ambas categorías padre.

2. **Nuestros book providers declaran:** `[7000, 7020, 8000, 8010]`

3. **Nuestros video providers declaran:**
   - MejorTorrent: `[2000, 2030, 2040, 2045, 5000, 5030, 5040, 5045]`
   - DonTorrent: `[2000, 2030, 2040, 2045, 5000, 5030, 5040]`

4. **Categorías usadas en SearchResult:** Los providers de libros típicamente asignan `[7020]` (ebook). Los de video asignan según la calidad (ej: `[2000, 2030]` para SD, `[2000, 2040]` para HD).

---

## CategoryMapper

**Archivo:** `app/core/categories.py`

Clase de utilidad para clasificar categorías:

### Constantes

```python
class CategoryMapper:
    MOVIES = 2000
    TV = 5000
    BOOKS = 7000
    BOOKS_ALT = 8000
    BOOK_EBOOK = 7020
    BOOK_EBOOK_ALT = 8010
    # ... más constantes
```

### Métodos de Clasificación

| Método | Descripción |
|--------|-------------|
| `is_book_category(cat_id)` | ¿Está en rango 7000-8999? |
| `is_video_category(cat_id)` | ¿Está en rango 2000-2999 o 5000-5999? |
| `is_movie_category(cat_id)` | ¿Está en rango 2000-2999? |
| `is_tv_category(cat_id)` | ¿Está en rango 5000-5999? |
| `get_parent_category(cat_id)` | Devuelve la categoría padre (ej: 7020 → 7000) |
| `normalize_categories(cats)` | Elimina duplicados |
| `categorize_request(categories)` | Devuelve `{'books', 'movies', 'tv'}` según las categorías |

### Uso en SmartRouter

```python
# app/routing/smart_router.py:65-70
detected = CategoryMapper.categorize_request(categories)
if "books" in detected and "movies" not in detected and "tv" not in detected:
    return self._get_book_providers()
elif ("movies" in detected or "tv" in detected) and "books" not in detected:
    return self._get_video_providers()
```

### Uso en ProviderRegistry

```python
# app/providers/registry.py:72-75
@staticmethod
def _parent_match(requested_cat: int, supported: list[int]) -> bool:
    parent = CategoryMapper.get_parent_category(requested_cat)
    return parent in supported
```

Permite que una categoría hija (ej: `7020`) matchee con un provider que declara la categoría padre (`7000`).

---

## Mapeo de Calidad a Categoría (MejorTorrent)

**Archivo:** `app/providers/video/mejortorrent.py:35-46`

```python
QUALITY_MAP = {
    "DVDRip": 2030,
    "BluRay-1080p": 2040,
    "MicroHD-1080p": 2040,
    "4K": 2045,
    "HDTV": 5030,
    "HDTV-720p": 5040,
    "HDTV-1080p": 5040,
    "SAT-Rip": 5030,
    "WEB-DL": 2080,
    "WEBRip": 2080,
}
```

---

## Archivos Relevantes

| Archivo | Rol |
|---------|-----|
| `app/core/categories.py` | CategoryMapper |
| `app/routing/smart_router.py` | Usa CategoryMapper para enrutar |
| `app/providers/registry.py` | Usa CategoryMapper para matching |
| `app/torznab/caps.py` | Usa categorías en capabilities XML |
| `app/providers/video/mejortorrent.py` | QUALITY_MAP |
