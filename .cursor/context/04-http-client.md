# 04 — HTTP Client

## Propósito

Documenta el `HttpClient`, el wrapper unificado de HTTP que usan todos los providers para hacer requests. Cubre rate limiting, User-Agent rotation, reintentos con backoff exponencial, el wrapper cloudscraper, y el soporte de proxy.

Cuándo consultar: para depurar timeouts, errores 429, problemas de Cloudflare, o modificar la política de rate limiting.

---

## Arquitectura

```
HttpClient
├── httpx.AsyncClient          # Cliente async para sitios normales
├── cloudscraper.create_scraper # Cliente sync para sitios con Cloudflare
├── Rate limiting por dominio   # Máximo N requests/segundo por dominio
├── User-Agent rotation         # 5 User-Agents, rotación round-robin
├── Retry con backoff           # Hasta 3 reintentos con espera exponencial
└── ScraperResponse wrapper     # Interfaz unificada para ambos clientes
```

---

## Constructor

**Archivo:** `app/scraping/http_client.py:53-79`

```python
def __init__(
    self,
    rate_limit_per_second: float = 2.0,
    max_retries: int = 3,
    timeout: int = 30,
    proxy: Optional[str] = None,
):
```

**Parámetros:**
| Parámetro | Default | Configuración | Descripción |
|-----------|---------|---------------|-------------|
| `rate_limit_per_second` | 2.0 | `WTR_RATE_LIMIT_PER_SECOND` | Requests/segundo por dominio |
| `max_retries` | 3 | `WTR_MAX_RETRIES` | Reintentos máximos |
| `timeout` | 30 | `WTR_REQUEST_TIMEOUT` | Timeout HTTP en segundos |
| `proxy` | None | `WTR_HTTP_PROXY` | Proxy HTTP opcional |

**Inicialización:**
1. Crea `httpx.AsyncClient` con keep-alive (20 conexiones)
2. Crea `cloudscraper.create_scraper` (browser Chrome/Windows emulado)
3. Ambos clients reciben el proxy si está configurado

---

## Métodos Públicos

### `async get(url, **kwargs) → ScraperResponse`

**Archivo:** `app/scraping/http_client.py:81-140`

Realiza un GET HTTP con rate limiting y reintentos.

**kwargs soportados:**
| Kwarg | Default | Descripción |
|-------|---------|-------------|
| `headers` | `{}` | Headers HTTP adicionales (User-Agent se añade automáticamente) |
| `follow_redirects` | `True` | Seguir redirects |
| `use_scraper` | `False` | Usar cloudscraper en lugar de httpx |
| `params` | `None` | Query parameters como dict |

**Headers por defecto inyectados:**
```python
User-Agent: (rotado)
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8
Accept-Language: es-ES,es;q=0.9,en;q=0.8
Accept-Encoding: gzip, deflate
DNT: 1
Connection: keep-alive
```

**Flujo de retry:**
1. Aplicar rate limit (`_apply_rate_limit`)
2. Rotar User-Agent
3. Intentar request (httpx o cloudscraper)
4. Si falla con 429/500/502/503/504 o ConnectionError → esperar `2^attempt` segundos y reintentar
5. Si falla con otro error → propagar excepción
6. Después de `max_retries` intentos → lanzar `Exception("Failed after N retries")`

### `async post(url, **kwargs) → ScraperResponse`

**Archivo:** `app/scraping/http_client.py:142-165`

Similar a `get()` pero usa POST. Solo reintenta en 429. Siempre usa httpx (no cloudscraper).

### `async download_file(url, **kwargs) → bytes`

**Archivo:** `app/scraping/http_client.py:167-169`

Convenience: hace `get()` y devuelve `response.content`.

### `async head(url, **kwargs) → ScraperResponse`

**Archivo:** `app/scraping/http_client.py:171-188`

HTTP HEAD para health checks. Usa httpx, no tiene retry.

---

## User-Agent Rotation

**Archivo:** `app/scraping/http_client.py:45-51, 190-193`

5 User-Agents que rotan en round-robin:

```python
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Firefox/121.0",
]
```

Cada request rota al siguiente UA. No hay lógica de evitar detección por UA repetido.

---

