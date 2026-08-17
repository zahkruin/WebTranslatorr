# Evaluación de Integración Playwright para Headless Browser

> **Fecha**: 2026-07-02
> **Plan relacionado**: [PLAN-20260701-003](PLAN-20260701-003-plan.md) — Paso 10
> **Prototipo**: `scripts/test_playwright_prototype.py`
> **Agente responsable**: `scraping`
> **Estado**: ⚠️ PENDIENTE DE EJECUCIÓN — las métricas reales requieren correr el prototipo

---

## 1. Resumen Ejecutivo

Esta evaluación analiza si integrar Playwright como headless browser en WebTranslatorr está justificado para manejar sitios SPA (Single Page Application) y bypass anti-bot avanzado que el stack actual (httpx + cloudscraper + BeautifulSoup4) no puede manejar.

**Conclusión anticipada (pendiente de validación empírica):** Para los 2-3 providers de manga en español que actualmente se beneficiarían, el coste en recursos (~500 MB Docker, ~1 GB RAM, mantenimiento de dependencia externa) probablemente no justifica la integración directa en el proyecto. Como camino intermedio, se recomienda evaluar **FlareSolverr** como servicio externo para bypass Cloudflare (desacoplado del proyecto), y aplazar el soporte de SPAs puras hasta que el catálogo de providers lo demande con más volumen.

---

## 2. Sitios de Prueba

El prototipo `scripts/test_playwright_prototype.py` evalúa tres sitios representativos de las dos clases de problema que Playwright resolvería:

| # | Sitio | URL | Tipo | Razón de inclusión |
|---|-------|-----|------|---------------------|
| 1 | **InManga** | `inmanga.com` | SPA pura (Angular/Vue) | HTML inicial vacío; requiere JS rendering para cualquier contenido. Sin headless browser, es imposible extraer datos. |
| 2 | **PDF Drive** | `pdfdrive.com` | Anti-bot avanzado | Fingerprinting agresivo, bloqueo por User-Agent + JS challenge. Sitio de libros en inglés con catálogo masivo. |
| 3 | **SkyMangas** | `skymangas.com` | SPA con SSR parcial | Caso intermedio: parte del contenido se sirve en SSR, pero el renderizado completo requiere JS. Representa la mayoría de sitios de manga modernos. |

**Por qué estos tres:** InManga representa el peor caso (SPA pura), PDF Drive representa el bypass anti-bot que cloudscraper no puede resolver, y SkyMangas representa el caso intermedio más común en el catálogo de 586 sitios de manga identificados.

---

## 3. Métricas del Prototipo

### 3.1 Métricas que el Prototipo Recolecta

El script `test_playwright_prototype.py` está diseñado para recolectar:

| Métrica | Fuente | Instrumentación |
|---------|--------|-----------------|
| `browser_launch_time_s` | `time.perf_counter()` | Tiempo desde `async_playwright()` hasta `browser.new_context()` |
| `first_navigation_time_s` | `page.goto(..., wait_until="networkidle")` | Tiempo hasta `networkidle` (métrica más realista para SPAs) |
| `second_navigation_time_s` | `page.goto(..., wait_until="domcontentloaded")` | Request subsecuente en browser ya abierto |
| `total_time_s` | `time.perf_counter()` | Tiempo total de la prueba (incluye launch + navegación + extracción) |
| `memory_delta_mb` | `psutil.Process.memory_info().rss` | Diferencia de RSS antes/después de la prueba |
| `html_length` | `len(page.content())` | Tamaño del HTML renderizado (comparado contra HTTP simple) |
| `http_status` | `response.status` | Código HTTP de la respuesta |
| Indicadores de contenido | `_content_indicators()` | `has_links`, `has_images`, `has_search_results`, `likely_spa_empty` |

### 3.2 Umbrales de Aceptación Esperados

Basados en benchmarks de la industria y experiencia con Playwright:

| Métrica | Umbral aceptable | Ideal | Inaceptable |
|---------|-----------------|-------|-------------|
| Tiempo primera carga (`networkidle`) | < 10 s | < 5 s | > 15 s |
| Tiempo requests subsiguientes (browser caliente) | < 5 s | < 3 s | > 8 s |
| Tiempo browser launch (cold start) | < 3 s | < 1.5 s | > 5 s |
| RAM delta por request | < 500 MB | < 300 MB | > 800 MB |
| RAM browser pool (2-3 browsers idle) | < 1 GB | < 700 MB | > 1.5 GB |
| Éxito extracción de contenido | > 80% | 100% | < 50% |
| Éxito bypass anti-bot (Cloudflare, fingerprinting) | Debe funcionar | — | Si falla, Playwright no aporta valor |

