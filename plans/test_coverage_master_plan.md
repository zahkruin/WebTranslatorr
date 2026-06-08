# Plan Maestro de Cobertura de Tests → 90%+

> **Objetivo**: Alcanzar ≥90% de cobertura de código en toda la aplicación WebTranslatorr,
> partiendo del ~72% actual (~189 tests en 24 archivos), con un plan sistemático,
> medible y reproducible.

**Fecha**: 2026-06-08
**Estado actual**: ~72% de cobertura, 189 tests, 24 archivos de test
**Objetivo**: ≥90% de cobertura, ~270 tests, 32 archivos de test
**Esfuerzo estimado**: 6 días (40-50 horas)

---

## 1. Selección del Framework y Justificación

### Framework principal: **pytest** (ya en uso)

**Justificación de mantener pytest:**

| Criterio | pytest | unittest | nose2 |
|----------|--------|----------|-------|
| **Sintaxis** | Funciones simples `def test_*`, asserts nativos | Clases + `self.assert*`, verboso | Similar a unittest |
| **Async** | `@pytest.mark.asyncio` nativo con pytest-asyncio | Requiere `asyncio.run()` manual | No soportado |
| **Fixtures** | Sistema de fixtures potente, inyección de dependencias | `setUp/tearDown` por clase | Limitado |
| **Parametrize** | `@pytest.mark.parametrize` — reduce código repetido | No nativo | No nativo |
| **Plugins** | pytest-cov, pytest-asyncio, pytest-xdist, pytest-mock | Limitado | Limitado |
| **Adopción** | Estándar de facto en Python moderno (FastAPI, Django) | Legacy | Obsoleto |
| **Compatibilidad** | Ya integrado en el proyecto, ~189 tests existentes | — | — |

**Conclusión**: pytest es la elección correcta y ya está adoptado. No hay motivo para cambiar.

### Plugins requeridos

```ini
# requirements-dev.txt (nuevo archivo)
pytest>=8.0
pytest-asyncio>=0.24
pytest-cov>=5.0
pytest-mock>=3.14
pytest-xdist>=3.6        # Ejecución paralela
pytest-timeout>=2.3      # Timeout por test
pytest-randomly>=3.15    # Orden aleatorio para detectar dependencias ocultas
coverage>=7.6            # Medición de cobertura
```

### Herramientas de medición

| Herramienta | Propósito |
|-------------|-----------|
| **pytest-cov** | Cobertura por archivo, informe terminal |
| **coverage.py** | Informes HTML, XML para CI, branch coverage |
| **coverage-badge** | Badge en README (opcional) |

---

## 2. Configuración Inicial del Entorno de Pruebas

### 2.1 Archivo `pyproject.toml` (sección pytest)

```toml
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
asyncio_mode = "auto"
addopts = [
    "--strict-markers",
    "--tb=short",
    "--cov=app",
    "--cov-report=term-missing",
    "--cov-report=html",
    "--cov-report=xml",
    "--cov-fail-under=90",
    "-n auto",
    "--timeout=30",
]
markers = [
    "slow: tests that are slow (deselect with '-m \"not slow\"')",
    "integration: tests that require real HTTP or external services",
    "unit: fast unit tests with no external dependencies",
]
filterwarnings = [
    "error",
    "ignore::DeprecationWarning:cloudscraper.*",
]
```

### 2.2 Archivo `.coveragerc`

```ini
[run]
source = app
branch = true
omit =
    */__init__.py
    */tests/*
    app/scraping/parser.py   # Código huérfano (ningún provider lo importa)

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod

[html]
directory = htmlcov
```

### 2.3 Archivo `requirements-dev.txt`

```text
-r requirements.txt
pytest>=8.0
pytest-asyncio>=0.24
pytest-cov>=5.0
pytest-mock>=3.14
pytest-xdist>=3.6
pytest-timeout>=2.3
pytest-randomly>=3.15
coverage>=7.6
```

### 2.4 Comandos de ejecución

