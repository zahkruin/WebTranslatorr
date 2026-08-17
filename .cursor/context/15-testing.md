# 15 — Testing

## Propósito

Guía de testing para WebTranslatorr. Cubre el framework (pytest + pytest-asyncio), los fixtures disponibles, patrones de test para providers, y cómo ejecutar tests.

Cuándo consultar: para escribir nuevos tests, entender la estructura de tests existentes, o depurar fallos en CI.

---

## Framework y Dependencias

- **Framework:** pytest
- **Async:** pytest-asyncio (todos los tests de providers son async)
- **HTTP Mock:** No se usa un mock library estándar; se recomienda mockear `HttpClient`

---

## Estructura de Tests

```
tests/
├── conftest.py                    # Fixtures compartidos
├── test_api_health.py             # Health endpoint
├── test_api_domains.py            # Domain endpoints
├── test_api_torznab.py            # Torznab endpoints
├── test_server.py                 # FastAPI app factory
├── test_base_provider.py          # BaseProvider tests
├── test_cache.py                  # SearchCache tests
├── test_categories.py             # CategoryMapper tests
├── test_domain_resolver.py        # DomainResolver tests
├── test_http_client.py            # HttpClient tests
├── test_parser.py                 # Parser helpers tests
├── test_scraper_response.py       # ScraperResponse tests
├── test_smart_router.py           # SmartRouter tests
├── test_torznab_integration.py    # Torznab integration tests
├── test_torznab_mapper.py         # TorznabMapper tests
├── test_zip_extractor.py          # ZipExtractor tests
├── test_provider_ebookelo.py      # Ebookelo provider tests
├── test_provider_epublibre.py     # EpubLibre provider tests
├── test_provider_lectulandia.py   # Lectulandia provider tests
├── test_provider_espaebook.py     # Espaebook provider tests
├── test_provider_holaebook.py     # HolaEbook provider tests
├── test_provider_annas_archive.py # Anna's Archive provider tests
├── test_provider_mejortorrent.py  # MejorTorrent provider tests
└── test_provider_dontorrent.py    # DonTorrent provider tests
```

---

## Fixtures (conftest.py)

**Archivo:** `tests/conftest.py`

```python
@pytest.fixture
def empty_registry():
    """Returns an empty provider registry."""
    registry = ProviderRegistry()
    registry.clear()
    return registry

@pytest.fixture
def router(empty_registry):
    """Returns a smart router with empty registry."""
    return SmartRouter(empty_registry)
```

---

## Cómo Ejecutar Tests

```bash
# Todos los tests
pytest

# Tests de un módulo específico
pytest tests/test_categories.py

# Tests de un provider específico
pytest tests/test_provider_epublibre.py

# Con verbose
pytest -v

# Con coverage
pytest --cov=app --cov-report=term-missing

# Solo tests que fallaron en la última ejecución
pytest --lf
```

---

## Patrón de Test para Providers

### 1. Test de parsing de resultados (sin HTTP)

El patrón más común: mockear `http_client.get()` para devolver HTML fijo.

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.core.models import SearchResult

class MockResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

@pytest.mark.asyncio
async def test_search_parses_results():
    # Arrange
    provider = MiProvider(http_client=AsyncMock())
    mock_html = """<html>...</html>"""
    provider.http_client.get.return_value = MockResponse(mock_html)
    
    # Act
    results = await provider.search("test query", categories=[7020])
    
    # Assert
    assert len(results) > 0
    assert isinstance(results[0], SearchResult)
    assert results[0].title == "Expected Title"
```

### 2. Test de get_download_url

```python
@pytest.mark.asyncio
async def test_get_download_url():
    provider = MiProvider(http_client=AsyncMock())
    detail_html = """<html><a href="/download/123">DESCARGAR EPUB</a></html>"""
    provider.http_client.get.return_value = MockResponse(detail_html)
    
    url = await provider.get_download_url("test-id")
    
    assert url is not None
    assert "/download/" in url
```

### 3. Test de capabilities

```python
def test_get_capabilities():
    provider = MiProvider(http_client=AsyncMock())
    caps = provider.get_capabilities()
    
    assert caps.provider_id == "miprovider"
    assert caps.supports_book_search == True
    assert 7020 in caps.supported_categories
```

### 4. Test de manejo de errores

```python
@pytest.mark.asyncio
async def test_search_handles_http_error():
    provider = MiProvider(http_client=AsyncMock())
    provider.http_client.get.side_effect = Exception("Connection error")
    
    results = await provider.search("test", categories=[7020])
    
    assert results == []  # Debe devolver lista vacía, no propagar
```

---

## Patrón AAA (Arrange-Act-Assert)

Todos los tests siguen el patrón:
1. **Arrange** — Preparar datos, mocks, instancias
2. **Act** — Ejecutar el método bajo test
3. **Assert** — Verificar resultados

---

## Tests de Integración Torznab

**Archivo:** `tests/test_torznab_integration.py`

Testean el flujo completo: endpoint → router → provider → mapper → XML.

```python
from fastapi.testclient import TestClient
from app.server import app

client = TestClient(app)

def test_caps_endpoint():
    response = client.get("/api?t=caps&apikey=test-key")
    assert response.status_code == 200
    assert "caps" in response.text
```

---

## Coverage Actual

Según el plan de mejora (`plans/coverage_improvement_plan.md`), la cobertura actual es ~72%. Los módulos con menor cobertura son:

| Módulo | Cobertura estimada | Razón |
|--------|-------------------|-------|
| Providers (general) | Baja | Pocos tests de parsing |
| DomainResolver | Media | Tests básicos solamente |
| SmartRouter | Media-Alta | Tests de routing básico |
| HttpClient | Media | Tests de rate limiting |
| TorznabMapper | Alta | Bien cubierto |

---

## Trampas / Problemas Conocidos

1. **Los providers requieren HttpClient mockeado** — No usar el HttpClient real en tests (haría requests HTTP reales).

2. **Async tests requieren `@pytest.mark.asyncio`** — Sin este decorador, `await` falla.

3. **El registry es un singleton global** — Los tests deben usar `empty_registry` fixture para aislarse.

4. **No hay tests para los providers nuevos** — Epubflix1, Libgen, Booobook, LectuEpubLibre5, MundoEpubLibre1, ZLibrary no tienen archivos de test.

5. **`TestClient` de FastAPI** — Para tests de integración, `TestClient` no soporta el lifespan real (startup/shutdown). Usar `@pytest.fixture` con `asynccontextmanager` si se necesita.

---

## Archivos Relevantes

| Archivo | Rol |
|---------|-----|
| `tests/conftest.py` | Fixtures compartidos |
| `tests/test_provider_ebookelo.py` | Ejemplo de tests de provider |
| `tests/test_categories.py` | Ejemplo de tests de módulo core |
| `tests/test_torznab_integration.py` | Ejemplo de tests de integración |
| `plans/coverage_improvement_plan.md` | Plan detallado de mejora de cobertura |
