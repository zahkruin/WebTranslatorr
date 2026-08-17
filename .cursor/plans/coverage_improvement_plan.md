# Plan de Mejora de Cobertura de Tests → ≥90% por Módulo

**Objetivo:** Subir la cobertura de cada módulo de `app/` al 90% o más.

**Estado actual:** 72% global (1.723 statements, 477 sin cubrir)  
**Objetivo:** ~90%+ global (~172 statements sin cubrir)

---

## Resumen de módulos objetivo

| # | Módulo | Actual | Target | Stmts | Miss | Esfuerzo |
|---|--------|--------|--------|-------|------|----------|
| 1 | `app/api/torznab.py` | 0% | 90% | 116 | 116 | Alta |
| 2 | `app/api/domains.py` | 0% | 90% | 32 | 32 | Media |
| 3 | `app/api/health.py` | 0% | 90% | 5 | 5 | Baja |
| 4 | `app/server.py` | 0% | 90% | 54 | 54 | Alta |
| 5 | `app/scraping/http_client.py` | 25% | 90% | 111 | 83 | Alta |
| 6 | `app/scraping/parser.py` | 0% | 90% | 17 | 17 | Baja |
| 7 | `app/services/domain_resolver.py` | 72% | 90% | 143 | 40 | Media |
| 8 | `app/providers/books/ebookelo.py` | 77% | 90% | 134 | 31 | Media |
| 9 | `app/providers/base.py` | 80% | 90% | 45 | 9 | Baja |
| 10 | `app/providers/registry.py` | 83% | 90% | 48 | 8 | Baja |
| 11 | `app/providers/video/mejortorrent.py` | 85% | 90% | 163 | 24 | Media |
| 12 | `app/providers/books/espaebook.py` | 89% | 90% | 66 | 7 | Baja |

---

## FASE 1: Módulos pequeños y rápidos (bajo esfuerzo)

### 1.1 `app/api/health.py` — 5 stmts, 0% → 100%

**Archivo:** [`app/api/health.py`](app/api/health.py)

**Líneas sin cubrir:** 5-13 (todo el archivo)

**Qué probar:**
- `GET /health` devuelve `{"status": "healthy", "service": "WebTranslatorr"}`

**Test:** Añadir a un nuevo archivo `tests/test_api_health.py`:
```python
from fastapi.testclient import TestClient
from app.server import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "WebTranslatorr"
```

**Líneas cubiertas:** 10-13 (endpoint completo)  
**Cobertura esperada:** 100%

---

### 1.2 `app/scraping/parser.py` — 17 stmts, 0% → 100%

**Archivo:** [`app/scraping/parser.py`](app/scraping/parser.py)

**Líneas sin cubrir:** 5-33 (todo el archivo)

**Qué probar:**
- `parse_html()` — crea BeautifulSoup desde HTML string
- `extract_text()` — None → default, elemento → texto limpio
- `extract_href()` — None → default, elemento → href
- `safe_int()` — número válido, string inválido, None

**Test:** Añadir a `tests/test_parser.py`:
```python
from app.scraping.parser import parse_html, extract_text, extract_href, safe_int

def test_parse_html():
    soup = parse_html("<html><body><p>hello</p></body></html>")
    assert soup is not None
    assert soup.find("p").text == "hello"

def test_extract_text_with_element():
    soup = parse_html("<a>click me</a>")
    assert extract_text(soup.find("a")) == "click me"

def test_extract_text_with_none():
    assert extract_text(None, "fallback") == "fallback"
    assert extract_text(None) == ""

def test_extract_href_with_element():
    soup = parse_html('<a href="https://example.com">link</a>')
    assert extract_href(soup.find("a")) == "https://example.com"

def test_extract_href_with_none():
    assert extract_href(None, "default") == "default"

def test_safe_int_valid():
    assert safe_int("42") == 42

def test_safe_int_invalid():
    assert safe_int("abc") == 0

def test_safe_int_none():
    assert safe_int(None) == 0
```