### 3.3 Estimaciones Conservadoras (Pre-Ejecución)

Basadas en documentación de Playwright y experiencia en entornos similares:

| Concepto | Estimación | Nota |
|----------|-----------|------|
| Chromium cold launch | 1.5–3.0 s | Depende de CPU/disco. En Docker suele ser más lento. |
| Navegación a `networkidle` | 4–10 s | Varía mucho según el sitio. SPAs pesadas pueden superar 10 s. |
| RAM por instancia Chromium | 200–400 MB | Un solo contexto/página. Crece con el número de pestañas. |
| Pool de 3 browsers idle | 600 MB – 1.2 GB | Memoria compartida parcial entre procesos Chromium. |
| Imagen Docker adicional | +400–600 MB | Chromium + dependencias de sistema (libnss3, libgbm, etc.). |
| Throughput con pool de 3 | ~6–12 requests/min | Estimado con 5 s por request + overhead de cola. |

**⚠️ Importante:** Estas son estimaciones, no mediciones reales. Los valores reales solo se obtienen ejecutando el prototipo en el entorno objetivo (local y Docker).

---

## 4. Evaluación de Impacto

### 4.1 Rendimiento

| Aspecto | Impacto | Detalle |
|---------|---------|---------|
| Latencia first request | +2–4 s | Tiempo de lanzar Chromium + primera navegación. Significativo comparado con HTTP simple (~0.5–2 s). |
| Latencia request subsiguiente | +1–3 s | Con browser pool caliente, el overhead se reduce a la navegación + renderizado JS. |
| Throughput global | Reducción 60–80% | HTTP simple puede hacer ~120 req/min (a 2 req/s rate limit); Playwright con pool de 3 baja a ~10–20 req/min. |
| Bloqueo del event loop | Moderado | Playwright Python es async-native; no bloquea el event loop. Pero la memoria de Chromium compite con el resto de la app. |

### 4.2 Recursos

| Recurso | Sin Playwright | Con Playwright (pool de 3) | Diferencia |
|---------|---------------|---------------------------|------------|
| RAM base del proceso Python | ~80–150 MB | ~80–150 MB | Sin cambio |
| RAM Chromium pool | — | 600–1200 MB | **+600–1200 MB** |
| RAM total estimada | ~150 MB | ~750–1350 MB | **5x–9x más** |
| CPU idle | < 1% | < 1% | Sin cambio significativo en idle |
| CPU durante request | ~5–15% (I/O bound) | ~30–60% (renderizado JS) | Pico más alto, pero breve |
| Disco (imagen Docker) | ~250 MB | ~650–850 MB | **+400–600 MB** |

### 4.3 Docker

```
# Dependencias adicionales necesarias en Dockerfile:
RUN apt-get update && apt-get install -y \
    libnss3 libnspr4 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libgbm1 libasound2 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libpango-1.0-0 libcairo2 libatspi2.0-0 \
    && playwright install chromium \
    && playwright install-deps chromium
```

- **Tamaño adicional de imagen**: ~400–600 MB (Chromium + 30+ paquetes de sistema)
- **Tiempo de build adicional**: ~2–4 minutos (descarga de Chromium ~130 MB + paquetes)
- **Compatibilidad**: Requiere imagen base `debian:bookworm-slim` o superior (no `alpine`, que carece de glibc)

### 4.4 Mantenimiento

| Aspecto | Frecuencia | Esfuerzo |
|---------|-----------|----------|
| Actualización de Playwright | Cada 4–6 semanas | `pip install --upgrade playwright && playwright install chromium` |
| Rotura por cambio en sitio target | Impredecible | Requiere actualizar selectores; mismo esfuerzo que un provider HTTP normal |
| Incompatibilidad con nueva versión de Python | Cada ~12 meses (Python minor) | Playwright tiene buen soporte; riesgo bajo |
| Vulnerabilidades en Chromium | Continuo | Playwright actualiza Chromium automáticamente con cada release |
| Depuración de fallos | Variable | Depurar headless browser es más complejo que HTTP; requiere capturar screenshots/HAR |

---

## 5. Alternativas Evaluadas

### Opción A: Integrar Playwright como dependencia opcional

**Descripción:** Añadir `playwright` a `requirements-optional.txt`, crear `JsHttpClient` en `app/scraping/js_http_client.py` con feature flag `WTR_JS_RENDERING_ENABLED=false` por defecto. Pool de browsers calientes gestionado por el HttpClient.