```bash
# Instalar dependencias de desarrollo
pip install -r requirements-dev.txt

# Ejecutar todos los tests con cobertura
pytest

# Solo tests unitarios (sin integración)
pytest -m "unit"

# Solo tests de un módulo específico
pytest tests/test_provider_ebookelo.py -v

# Con informe HTML de cobertura
pytest --cov=app --cov-report=html
open htmlcov/index.html

# Fallar si la cobertura es < 90%
pytest --cov=app --cov-fail-under=90

# Ejecutar en paralelo (4 workers)
pytest -n 4

# Detectar tests que dependen del orden
pytest --randomly-seed=1234
```

---

## 3. Estructura y Organización de Tests

### 3.1 Principio rector: 1 archivo de test por módulo fuente

```
app/                              tests/
├── api/                          ├── test_api_torznab.py          ✅ Existe
│   ├── torznab.py        ←────── ├── test_api_health.py           ✅ Existe
│   ├── health.py         ←────── ├── test_api_domains.py          ✅ Existe
│   └── domains.py        ←──────
│                                  
├── core/                         ├── test_categories.py           ✅ Existe
│   ├── categories.py     ←────── ├── test_models.py               🆕 NUEVO
│   ├── models.py         ←────── ├── test_enums.py                🆕 NUEVO
│   ├── enums.py          ←────── └── test_exceptions.py           🆕 NUEVO
│   └── exceptions.py     ←──────
│                                  
├── providers/                    
│   ├── base.py           ←────── test_base_provider.py            ✅ Existe
│   ├── registry.py       ←────── test_torznab_integration.py      ✅ Existe (parcial)
│   ├── books/                    
│   │   ├── ebookelo.py   ←────── test_provider_ebookelo.py        ✅ Existe
│   │   ├── epublibre.py  ←────── test_provider_epublibre.py       ✅ Existe
│   │   ├── lectulandia.py←────── test_provider_lectulandia.py     ✅ Existe
│   │   ├── espaebook.py  ←────── test_provider_espaebook.py       ✅ Existe
│   │   ├── holaebook.py  ←────── test_provider_holaebook.py       ✅ Existe
│   │   ├── annas_archive.py←──── test_provider_annas_archive.py   ✅ Existe
│   │   ├── libgen.py     ←────── test_provider_libgen.py          🆕 NUEVO
│   │   ├── epubflix1.py  ←────── test_provider_epubflix1.py       🆕 NUEVO
│   │   ├── booobook.py   ←────── test_provider_booobook.py        🆕 NUEVO
│   │   ├── lectuepublibre5.py←── test_provider_lectuepublibre5.py 🆕 NUEVO
│   │   ├── mundoepublibre1.py←── test_provider_mundoepublibre1.py 🆕 NUEVO
│   │   └── zlibrary.py   ←────── test_provider_zlibrary.py        🆕 NUEVO
│   └── video/
│       ├── mejortorrent.py←───── test_provider_mejortorrent.py    ✅ Existe
│       └── dontorrent.py ←────── test_provider_dontorrent.py      ✅ Existe
│                                  
├── routing/                      ├── test_smart_router.py          ✅ Existe
│   └── smart_router.py   ←──────
│                                  
├── scraping/                     ├── test_http_client.py           ✅ Existe
│   ├── http_client.py    ←────── ├── test_parser.py                ✅ Existe
│   ├── parser.py         ←────── ├── test_scraper_response.py     ✅ Existe
│   └── wp_api_client.py  ←────── └── test_wp_api_client.py        🆕 NUEVO
│                                  
├── services/                     ├── test_cache.py                 ✅ Existe
│   ├── cache.py         ←────── ├── test_domain_resolver.py       ✅ Existe
│   ├── domain_resolver.py←──────
│   └── domain_strategies.py←──── (parte de test_domain_resolver)
│                                  
├── torznab/                      ├── test_torznab_mapper.py        ✅ Existe
│   ├── mapper.py         ←────── ├── test_torznab_integration.py   ✅ Existe
│   ├── caps.py           ←────── └── test_torznab_errors.py        ❓ (en integration)
│   └── errors.py         ←──────
│                                  
├── utils/                        └── test_zip_extractor.py         ✅ Existe
│   └── zip_extractor.py  ←──────
│                                  
└── server.py             ←────── test_server.py                   ✅ Existe
```

### 3.2 Archivos nuevos necesarios