**Cobertura esperada:** 100%

---

### 1.3 `app/providers/base.py` — 9 missing → ~90%

**Archivo:** [`app/providers/base.py`](app/providers/base.py)

**Líneas sin cubrir:** 75-79 (`is_healthy`), 96-97 (`_combine_query` con query+parts), 102 (`_build_search_url`), 106 (`_parse_results`)

**Qué probar (añadir a test existente o crear `tests/test_base_provider.py`):**
1. `is_healthy()` — crea un concrete provider mock, mock `http_client.get` → status_code=200 → True
2. `is_healthy()` — error de conexión → False (línea 79)
3. `_combine_query()` — query + author + title combinados (líneas 96-97: cuando query existe y no está en parts)
4. `_build_search_url()` — verificar que no lance error (línea 102, es un pass)
5. `_parse_results()` — verificar que no lance error (línea 106, es un pass)

**Test:**
```python
class ConcreteProvider(BaseProvider):
    async def search(self, query, categories=None, **kwargs):
        return []
    async def get_download_url(self, internal_id):
        return ""

@pytest.mark.asyncio
async def test_is_healthy_returns_true():
    prov = ConcreteProvider(mock_client, base_url="https://example.com")
    mock_client.get.return_value = ScraperResponse(200, "ok", b"ok", {}, "https://example.com")
    assert await prov.is_healthy() is True
    mock_client.get.assert_called_once_with("https://example.com")

@pytest.mark.asyncio
async def test_is_healthy_returns_false_on_error():
    prov = ConcreteProvider(mock_client, base_url="https://example.com")
    mock_client.get.side_effect = Exception("Connection error")
    assert await prov.is_healthy() is False

def test_combine_query_with_all_parts():
    prov = ConcreteProvider(mock_client)
    # query + author + title where query is not in combined parts
    result = prov._combine_query("extra", "tolkien", "lord")
    assert "tolkien" in result
    assert "lord" in result
    assert "extra" in result

def test_build_search_url_does_nothing():
    prov = ConcreteProvider(mock_client)
    assert prov._build_search_url("test") is None

def test_parse_results_does_nothing():
    prov = ConcreteProvider(mock_client)
    assert prov._parse_results("<html></html>") is None
```

**Cobertura esperada:** 91% (4 líneas sin cubrir de 45 = ~91%)

---

### 1.4 `app/providers/registry.py` — 8 missing → 90%+

**Archivo:** [`app/providers/registry.py`](app/providers/registry.py)

**Líneas sin cubrir:** 30 (get con error), 40-41 (`_parent_match` True), 63-65 (unregister con provider existente), 74-75 (`_parent_match` internals)

**Qué probar (añadir a `tests/test_torznab_integration.py::TestProviderRegistryIntegration`):**
1. `get()` con ID inexistente → `ProviderNotFoundError` (línea 30)
2. `unregister()` con provider existente → se elimina (líneas 63-65)
3. `get_by_categories()` con categoría que necesita `_parent_match` (líneas 40-41, 74-75)
4. `_parent_match` directamente

**Test a añadir:**
```python
def test_get_raises_on_unknown(self):
    registry.clear()
    with pytest.raises(ProviderNotFoundError):
        registry.get("nonexistent")

def test_unregister_existing(self):
    registry.clear()
    mock_prov = MagicMock()
    mock_prov.provider_id = "test_prov"
    registry.register(mock_prov)
    assert registry.get("test_prov") == mock_prov
    registry.unregister("test_prov")
    with pytest.raises(ProviderNotFoundError):
        registry.get("test_prov")

def test_parent_category_matching(self):
    registry.clear()
    # Provider only supports parent category 2000, but we request subcategory 2040
    mock_prov = MagicMock()
    mock_prov.provider_id = "parent_test"
    mock_prov.get_capabilities.return_value = ProviderCapabilities(
        provider_id="parent_test",
        supported_categories=[2000],  # Only parent, not 2040
    )
    registry.register(mock_prov)
    # 2040 should match via _parent_match → 2000
    matching = registry.get_by_categories([2040])
    assert mock_prov in matching
```