**Ventajas:**
- Soporte completo para SPAs puras (InManga y similares)
- Bypass anti-bot robusto (fingerprinting, JS challenges)
- No depende de servicios externos
- Control total sobre timeouts, selectores, y estrategia de espera

**Desventajas:**
- +400–600 MB en imagen Docker
- +600–1200 MB RAM para pool de browsers
- Mantenimiento continuo de dependencia externa
- Throughput muy reducido (6–12 req/min vs 120 req/min)
- Complejidad añadida al sistema de rate-limiting actual
- Solo beneficia a 2-3 providers de un catálogo de 781 sitios

**Estimación de esfuerzo de implementación:** 3–5 días (JsHttpClient + pool + tests + documentación + Docker)

---

### Opción B: NO integrar Playwright (status quo)

**Descripción:** Mantener el stack actual (httpx + cloudscraper + BS4). Los sitios SPA puros y anti-bot avanzado se marcan como `blocked` en el catálogo de providers.

**Ventajas:**
- Sin cambios en infraestructura
- Sin aumento de recursos (RAM, Docker, mantenimiento)
- Foco en los 605 sitios de complejidad baja/media del catálogo

**Desventajas:**
- ~30 sitios de complejidad alta quedan fuera de alcance
- InManga y PDF Drive no son viables
- Si cloudscraper falla contra Cloudflare moderno, incluso sitios de complejidad media pueden volverse inaccesibles

**Estimación de esfuerzo:** 0 días (no se hace nada)

---

### Opción C: FlareSolverr para Cloudflare, sin SPAs (camino intermedio)

**Descripción:** Desplegar [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) como servicio Docker externo para bypass Cloudflare. Para SPAs puras, se mantiene el bloqueo (no se integra Playwright). El `HttpClient` se configura para proxyficar requests a través de FlareSolverr cuando `use_flaresolverr=True`.

**Ventajas:**
- Resuelve el problema Cloudflare sin añadir dependencias al proyecto
- FlareSolverr es un proyecto mantenido por la comunidad
- Desacoplado: si FlareSolverr falla, WebTranslatorr sigue funcionando
- RAM de FlareSolverr está en su propio contenedor, no compite con la app
- Puede manejar challenges Cloudflare Turnstile y JS

**Desventajas:**
- Componente externo: requiere Docker Compose con dos servicios
- Latencia adicional: +2–8 s por request (FlareSolverr debe resolver el challenge)
- No resuelve SPAs puras (InManga)
- FlareSolverr usa headless browser internamente (mismo coste de recursos, pero aislado)
- Dependencia de un proyecto third-party con su propio ciclo de releases

**Estimación de esfuerzo:** 1–2 días (añadir soporte FlareSolverr a HttpClient + documentar configuración Docker Compose)

---

## 6. Recomendación

### Decisión: **Opción C (FlareSolverr para Cloudflare, sin SPAs)**

**Justificación:**

1. **Coste/beneficio desfavorable para Playwright:** Los 2-3 providers de manga que se beneficiarían de Playwright (InManga, potencialmente PDF Drive y SkyMangas) no justifican +500 MB Docker y +1 GB RAM. El catálogo tiene 605 sitios de complejidad baja/media que no necesitan headless browser.

2. **FlareSolverr resuelve el problema más urgente:** El bloqueo Cloudflare afecta a más sitios (TMO, LectorManga, LeerManga, y potencialmente otros del catálogo) que las SPAs puras. FlareSolverr es la solución estándar de la comunidad para esto.

3. **Arquitectura desacoplada:** Un servicio externo es más fácil de mantener, depurar, y escalar independientemente. Si en el futuro el volumen de providers SPA crece significativamente, se puede reevaluar.

4. **El prototipo debe ejecutarse para cerrar el ciclo:** Aunque la recomendación es clara sin ejecutarlo, los datos empíricos del prototipo validarían o refutarían estas estimaciones. Si los tiempos reales de Playwright son < 3 s y la RAM es < 300 MB, la Opción A ganaría peso.

### Prerrequisito para la Opción A en el futuro

Si se decide reevaluar Playwright más adelante, deben cumplirse estas condiciones:
- Al menos 5 providers SPA/anti-bot identificados que no tengan alternativa HTTP
- Los resultados del prototipo muestran tiempos < 8 s por request y RAM < 500 MB por browser
- Se dispone de un servidor con al menos 2 GB RAM libres

---

## 7. Plan de Acción Derivado

### 7.1 Providers que se pueden implementar YA (sin headless browser)

Estos providers son viables con el stack actual (httpx + cloudscraper + BS4):

