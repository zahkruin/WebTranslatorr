# 07 — Smart Router

## Propósito

Documenta el `SmartRouter`, el componente que determina qué providers invocar para cada petición Torznab. Implementa un algoritmo de inferencia de contenido que evita consultar providers irrelevantes.

Cuándo consultar: para entender cómo se seleccionan providers, depurar búsquedas que no devuelven resultados esperados, o modificar las keywords de inferencia.

---

## Arquitectura

```
Petición Torznab (params: t, q, cat, imdbid, author, etc.)
    │
    ▼
SmartRouter.route(params)
    │
    ├── 1. Detectar search_type (t=caps/tvsearch/movie/book/search)
    │       └── Si book/movie/tv explícito → filtrar por tipo
    │
    ├── 2. Extraer categorías del param cat=
    │       └── Si solo libros o solo video → filtrar por tipo
    │
    ├── 3. Parámetros especiales (imdbid/tvdbid → video, author/title → libros)
    │
    ├── 4. Inferencia desde el query (keyword matching)
    │       └── BOOK_KEYWORDS, MOVIE_KEYWORDS, TV_KEYWORDS
    │
    └── 5. Sin filtros → devolver todos los providers
```

---

## Algoritmo de Routing (Paso a Paso)

**Archivo:** `app/routing/smart_router.py:41-87`

```python
async def route(self, params: dict) -> list[BaseProvider]:
```

### Paso 1: Tipo de búsqueda explícito

```python
search_type = self._detect_search_type(params)
if search_type == SearchType.BOOK:
    return self._get_book_providers()
elif search_type in (SearchType.TV, SearchType.MOVIE):
    return self._get_video_providers()
```

Mapeo del parámetro `t`:
| `t` | SearchType | Providers seleccionados |
|-----|------------|------------------------|
| `book` | BOOK | Solo providers con `supports_book_search=True` |
| `movie` | MOVIE | Solo providers con `supports_movie_search=True` |
| `tvsearch` | TV | Solo providers con `supports_tv_search=True` |
| `search` | GENERIC | Pasa al siguiente paso |
| `caps` | — | No pasa por el router (se maneja antes) |

### Paso 2: Categorías Newznab

```python
categories = self._extract_categories(params)
if categories:
    detected = CategoryMapper.categorize_request(categories)
    if "books" in detected and "movies" not in detected and "tv" not in detected:
        return self._get_book_providers()
    elif ("movies" in detected or "tv" in detected) and "books" not in detected:
        return self._get_video_providers()
    return self.registry.get_by_categories(categories)
```

| Categorías | Resultado |
|------------|-----------|
| `7000,7020` (solo libros) | Book providers |
| `2000,2030` (solo películas) | Video providers |
| `5000,5030` (solo TV) | Video providers |
| `2000,7000` (mixto) | Providers que soporten esas cats |

### Paso 3: Parámetros especiales

```python
if params.get("imdbid") or params.get("tvdbid"):
    return self._get_video_providers()
if params.get("author") or params.get("title"):
    return self._get_book_providers()
```

- `imdbid` o `tvdbid` → solo video providers
- `author` o `title` → solo book providers

### Paso 4: Inferencia inteligente desde el query

```python
if query:
    inferred_type = self._infer_content_type(query)
    if inferred_type == "books":
        return self._get_book_providers()
    elif inferred_type in ("movies", "tv"):
        return self._get_video_providers()
```

**Archivo:** `app/routing/smart_router.py:89-118`

El método `_infer_content_type()` utiliza **keyword scoring**:

```python
def _infer_content_type(self, query: str) -> Optional[str]:
    query_lower = query.lower()
    
    book_score = sum(1 for kw in BOOK_KEYWORDS if kw in query_lower)
    movie_score = sum(1 for kw in MOVIE_KEYWORDS if kw in query_lower)
    tv_score = sum(1 for kw in TV_KEYWORDS if kw in query_lower)
    
    winners = []
    max_score = max(book_score, movie_score, tv_score)
    
    if max_score == 0:
        return None  # No se pudo inferir
    
    if book_score == max_score:
        winners.append("books")
    if movie_score == max_score:
        winners.append("movies")
    if tv_score == max_score:
        winners.append("tv")
    
    # Empate movies+tv → "video"
    if len(winners) == 2 and "movies" in winners and "tv" in winners:
        return "video"
    
    return winners[0] if winners else None
```

**Reglas de inferencia:**
- Cuenta cuántas keywords de cada categoría aparecen en el query
- Gana la categoría con más coincidencias
- En caso de empate movies+tv → devuelve "video" (ambos tipos)
- En caso de empate books+video → la primera en `winners` gana
- Si no hay coincidencias → `None` (sin inferencia)