**Cobertura esperada:** 94% (3 líneas sin cubrir de 48)

---

### 1.5 `app/providers/books/espaebook.py` — 89% → 90%+

**Archivo:** [`app/providers/books/espaebook.py`](app/providers/books/espaebook.py)

**Líneas sin cubrir:** 20-22 (constructor `__init__` kwargs), 66, 73, 88, 114

**Qué probar (añadir a test existente):**
- Líneas 20-22: Inicializar provider con kwargs como `domain_resolver` (probarlo en el fixture)
- Línea 66: Ruta HTTP error en search (ya existe test `test_search_http_error_returns_empty`, verificar que cubre línea 66)
- Línea 73: Empty query path (añadir `test_search_empty_query_returns_empty` si no existe)
- Línea 88: `get_download_url` cuando falla y retorna fallback URL
- Línea 114: Error path en get_download_url

**Acción:** Verificar que los tests existentes ya cubren estas líneas. Si no, añadir casos.
- Líneas 20-22: Asegurar que el fixture `provider` en [`tests/test_provider_espaebook.py`](tests/test_provider_espaebook.py) usa `domain_resolver`
- Línea 73: No hay test de `search()` con query vacía → añadirlo

**Cobertura esperada:** 92%+

---

## FASE 2: Módulos de complejidad media

### 2.1 `app/providers/video/mejortorrent.py` — 24 missing → 90%+

**Archivo:** [`app/providers/video/mejortorrent.py`](app/providers/video/mejortorrent.py)

**Líneas sin cubrir:**
- 51-53: Constructor `__init__` kwargs (domain_resolver)
- 119: Filtro por season en search
- 121: Filtro por episode en search
- 125: Aplicar offset
- 132: `_build_search_url` con page > 1
- 147, 156-160, 163, 167: Paths del parsing (selector sin match, /documental/, sin match)
- 220-221: `_fetch_detail_page` sin torrent links
- 231: Series con extract_season_episode usando tag del índice
- 256: Movie detail, set IMDB ID
- 295: `_extract_imdb_id` sin match
- 308, 320-323: `_resolve_imdb_to_spanish_title` paths de error

**Qué probar:**
1. Constructor con `domain_resolver` (líneas 51-53)
2. Search con `season` y `episode` (líneas 119, 121)
3. Search con `offset` > 0 (línea 125)
4. `_build_search_url` con `page=2` (línea 132)
5. `_parse_results` con HTML que no tiene enlaces (línea 147)
6. `_parse_results` con `/documental/` URL (líneas 156-160)
7. `_fetch_detail_page` sin torrent links en HTML (líneas 220-221)
8. `_resolve_imdb_to_spanish_title` con error de conexión a TMDB (líneas 308, 320-323)