| # | Archivo de test | Módulo fuente | Prioridad | Tests estimados |
|---|----------------|---------------|-----------|-----------------|
| 1 | `test_provider_libgen.py` | `books/libgen.py` | **Crítica** | 14 |
| 2 | `test_provider_epubflix1.py` | `books/epubflix1.py` | **Crítica** | 12 |
| 3 | `test_provider_lectuepublibre5.py` | `books/lectuepublibre5.py` | **Crítica** | 12 |
| 4 | `test_provider_booobook.py` | `books/booobook.py` | **Crítica** | 12 |
| 5 | `test_provider_zlibrary.py` | `books/zlibrary.py` | **Crítica** | 14 |
| 6 | `test_provider_mundoepublibre1.py` | `books/mundoepublibre1.py` | Alta | 12 |
| 7 | `test_wp_api_client.py` | `scraping/wp_api_client.py` | Alta | 10 |
| 8 | `test_models.py` | `core/models.py` | Media | 6 |
| 9 | `test_enums.py` | `core/enums.py` | Media | 4 |
| 10 | `test_exceptions.py` | `core/exceptions.py` | Media | 6 |

### 3.3 Archivos existentes a ampliar

| # | Archivo | Qué falta | Tests a añadir |
|---|---------|-----------|----------------|
| 1 | `test_domain_resolver.py` | `get_current()` error, `resolve_all()`, `health_check()`, `domain_check_loop()` | 5 |
| 2 | `test_api_torznab.py` | Reducir duplicación de `mock_settings`, añadir `search_with_cache()` cache miss path | 3 |
| 3 | `test_provider_mejortorrent.py` | `season`/`episode` filter, `offset`, `_build_search_url(page=2)`, `_parse_results` sin matches, `/documental/`, `_resolve_imdb_to_spanish_title` error, `_fetch_detail_page` sin torrents | 8 |
| 4 | `test_provider_ebookelo.py` | Enrichment con offset > 0, `_parse_book_detail` sin autor/formatos, descarga con redirect, `profitablecpmgate` skip | 4 |
| 5 | `test_torznab_integration.py` | `registry.get()` con ID inexistente, `unregister()`, `_parent_match`, `registry.get_by_content_type()` no cubierto | 4 |

---

## 4. Tipos de Tests y Estrategia de Cobertura

### 4.1 Matriz de tipos de test por módulo

Para cada función/método, se deben cubrir:

| Tipo | Descripción | Ejemplo |
|------|-------------|---------|
| **Caso positivo** | Entrada válida, resultado esperado | `search("quijote", [7020])` → `list[SearchResult]` |
| **Caso negativo** | Entrada inválida, manejo de error | `search("", [7020])` → `[]` |
| **Caso límite** | Valores en los bordes del dominio | `limit=0`, `limit=100`, `offset` > total resultados |
| **Excepción** | Fallo de dependencia externa | `http_client.get()` lanza `Exception` → devolver `[]` |
| **Mock verification** | Verificar que se llamó a la dependencia correcta | `mock_client.get.assert_called_once_with(url)` |

### 4.2 Plantilla de test para providers