### Paso 5: Sin filtros

Si ningún paso anterior seleccionó providers, se devuelven **todos** los providers registrados:

```python
return self.registry.get_all()
```

---

## Keywords de Inferencia

**Archivo:** `app/routing/smart_router.py:21-34`

### BOOK_KEYWORDS
```python
BOOK_KEYWORDS = [
    "libro", "novela", "lectura", "pdf", "epub", "mobi", "autor", "author",
    "book", "literatura", "poesía", "poesia", "cuento", "ensayo",
    "editorial", "saga", "trilogía", "trilogia", "biografía", "biografia",
]
```

### MOVIE_KEYWORDS
```python
MOVIE_KEYWORDS = [
    "película", "pelicula", "movie", "film", "cine", "ver", "subtitulada",
    "1080p", "2160p", "4k", "bluray", "blu-ray", "dvdrip", "hdrip",
    "cam", "ts", "director's cut",
]
```

### TV_KEYWORDS
```python
TV_KEYWORDS = [
    "serie", "tv", "capítulo", "capitulo", "episodio", "temporada",
    "chapter", "season", "episode", "tvshow", "sitcom",
]
```

**Ejemplos de inferencia:**
| Query | Book score | Movie score | TV score | Resultado |
|-------|-----------|-------------|----------|-----------|
| `el quijote libro epub` | 3 (libro, epub, libro) | 0 | 0 | `books` |
| `harry potter y la piedra filosofal` | 0 | 0 | 0 | `None` (sin inferencia) |
| `inception 1080p bluray` | 0 | 3 (movie, 1080p, bluray) | 0 | `movies` |
| `breaking bad temporada 1` | 0 | 0 | 3 (tv, temporada, season) | `tv` |
| `game of thrones 1080p` | 0 | 1 (1080p) | 0 | `movies` (aunque es TV!) |

**Limitación:** La keyword `1080p` favorece movies sobre TV. Una búsqueda de serie en HD puede clasificarse incorrectamente como película.

---

## Métodos de Obtención de Providers

### `_get_book_providers()`
```python
def _get_book_providers(self) -> list[BaseProvider]:
    return self.registry.get_by_content_type("books")
```
Devuelve providers con `supports_book_search=True`.

### `_get_video_providers()`
```python
def _get_video_providers(self) -> list[BaseProvider]:
    movies = self.registry.get_by_content_type("movies")
    tv = self.registry.get_by_content_type("tv")
    # Unir y eliminar duplicados
    seen = set()
    result = []
    for p in movies + tv:
        if p.provider_id not in seen:
            seen.add(p.provider_id)
            result.append(p)
    return result
```
Devuelve providers con `supports_movie_search=True` o `supports_tv_search=True`, sin duplicados (un provider puede soportar ambos).

---

## Instancia Global

```python
# app/routing/smart_router.py:152-153
smart_router = SmartRouter(registry)
```

El `registry` es la instancia global de `ProviderRegistry` (definida en `app/providers/registry.py:79`).

---

## Integración con el Endpoint

**Archivo:** `app/api/torznab.py:266-267`

```python
params = dict(request.query_params)
providers = await smart_router.route(params)
```

El router recibe TODOS los query params como dict y decide qué providers usar. Luego `_handle_torznab_request()` ejecuta la búsqueda en los providers seleccionados.

---

## Trampas / Problemas Conocidos

1. **Keywords de calidad (1080p, 4K, etc.) están en MOVIE_KEYWORDS** — Una búsqueda de serie en HD puede inferirse como película. Si el usuario busca `"stranger things 1080p"`, el router lo clasifica como movie y omite los providers de TV.

2. **Sin filtro → se consultan TODOS los providers** — Si Readarr busca `"harry potter"` sin categoría explícita, el router también consulta MejorTorrent y DonTorrent, añadiendo latencia innecesaria.

3. **La inferencia es puramente textual** — No hay análisis semántico ni NLP. Solo cuenta palabras clave.

4. **Las keywords están hardcodeadas** — No son configurables. Para añadir keywords hay que editar `smart_router.py`.

---

## Archivos Relevantes

| Archivo | Rol |
|---------|-----|
| `app/routing/smart_router.py` | Implementación del router |
| `app/providers/registry.py` | ProviderRegistry (fuente de providers) |
| `app/core/categories.py` | CategoryMapper (clasificación por categorías) |
| `app/core/enums.py` | SearchType enum |
| `app/api/torznab.py` | Endpoint que usa el router |