**Tests a añadir:**
```python
@pytest.mark.asyncio
async def test_search_with_season_filter(self, provider, mock_client):
    mock_client.get.side_effect = [
        ScraperResponse(200, SEARCH_HTML, SEARCH_HTML.encode(), {}, "url"),
        ScraperResponse(200, DETAIL_SERIES_HTML, DETAIL_SERIES_HTML.encode(), {}, "url"),
    ]
    results = await provider.search(query="breaking bad", categories=[], season=1)
    assert len(results) > 0

@pytest.mark.asyncio
async def test_search_with_offset(self, provider, mock_client):
    mock_client.get.side_effect = [
        ScraperResponse(200, SEARCH_HTML, SEARCH_HTML.encode(), {}, "url"),
        ScraperResponse(200, DETAIL_MOVIE_HTML, DETAIL_MOVIE_HTML.encode(), {}, "url"),
        ScraperResponse(200, DETAIL_SERIES_HTML, DETAIL_SERIES_HTML.encode(), {}, "url"),
    ]
    results = await provider.search(query="inception", categories=[], offset=1)
    assert isinstance(results, list)

@pytest.mark.asyncio
async def test_search_imdb_resolve_error(self, provider, mock_client):
    # mock_client.get raises connection error for TMDB call
    mock_client.get.side_effect = Exception("TMDB error")
    results = await provider.search(query="", imdb_id="tt1375666", categories=[])
    assert results == []

def test_build_search_url_page_2(self, provider):
    url = provider._build_search_url("test", page=2)
    assert "page/2" in url

def test_parse_results_no_matches(self, provider):
    results = provider._parse_results("<html><body><p>no links</p></body></html>")
    assert results == []

def test_parse_results_documental(self, provider):
    html = '<html><body><a href="/documental/999/title">Doc</a></body></html>'
    results = provider._parse_results(html)
    assert len(results) > 0

@pytest.mark.asyncio
async def test_fetch_detail_no_torrent(self, provider, mock_client):
    from app.core.models import SearchResult
    result = SearchResult(title="test", guid="test-1", link="https://example.com/detail")
    mock_client.get.return_value = ScraperResponse(
        200, "<html><body>No torrents</body></html>",
        b"", {}, "https://example.com/detail"
    )
    enriched = await provider._fetch_detail_page(result)
    assert len(enriched) == 1
```

**Cobertura esperada:** 92%+

---

### 2.2 `app/providers/books/ebookelo.py` — 31 missing → 90%+

**Archivo:** [`app/providers/books/ebookelo.py`](app/providers/books/ebookelo.py)

**Líneas sin cubrir:**
- 41-43: Constructor kwargs (domain_resolver)
- 98, 101-103, 105-107: Detail enrichment (author, formats, genre) — son paths try/except de `_parse_book_detail`
- 112: Aplicar offset
- 132, 140: Paths de `_parse_results` (sin match, sin ID)
- 178, 183-186: `_parse_book_detail` paths (sin autor, sin enlaces)
- 192, 197-200: `_parse_book_detail` error handling (sin género, excepción)
- 220-221: `get_download_url` paths específicos para EPUB
- 233-235: download URL con redirección
- 240: download URL con error de parsing
- 246: timeout en download
- 250: error en download

**Qué probar:**
1. Constructor con `domain_resolver` (líneas 41-43)
2. Search con `offset` > 0 (línea 112)
3. `_parse_book_detail` con respuesta sin autor (línea 178)
4. `_parse_book_detail` con respuesta sin enlaces de descarga (línea 183-186)
5. `get_download_url` para formato EPUB (líneas 220-221) — escenario específico
6. `get_download_url` con timeout simulado (línea 246)

**Cobertura esperada:** 92%+

---

### 2.3 `app/services/domain_resolver.py` — 40 missing → 90%+

**Archivo:** [`app/services/domain_resolver.py`](app/services/domain_resolver.py)

**Líneas sin cubrir:**
- 110-112: `get_current` con provider no registrado (ValueError)
- 119-121: `get_status` con provider_id específico no registrado
- 135: Path de resolución exitosa en `resolve()`
- 198-206: `resolve_all` método completo
- 210-225: `health_check` método completo
- 245-246: `_notify_change` cuando no hay callback
- 260-261: `_persist` error handling
- 281-282: `_load_persisted` error handling
- 296-307: `domain_check_loop` función autónoma

**Qué probar:**
1. `get_current()` con provider no registrado → ValueError (líneas 110-112)
2. `get_status(provider_id)` con provider no registrado (línea 119-121) — ¡importante! Este test existe pero puede no cubrir todas las ramas
3. `resolve_all()` con múltiples providers (líneas 198-206)
4. `health_check()` endpoint completo (líneas 210-225)
5. `_persist()` con error de escritura (líneas 260-261)
6. `_load_persisted()` con archivo corrupto (líneas 281-282)
7. `domain_check_loop()` función standalone (líneas 296-307)

**Tests específicos ya existentes en `test_domain_resolver.py`:** Revisar qué cubren las líneas faltantes.

**Cobertura esperada:** 92%+

---