```python
import pytest
from unittest.mock import AsyncMock
from app.core.models import SearchResult
from app.providers.books.nuevo import NuevoProvider
from app.scraping.http_client import ScraperResponse

# ── Fixtures ────────────────────────────────────────────

@pytest.fixture
def mock_client():
    """HTTP client mockeado que devuelve respuestas predefinidas."""
    client = AsyncMock()
    client.get = AsyncMock()
    return client

@pytest.fixture
def provider(mock_client):
    """Instancia del provider con HTTP client mockeado."""
    return NuevoProvider(http_client=mock_client)

# ── HTML de ejemplo (capturado del sitio real) ──────────

SEARCH_HTML = """<html>...</html>"""    # HTML real de búsqueda
DETAIL_HTML = """<html>...</html>"""    # HTML real de detalle

# ── search() tests ─────────────────────────────────────

class TestNuevoProviderSearch:
    
    @pytest.mark.asyncio
    async def test_search_returns_results(self, provider, mock_client):
        """Caso positivo: búsqueda exitosa."""
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "https://example.com"
        )
        results = await provider.search("quijote", categories=[7020])
        
        assert len(results) > 0
        assert all(isinstance(r, SearchResult) for r in results)
        assert results[0].title != ""
        assert results[0].guid.startswith("NUEVO_ID-")

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_empty(self, provider):
        """Caso límite: query vacía."""
        results = await provider.search("", categories=[7020])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_normalizes_query(self, provider, mock_client):
        """Caso límite: query con caracteres especiales."""
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "https://example.com"
        )
        results = await provider.search("¡Quijote! ¿Cervantes?", categories=[7020])
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_http_error_returns_empty(self, provider, mock_client):
        """Caso negativo: error HTTP."""
        mock_client.get.side_effect = Exception("Connection refused")
        results = await provider.search("quijote", categories=[7020])
        assert results == []

    @pytest.mark.asyncio
    async def test_search_applies_offset(self, provider, mock_client):
        """Caso límite: paginación con offset."""
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "https://example.com"
        )
        results = await provider.search("quijote", categories=[7020], offset=5)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_respects_limit(self, provider, mock_client):
        """Caso límite: respeta el parámetro limit."""
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "https://example.com"
        )
        results = await provider.search("quijote", categories=[7020], limit=5)
        assert len(results) <= 5

    @pytest.mark.asyncio
    async def test_search_deduplicates_results(self, provider, mock_client):
        """Caso límite: no devuelve resultados duplicados."""
        mock_client.get.return_value = ScraperResponse(
            200, SEARCH_HTML, b"", {}, "https://example.com"
        )
        results = await provider.search("quijote", categories=[7020])
        guids = [r.guid for r in results]
        assert len(guids) == len(set(guids))

# ── get_download_url() tests ────────────────────────────

class TestNuevoProviderDownload:
    
    @pytest.mark.asyncio
    async def test_get_download_url_success(self, provider, mock_client):
        """Caso positivo: descarga exitosa."""
        mock_client.get.return_value = ScraperResponse(
            200, DETAIL_HTML, b"", {}, "https://example.com"
        )
        url = await provider.get_download_url("test-id", fmt="epub")
        
        assert url is not None
        assert url.startswith("http")

    @pytest.mark.asyncio
    async def test_get_download_url_not_found(self, provider, mock_client):
        """Caso negativo: enlace de descarga no encontrado."""
        mock_client.get.return_value = ScraperResponse(
            200, "<html><body>No download</body></html>", b"", {}, "url"
        )
        url = await provider.get_download_url("test-id", fmt="epub")
        assert url is None

    @pytest.mark.asyncio
    async def test_get_download_url_http_error(self, provider, mock_client):
        """Caso negativo: error HTTP en página de detalle."""
        mock_client.get.side_effect = Exception("Timeout")
        url = await provider.get_download_url("test-id", fmt="epub")
        assert url is None

# ── get_capabilities() test ─────────────────────────────

class TestNuevoProviderCapabilities:
    
    def test_get_capabilities(self, provider):
        """Caso positivo: verificar capabilities declaradas."""
        caps = provider.get_capabilities()
        assert caps.provider_id == "NUEVO_ID"
        assert caps.supports_book_search is True
        assert 7020 in caps.supported_categories
```

### 4.3 Plantilla para tests de WordPressApiClient