| Provider | Tipo | Complejidad | Nota |
|----------|------|-------------|------|
| BookSee | Libros | Baja | HTML estándar, sin Cloudflare |
| OceanOfPDF | Libros | Baja | HTML estándar, sin protecciones |
| Cualquier provider con score 4+ del catálogo | — | Baja | 605 sitios evaluados como viabilidad alta |

### 7.2 Providers que requieren FlareSolverr (Opción C)

Si se implementa la Opción C, estos providers se vuelven viables:

| Provider | Tipo | Bloqueo actual |
|----------|------|----------------|
| TuMangaOnline (TMO) | Manga | Cloudflare agresivo, requiere login |
| LectorManga | Manga | Misma infraestructura que TMO |
| LeerManga | Manga | Cloudflare independiente |

### 7.3 Providers bloqueados hasta integración Playwright (Opción A)

Estos providers no son viables sin headless browser real:

| Provider | Tipo | Razón |
|----------|------|-------|
| InManga | Manga | SPA pura (Angular/Vue), HTML vacío sin JS |
| PDF Drive | Libros | Anti-bot avanzado con fingerprinting |

### 7.4 Próximos pasos inmediatos

1. **Ejecutar el prototipo** (`python scripts/test_playwright_prototype.py`) en entorno local para obtener métricas reales y validar o refutar las estimaciones de este informe.
2. **Evaluar FlareSolverr** como siguiente paso: probar si resuelve los challenges Cloudflare de TMO/LectorManga/LeerManga.
3. **Actualizar este informe** con los resultados empíricos del prototipo una vez ejecutado.
4. **Si FlareSolverr funciona:** implementar soporte en `HttpClient` (nuevo parámetro `use_flaresolverr`) y documentar configuración Docker Compose.
5. **Si FlareSolverr NO funciona:** reevaluar la Opción A (Playwright directo) con los datos reales del prototipo.

### 7.5 Nota sobre el prototipo

El script `scripts/test_playwright_prototype.py` está diseñado como herramienta de evaluación standalone. Para ejecutarlo:

```bash
# Instalar dependencias del prototipo (NO modifica requirements.txt)
pip install playwright httpx psutil
playwright install chromium

# Ejecutar
python scripts/test_playwright_prototype.py

# Salida:
#   - Resultados en stdout (JSON)
#   - Archivo JSON con timestamp en scripts/
```

El script genera automáticamente recomendaciones basadas en los umbrales definidos en la sección 3.2. Si `playwright_adds_value >= 2`, recomendará integración. Si `avg_time > 15s`, recomendará descartar. Estas recomendaciones automáticas deben ser revisadas por un humano antes de tomar una decisión final.

---

## Apéndice: Diseño Esbozado de `JsHttpClient` (Opción A)

Si en el futuro se decide integrar Playwright, este sería el diseño preliminar:

```python
# app/scraping/js_http_client.py (ESBOZO — NO IMPLEMENTAR)

class JsHttpClient:
    """Cliente HTTP con soporte JavaScript via Playwright.
    
    Feature-gated: solo se instancia si WTR_JS_RENDERING_ENABLED=true.
    Mantiene un pool de browsers Chromium calientes para reducir latencia.
    """
    
    def __init__(self, pool_size: int = 2, timeout_ms: int = 15_000):
        self._pool: list[Browser] = []
        self._pool_size = pool_size
        self._timeout = timeout_ms
        self._available = asyncio.Semaphore(pool_size)
    
    async def _get_browser(self) -> tuple[Browser, BrowserContext]:
        """Obtiene un browser del pool o crea uno nuevo."""
        ...
    
    async def get(self, url: str, wait_until: str = "networkidle") -> ScraperResponse:
        """Navega a una URL y devuelve el HTML renderizado."""
        ...
    
    async def close(self):
        """Cierra todos los browsers del pool."""
        ...
```

**Feature flag:** `WTR_JS_RENDERING_ENABLED=false` en `.env`. Si `false`, `JsHttpClient` nunca se instancia y los providers SPA lanzan `ProviderNotAvailableError`.

**Pool de browsers:** 2-3 instancias de Chromium pre-lanzadas, gestionadas con `asyncio.Semaphore`. Timeout de inactividad de 5 minutos (si un browser no se usa en 5 min, se cierra para liberar RAM).

**Integración con HttpClient existente:** El `HttpClient` actual recibe un parámetro opcional `js_client: JsHttpClient | None`. Los providers que necesiten JS rendering usan `self.http_client.js_get(url)` en lugar de `self.http_client.get(url)`.