## Rate Limiting

**Archivo:** `app/scraping/http_client.py:195-203`

Rate limiting **por dominio**, no global:

```python
async def _apply_rate_limit(self, url: str) -> None:
    domain = urlparse(url).netloc
    now = asyncio.get_event_loop().time()
    last = self._last_request.get(domain)
    if last is not None:
        elapsed = now - last
        if elapsed < (1.0 / self._rate_limit):
            await asyncio.sleep((1.0 / self._rate_limit) - elapsed)
    self._last_request[domain] = asyncio.get_event_loop().time()
```

Con `rate_limit_per_second=2.0`, se espera al menos 500ms entre requests al mismo dominio.

---

## Cloudscraper Wrapper

**Archivo:** `app/scraping/http_client.py:97-110`

Cuando se usa `use_scraper=True`, el request se ejecuta en un thread aparte vía `loop.run_in_executor()` (cloudscraper es síncrono).

La respuesta de `requests.Response` se convierte a `ScraperResponse`:

```python
@dataclass
class ScraperResponse:
    status_code: int
    text: str
    content: bytes
    headers: dict
    url: str

    @classmethod
    def from_requests_response(cls, resp):
        return cls(
            status_code=resp.status_code,
            text=resp.text,
            content=resp.content,
            headers=dict(resp.headers),
            url=str(resp.url),
        )
```

Los providers que **requieren** cloudscraper:
- `annas_archive.py` — Anna's Archive tiene protección Cloudflare
- `epublibre.py` — EpubLibre puede requerir bypass
- `lectulandia.py` — Lectulandia puede requerir bypass
- `espaebook.py`, `holaebook.py` — WordPress con posible protección
- `zlibrary.py` — Z-Library cambia frecuentemente de protección

---

## Ciclo de Vida

El HttpClient es **compartido** entre todos los providers. Se crea una única instancia en el startup de FastAPI:

```python
# app/server.py:lifespan()
http_client = HttpClient(...)
app.state.http_client = http_client

# app/api/torznab.py:_init_providers()
http_client = _get_http_client()  # Singleton lazy
```

En shutdown, se cierra el cliente httpx:
```python
await http_client.close()  # Cierra httpx.AsyncClient
```

---

## Configuración Relacionada

| Variable | Campo | Default | Impacto |
|----------|-------|---------|---------|
| `WTR_RATE_LIMIT_PER_SECOND` | `RATE_LIMIT_PER_SECOND` | 2.0 | Velocidad máxima de scraping |
| `WTR_MAX_RETRIES` | `MAX_RETRIES` | 3 | Veces que se reintenta un request fallido |
| `WTR_REQUEST_TIMEOUT` | `REQUEST_TIMEOUT` | 30 | Timeout HTTP |
| `WTR_HTTP_PROXY` | `HTTP_PROXY` | "" | Proxy HTTP |

---

## Trampas / Problemas Conocidos

1. **El diccionario `_last_request` crece sin límite** — Acumula entradas por cada dominio visitado. No hay limpieza periódica. Issue #11.

2. **Cloudscraper es síncrono** — Se ejecuta en `run_in_executor`, lo que consume un thread del pool. Si muchos providers usan cloudscraper simultáneamente, puede haber contención de threads.

3. **No hay rate limiting cross-provider** — Si 10 providers hacen requests al mismo dominio, cada uno aplica su propio rate limit, pero no hay coordinación global.

4. **`head()` no tiene retry** — Si falla, la excepción se propaga directamente. Esto afecta al `DomainResolver` que usa `head()` para validar dominios.

5. **`_scraper` se usa para GET con `use_scraper=True`, pero `post()` y `head()` siempre usan httpx** — No se puede hacer POST con cloudscraper.

---

## Archivos Relevantes

| Archivo | Rol |
|---------|-----|
| `app/scraping/http_client.py` | Implementación principal |
| `app/scraping/parser.py` | Helpers de parsing (no usados actualmente) |
| `config.py` | Settings relacionados con HTTP |
| `app/providers/books/annas_archive.py` | Ejemplo de provider que requiere cloudscraper |
| `app/providers/books/epublibre.py` | Ejemplo de provider que requiere cloudscraper |