```python
import json
import pytest
from unittest.mock import AsyncMock
from app.scraping.wp_api_client import WordPressApiClient
from app.core.models import SearchResult

WP_POST_RESPONSE = [
    {
        "id": 123,
        "date": "2026-04-19T08:42:37",
        "slug": "el-quijote-cervantes",
        "link": "https://site.com/el-quijote/",
        "title": {"rendered": "El Quijote | Miguel de Cervantes"},
        "excerpt": {"rendered": "<p>Una gran obra...</p>"},
        "content": {"rendered": "<p>Contenido completo...</p>"},
        "type": "post",
        "yoast_head_json": {
            "og_title": "El Quijote",
            "og_description": "La obra maestra de Cervantes",
            "og_image": [{"url": "https://site.com/cover.jpg"}],
        }
    }
]

@pytest.fixture
def mock_http():
    client = AsyncMock()
    client.get = AsyncMock()
    return client

@pytest.fixture
def wp_client(mock_http):
    return WordPressApiClient(
        http_client=mock_http,
        base_url="https://site.com",
        provider_id="test-wp",
    )

class TestWordPressApiClient:

    @pytest.mark.asyncio
    async def test_search_returns_results(self, wp_client, mock_http):
        """Caso positivo: API devuelve posts."""
        mock_http.get.return_value.text = json.dumps(WP_POST_RESPONSE)
        
        results = await wp_client.search("quijote", limit=10)
        
        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].title == "El Quijote"
        assert results[0].author == "Miguel de Cervantes"

    @pytest.mark.asyncio
    async def test_search_empty_query(self, wp_client):
        """Caso límite: query vacía."""
        results = await wp_client.search("")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_api_error(self, wp_client, mock_http):
        """Caso negativo: error de la API."""
        mock_http.get.side_effect = Exception("API error")
        
        results = await wp_client.search("quijote")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_handles_malformed_response(self, wp_client, mock_http):
        """Caso límite: respuesta JSON malformada."""
        mock_http.get.return_value.text = "not json"
        
        results = await wp_client.search("quijote")
        assert results == []

    def test_parse_title_author_pipe_separator(self):
        title, author = WordPressApiClient._parse_title_author("Book | Author")
        assert title == "Book"
        assert author == "Author"

    def test_parse_title_author_emdash_separator(self):
        title, author = WordPressApiClient._parse_title_author("Book — Author")
        assert title == "Book"
        assert author == "Author"

    def test_parse_title_author_no_separator(self):
        title, author = WordPressApiClient._parse_title_author("Just a Book")
        assert title == "Just a Book"
        assert author is None
```

---

## 5. Estrategia para Alcanzar y Mantener el 90%

### 5.1 Métricas objetivo

| Métrica | Actual | Objetivo | Herramienta |
|---------|--------|----------|-------------|
| **Line coverage** | ~72% | ≥90% | `pytest-cov --cov=app` |
| **Branch coverage** | ~65% | ≥85% | `.coveragerc` con `branch = true` |
| **Tests totales** | ~189 | ≥270 | `pytest --collect-only` |
| **Módulos con 0% de cobertura** | 7 | 0 | `coverage report --show-missing` |
| **Tiempo de ejecución** | ~15s | ≤30s | `pytest --durations=10` |

### 5.2 Priorización de partes críticas

**Nivel 1 — Crítico (día 1-2): Código sin ningún test**

| Módulo | Riesgo si no se prueba | Esfuerzo |
|--------|----------------------|----------|
| `books/libgen.py` (203 líneas) | Provider activo, sin tests. Si se rompe el parsing de tabla, Readarr pierde LibGen | 3h |
| `books/zlibrary.py` (248 líneas) | Provider más complejo, multi-patrón, sin tests | 3h |
| `books/epubflix1.py` (173 líneas) | Recién migrado a API híbrida, sin tests | 2.5h |
| `books/lectuepublibre5.py` (179 líneas) | Recién migrado a API híbrida, sin tests | 2.5h |
| `books/booobook.py` (171 líneas) | CMS desconocido, estrategia defensiva, sin tests | 3h |
| `books/mundoepublibre1.py` (142 líneas) | Casi idéntico a lectuepublibre5, sin tests | 2h |

**Nivel 2 — Alto (día 3): Cobertura parcial < 85%**

| Módulo | % actual | Qué falta |
|--------|---------|-----------|
| `scraping/wp_api_client.py` | 0% | Tests de cliente API WordPress |
| `api/torznab.py` | ~60% | Paths de cache miss, `_init_providers` completo |
| `services/domain_resolver.py` | ~72% | `resolve_all()`, `health_check()`, `domain_check_loop()`, persistencia |
| `providers/video/mejortorrent.py` | ~85% | Filtros season/episode, offset, `_resolve_imdb` error |
| `providers/books/ebookelo.py` | ~77% | Enrichment con offset, `_parse_book_detail` edge cases |

**Nivel 3 — Medio (día 4): Refactor y hardening**

| Tarea | Descripción |
|-------|-------------|
| Reducir duplicación en `test_api_torznab.py` | Extraer `mock_settings` a fixture parametrizada |
| Añadir `@pytest.mark.parametrize` | Donde haya múltiples casos similares |
| Tests de modelos/excepciones | `test_models.py`, `test_exceptions.py` |
| Edge cases en providers existentes | `_parse_book_detail` sin autor, sin formatos, error HTTP |

**Nivel 4 — Bajo (día 5): Integración y CI/CD**