## FASE 3: Módulos de infraestructura (alta complejidad)

### 3.1 `app/scraping/http_client.py` — 83 missing → 90%+

**Archivo:** [`app/scraping/http_client.py`](app/scraping/http_client.py)

**Líneas sin cubrir:**
- 60-79: Constructor — creación de cliente httpx y cloudscraper
- 82-140: `get()` — retry logic, cloudscraper path, HTTPStatusError, ConnectError, requests.exceptions
- 143-165: `post()` — implementación completa
- 168-169: `download_file()` — wrapper
- 172-188: `head()` — implementación completa
- 191-193: `_rotate_ua()` — rotación de user-agent
- 196-203: `_apply_rate_limit()` — rate limiting por dominio
- 206: `close()` — limpiar cliente

**Qué probar:**
1. **Constructor** (líneas 60-79): Crear HttpClient con proxy, verificar que cloudscraper recibe proxy config
2. **`get()` con httpx** (líneas 111-125): Mock httpx.AsyncClient.get → response exitosa
3. **`get()` con cloudscraper** (líneas 97-110): `use_scraper=True` → verifica que llama a cloudscraper
4. **`get()` retry en 429** (líneas 126-128): Mock responde 429, luego 200 → verificar 2 intentos
5. **`get()` retry en ConnectError** (líneas 131-132): Mock lanza ConnectError, luego éxito
6. **`get()` falla tras N retries** (línea 140): Mock lanza error siempre → verificar excepción final
7. **`post()`** (líneas 142-165): Mock httpx.AsyncClient.post → response exitosa
8. **`post()` 429 retry** (líneas 159-161): Mock 429, luego éxito
9. **`download_file()`** (líneas 167-169): Verificar que llama a get y retorna .content
10. **`head()`** (líneas 171-188): Mock httpx.AsyncClient.head → response exitosa
11. **`_rotate_ua()`** (líneas 190-193): Llamar 2 veces → diferente UA
12. **`_apply_rate_limit()`** (líneas 195-203): Llamar get rápida 2 veces al mismo dominio → se aplica sleep
13. **`close()`** (línea 206): Llamar close → cliente se cierra

**Estrategia de testing:**
Se necesita mocking profundo, ya que HttpClient usa httpx.AsyncClient y cloudscraper internamente.

```python
# Usar patch para mockear httpx.AsyncClient y cloudscraper
@patch("app.scraping.http_client.httpx.AsyncClient")
@patch("app.scraping.http_client.cloudscraper")
def test_http_client_get_success(mock_scraper, mock_httpx):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "OK"
    mock_response.content = b"OK"
    mock_response.url = "https://example.com"
    mock_httpx.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
    
    client = HttpClient()
    response = await client.get("https://example.com")
    assert response.status_code == 200
```

**Cobertura esperada:** 90%+

---

### 3.2 `app/api/torznab.py` — 116 missing → 90%+

**Archivo:** [`app/api/torznab.py`](app/api/torznab.py)

**Líneas sin cubrir:** 18-259 (archivo completo)

**Estrategia:**
Usar `TestClient` de FastAPI con mocking de `smart_router`, `registry` y `HttpClient`.

**Tests a crear en `tests/test_api_torznab.py`:**

1. **`GET /api?t=caps`** — verificar XML de capabilities
2. **`GET /api?t=search&q=test&apikey=...`** — búsqueda exitosa → XML RSS
3. **`GET /api?t=search&q=test`** (sin apikey) → error 100 XML
4. **`GET /api?apikey=wrong`** → error 100 XML
5. **`GET /api?t=search&q=&apikey=...`** (sin query) → resultados vacíos
6. **`GET /api/download?provider=test&id=123`** — descarga exitosa
7. **`GET /api/download?provider=nonexistent&id=123`** — error
8. **`_get_http_client()`** — lazy initialization
9. **`_init_providers()`** — inicialización con settings mockeados
10. **`_parse_cats()`** — string vacío, string con números, string con inválidos
11. **`_validate_apikey()`** — correcta vs incorrecta