| Tarea | Descripción |
|-------|-------------|
| Configurar CI para fallar si cobertura < 90% | GitHub Actions con `pytest --cov-fail-under=90` |
| Tests de integración con HTML real | Capturar HTML de cada sitio y testear parseo |
| `pytest-randomly` en CI | Detectar tests con dependencias de orden |
| Coverage badge en README | `coverage-badge` |

### 5.3 Script de verificación de cobertura

```bash
#!/bin/bash
# scripts/check_coverage.sh
pytest --cov=app --cov-report=term --cov-fail-under=90 "$@"
```

### 5.4 Mantenimiento continuo de la cobertura

1. **Pre-commit hook**: Ejecutar `pytest --cov-fail-under=90` antes de cada commit
2. **CI gate**: El pipeline de CI falla si la cobertura baja del 90%
3. **Code review**: Todo PR que añada código debe incluir tests
4. **Reporte semanal**: `coverage report --show-missing` en el canal de desarrollo
5. **Rotura de tests**: Si un test falla, se arregla antes que cualquier feature nueva

---

## 6. Integración en CI/CD

### 6.1 GitHub Actions workflow (ampliación del existente)

```yaml
# .github/workflows/test.yml (NUEVO archivo)
name: Tests & Coverage

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run tests with coverage
        run: |
          pytest --cov=app --cov-report=xml --cov-report=term \
                 --cov-fail-under=90 \
                 -n auto \
                 --randomly-seed=42 \
                 -m "not integration"

      - name: Upload coverage to Codecov (opcional)
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          fail_ci_if_error: false
          target: 90%

      - name: Generate coverage badge
        run: |
          coverage report --format=markdown > coverage.md
```

### 6.2 Pre-commit config

```yaml
# .pre-commit-config.yaml (NUEVO archivo)
repos:
  - repo: local
    hooks:
      - id: pytest-cov
        name: Run tests with coverage
        entry: pytest --cov=app --cov-fail-under=90 -x -m "not integration"
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-commit]
```

---

## 7. Cronograma de Implementación

### Día 1: Providers sin tests — Lote 1 (8 horas)

| Hora | Tarea | Entregable |
|------|-------|-----------|
| 09:00-10:00 | Capturar HTML real de libgen.ee y z-library.sk (o usar snapshots) | HTML fixture files |
| 10:00-13:00 | Crear `test_provider_libgen.py` (14 tests) | Archivo de test completo |
| 14:00-17:00 | Crear `test_provider_zlibrary.py` (14 tests) | Archivo de test completo |
| 17:00-18:00 | Ejecutar y verificar cobertura de los 2 providers | Coverage ≥ 85% para ambos |

### Día 2: Providers sin tests — Lote 2 (8 horas)

| Hora | Tarea | Entregable |
|------|-------|-----------|
| 09:00-11:30 | Crear `test_provider_epubflix1.py` (12 tests, API + scraping) | Archivo de test completo |
| 11:30-14:00 | Crear `test_provider_lectuepublibre5.py` (12 tests) | Archivo de test completo |
| 15:00-17:30 | Crear `test_provider_booobook.py` (12 tests) | Archivo de test completo |
| 17:30-18:00 | Crear `test_provider_mundoepublibre1.py` (12 tests, basado en lectuepublibre5) | Archivo de test completo |

### Día 3: WordPressApiClient + cobertura parcial (8 horas)

| Hora | Tarea | Entregable |
|------|-------|-----------|
| 09:00-12:00 | Crear `test_wp_api_client.py` (10 tests) | Archivo de test completo |
| 12:00-14:00 | Ampliar `test_api_torznab.py`: cache miss, `_init_providers` completo | +3 tests |
| 15:00-17:00 | Ampliar `test_domain_resolver.py`: `resolve_all()`, `health_check()`, `domain_check_loop()` | +5 tests |
| 17:00-18:00 | Ejecutar cobertura global, registrar % alcanzado | Métrica actualizada |

### Día 4: Edge cases y refactor (8 horas)

| Hora | Tarea | Entregable |
|------|-------|-----------|
| 09:00-10:30 | Ampliar `test_provider_mejortorrent.py`: season/episode, offset, imdb error, page URL | +8 tests |
| 10:30-12:00 | Ampliar `test_provider_ebookelo.py`: enrichment offset, detail sin autor/formatos, redirect | +4 tests |
| 12:00-13:00 | Crear `test_models.py`: SearchResult defaults, ProviderCapabilities | +6 tests |
| 14:00-15:00 | Crear `test_enums.py`, `test_exceptions.py` | +10 tests |
| 15:00-17:00 | Refactorizar `test_api_torznab.py`: fixture `mock_settings` parametrizada | Código más limpio |
| 17:00-18:00 | Añadir `@pytest.mark.parametrize` donde aplique | Reducción de líneas |

### Día 5: CI/CD y automatización (6 horas)

| Hora | Tarea | Entregable |
|------|-------|-----------|
| 09:00-10:00 | Crear `.github/workflows/test.yml` | CI pipeline |
| 10:00-10:30 | Crear `.pre-commit-config.yaml` | Pre-commit hook |
| 10:30-11:30 | Crear `requirements-dev.txt`, `.coveragerc`, `pyproject.toml` [pytest] | Configuración |
| 11:30-13:00 | Crear `scripts/check_coverage.sh` | Script de verificación |
| 14:00-16:00 | Ejecutar suite completa, corregir fallos, verificar 90% | Suite verde |

### Día 6: Integración y documentación (4 horas)

| Hora | Tarea | Entregable |
|------|-------|-----------|
| 09:00-11:00 | Crear tests de integración con HTML real (marcados `@pytest.mark.integration`) | Tests de humo |
| 11:00-12:00 | Documentar cómo escribir tests para nuevos providers | Actualizar `context/15-testing.md` |
| 12:00-13:00 | Revisión final, ajuste de métricas, commit | PR listo |

---

## 8. Resumen de Entregables

| Entregable | Tipo | Cantidad |
|-----------|------|----------|
| **Archivos de test nuevos** | `.py` | 10 |
| **Archivos de test ampliados** | `.py` | 5 |
| **Tests nuevos totales** | funciones | ~81 |
| **Líneas de test nuevas** | líneas | ~1900 |
| **Cobertura objetivo** | % | 90%+ |
| **Archivos de configuración** | `.yml`, `.toml`, `.ini`, `.txt` | 5 |
| **Scripts** | `.sh` | 1 |

---

## 9. Riesgos y Mitigaciones

| Riesgo | Probabilidad | Mitigación |
|--------|:-----------:|------------|
| HTML de sitios web cambia y los fixtures quedan obsoletos | Alta | Usar snapshots del HTML real, actualizar trimestralmente. Marcar como `@pytest.mark.integration` para no ejecutar en cada commit |
| Tests de provider sin API son frágiles (dependen de estructura HTML) | Media | Usar HTML capturado, no requests reales. Si un test falla, verificar si es cambio real del sitio o rotura de test |
| `pytest-xdist` causa problemas con fixtures que comparten estado global | Media | Usar `@pytest.fixture(scope="function")`, limpiar estado en `autouse` fixtures |
| No alcanzar 90% en algunos módulos (código muerto, paths inalcanzables) | Baja | Usar `# pragma: no cover` para código intencionalmente no testeable (abstract methods, TYPE_CHECKING) |
| Los tests de integración requieren acceso a Internet | Alta | Separar con `@pytest.mark.integration`, excluir de CI estándar con `-m "not integration"` |

---

## 10. Cómo Ejecutar el Plan

```bash
# Paso 1: Preparar entorno
pip install -r requirements-dev.txt

# Paso 2: Verificar cobertura actual (baseline)
pytest --cov=app --cov-report=term

# Paso 3: Ejecutar día 1 — crear tests de providers sin cobertura
# (crear archivos test_provider_libgen.py, test_provider_zlibrary.py, etc.)

# Paso 4: Verificar progreso después de cada lote
pytest tests/test_provider_libgen.py --cov=app/providers/books/libgen.py --cov-report=term

# Paso 5: Al final de cada día, ejecutar suite completa
pytest --cov=app --cov-report=term --cov-fail-under=90

# Paso 6: Configurar CI
# (crear .github/workflows/test.yml, .pre-commit-config.yaml)

# Paso 7: Commit y PR
git add tests/ .github/ .coveragerc pyproject.toml requirements-dev.txt
git commit -m "test: alcanzar ≥90% de cobertura con 81 tests nuevos"
```