```python
from fastapi.testclient import TestClient
from app.server import app

# Mockear settings para tests
@patch("app.api.torznab.settings")
def test_caps_endpoint(mock_settings):
    mock_settings.API_KEY = "testkey"
    # Configurar mock_settings con valores por defecto...
    client = TestClient(app)
    response = client.get("/api?t=caps&apikey=testkey")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/xml"
```

**Cobertura esperada:** 92%+

---

### 3.3 `app/api/domains.py` — 32 missing → 90%+

**Archivo:** [`app/api/domains.py`](app/api/domains.py)

**Líneas sin cubrir:** 5-80 (archivo completo)

**Estrategia:** Usar `TestClient` con `app.state.domain_resolver` mockeado.

**Tests:**
1. `GET /api/domains` — lista de dominios (mock `resolver.get_status()`)
2. `POST /api/domains/refresh` — refresh todos (mock `resolver.resolve_all()`)
3. `POST /api/domains/refresh/{provider_id}` — refresh uno específico
4. `POST /api/domains/refresh/{provider_id}` con provider inexistente → 404
5. `GET /api/domains/health/{provider_id}` — health check
6. `GET /api/domains/health/{provider_id}` con provider inexistente → 404

**Cobertura esperada:** 94%+

---

### 3.4 `app/server.py` — 54 missing → 90%+

**Archivo:** [`app/server.py`](app/server.py)

**Líneas sin cubrir:** 5-156 (archivo completo)

**Estrategia:** El `lifespan` y `create_app()` se prueban indirectamente a través de los tests de API con `TestClient`. Sin embargo, el lifespan en sí (registro de providers, resolución inicial, domain_check_loop) requiere mocking más profundo.

**Qué probar:**
1. `create_app()` — crear app y verificar routers incluidos
2. `lifespan` startup — mocking de settings para verificar registro de providers
3. `lifespan` shutdown — verificar que se cancela el task y se cierra http_client

Usar `TestClient` con la app real (el startup se ejecuta al crear el client).

**Cobertura esperada:** 90%+

---

## Resumen de nuevos archivos de test

| Archivo | Tests estimados | Módulos cubiertos |
|---------|----------------|-------------------|
| `tests/test_api_health.py` | 1 | health.py |
| `tests/test_parser.py` | 7 | parser.py |
| `tests/test_base_provider.py` | 5 | base.py |
| `tests/test_http_client.py` | 13 | http_client.py |
| `tests/test_api_torznab.py` | 11 | torznab.py |
| `tests/test_api_domains.py` | 6 | domains.py |
| `tests/test_server.py` | 3 | server.py |

## Tests a ampliar en archivos existentes

| Archivo | Tests a añadir |
|---------|---------------|
| `tests/test_torznab_integration.py` | +3 tests (registry: get unknown, unregister, parent_match) |
| `tests/test_provider_mejortorrent.py` | +8 tests (season filter, offset, imdb resolve error, page URL, no matches, documental, no torrent, imdb resolve) |
| `tests/test_provider_ebookelo.py` | +4 tests (offset, detail no author, detail no links, download epub path) |
| `tests/test_provider_espaebook.py` | +1 test (empty query) |
| `tests/test_domain_resolver.py` | +3 tests (get_current unknown, resolve_all, health_check, persist error, load corrupt, domain_check_loop) |

## Estimación de esfuerzo

| Fase | Archivos | Tests nuevos | Líneas de test | Cobertura ganada |
|------|----------|-------------|----------------|------------------|
| FASE 1 | 5 módulos pequeños | ~20 tests | ~300 líneas | ~8% (72% → 80%) |
| FASE 2 | 3 módulos medios | ~15 tests | ~350 líneas | ~6% (80% → 86%) |
| FASE 3 | 4 módulos complejos | ~33 tests | ~700 líneas | ~6% (86% → 92%) |
| **Total** | **12 módulos** | **~68 tests** | **~1350 líneas** | **72% → ~92%** |
