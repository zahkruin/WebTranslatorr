# 16 — Known Issues & Bugs

## Propósito

Documenta bugs conocidos, problemas de arquitectura, workarounds y el estado de las funcionalidades pendientes. Basado en el plan de análisis (`plans/analysis_and_improvement_plan.md`).

Cuándo consultar: al depurar comportamientos inesperados, planificar fixes, o entender por qué ciertas cosas funcionan de cierta manera.

---

## 🔴 Bugs Críticos (ya corregidos en el código actual)

Los siguientes bugs del plan de análisis ya fueron solucionados en el código actual:

### Bug 1: Providers devolvían dict en lugar de SearchResult ✅ CORREGIDO

**Archivos:** epublibre.py, lectulandia.py, espaebook.py, holaebook.py, annas_archive.py

**Estado actual:** Los 5 providers ya usan `SearchResult` dataclass y tienen firmas de `search()` compatibles con `BaseProvider`. Ya no devuelven diccionarios.

### Bug 2: URLs construidas con 0.0.0.0 ✅ CORREGIDO

**Estado actual:** Los providers ahora usan `settings.EXTERNAL_URL` para construir las `download_url`. El campo `EXTERNAL_URL` tiene default `http://localhost:9811`.

**Workaround si falla:** Asegurarse de que `.env` tenga `WTR_EXTERNAL_URL=http://IP_O_DOMINIO:9811` apuntando a una IP accesible por las *Arr apps.

### Bug 3: Firma de search() con category vs categories ✅ CORREGIDO

**Estado actual:** Todos los providers usan la firma estándar: `search(self, query, categories: list[int] = None, ...)`.

### Bug 4: HttpClient y cloudscraper ✅ CORREGIDO

**Estado actual:** `ScraperResponse` wrapper estandariza la respuesta de cloudscraper (`requests.Response`) a la misma interfaz que httpx.

---

## 🟠 Problemas de Alta Prioridad

### Issue 7: Dominios por defecto probablemente desactualizados

**Severidad:** Alta
**Archivos:** `config.py:33-50`, `app/services/domain_resolver.py`

Los dominios hardcodeados en `config.py` pueden quedar obsoletos. El `DomainResolver` intenta resolverlos dinámicamente, pero si todas las estrategias fallan, se usa el dominio por defecto.

**Mitigación actual:**
- Cadena de 3 estrategias en `DomainResolver`: privtr.ee → Telegram → healthcheck
- `domain_check_loop` verifica cada 30 minutos (configurable con `WTR_DOMAIN_CHECK_INTERVAL`)
- Persistencia de dominios resueltos en `data/domains.json`

**Workaround manual:**
```bash
# Forzar resolución de todos los dominios
curl -X POST http://localhost:9811/api/domains/refresh

# Verificar estado
curl http://localhost:9811/api/domains
```

### Issue 8: Elejandria y Gutenberg no implementados

**Severidad:** Alta
**Archivos:** `config.py`, `app/api/torznab.py:123-126`

Los flags `ELEJANDRIA_ENABLED` y `GUTENBERG_ENABLED` existen pero no hay implementación. Al iniciar, se loggea una advertencia:
```
WARNING - Elejandria provider is configured as enabled but not yet implemented
WARNING - Gutenberg provider is configured as enabled but not yet implemented
```

**Estado:** Stubs pendientes. Estos providers están declarados pero no se registran en `ProviderRegistry`.

### Issue 9: Cache implementado pero no usado en todos los paths

**Severidad:** Media
**Archivos:** `app/services/cache.py`, `app/api/torznab.py:169-174`

El `SearchCache` está implementado con `cachetools.TTLCache` y se usa en `_handle_torznab_request()`. Sin embargo:
- Solo cachea resultados de `search()`, no de `get_download_url()`
- La invalidación es limitada (TTLCache no soporta eliminación por patrón)

### Issue 10: Soporte de proxy HTTP

**Severidad:** Media
**Archivos:** `app/scraping/http_client.py`

El `HTTP_PROXY` está configurado como campo en Settings y se pasa a `HttpClient.__init__()`. Se configuran proxies tanto en `httpx.AsyncClient` como en `cloudscraper.create_scraper()`.

**Verificar:** Si se usa proxy, asegurarse de que el formato sea correcto: `http://proxy:8080`.

---

## 🟡 Mejoras de Media Prioridad

### Issue 11: `_last_request` crece sin límite

**Archivo:** `app/scraping/http_client.py:71`

El diccionario `_last_request: dict[str, float]` acumula timestamps por dominio sin limpieza periódica. Con el tiempo, si se visitan muchos dominios únicos, puede crecer.

**Impacto:** Mínimo (solo memory leak si hay cientos de dominios únicos).

### Issue 12: `app/scraping/parser.py` no se usa

**Archivo:** `app/scraping/parser.py`

Funciones helper (`parse_html`, `extract_text`, `extract_href`, `safe_int`) existen pero ningún provider las importa. Cada provider hace `BeautifulSoup(html, "lxml")` directamente.

**Estado:** Código huérfano. Puede eliminarse o refactorizarse para que los providers lo usen.

### Issue 13: MejorTorrent no limita resultados en parsing inicial

**Archivo:** `app/providers/video/mejortorrent.py:102`

El `_parse_results()` no tiene límite. El `limit` se aplica después del enriquecimiento (más costoso). Si la página de búsqueda devuelve 200+ resultados, se enriquecen todos innecesariamente.

**Workaround:** El parámetro `limit` se pasa a `_fetch_detail_page` que itera sobre `results[:limit]`.

### Issue 14: Cobertura de tests incompleta

**Archivos:** `tests/`

Los tests cubren:
- ✅ CategoryMapper, TorznabMapper, TorznabErrors
- ✅ SmartRouter (básico)
- ✅ ProviderRegistry, SearchCache
- ✅ Health endpoint
- ❌ La mayoría de providers no tienen tests unitarios
- ❌ DomainResolver no tiene tests de integración
- ❌ No hay tests end-to-end del flujo Torznab

---

## 🟢 Funcionalidades Pendientes

| Funcionalidad | Estado | Prioridad |
|--------------|--------|-----------|
| Provider Elejandria | No implementado | Media |
| Provider Gutenberg | No implementado | Media |
| Cache de download_url | No implementado | Baja |
| Rate limiting global (cross-provider) | No implementado | Baja |
| Métricas/Prometheus | No implementado | Baja |
| Web UI de estado | No implementado | Baja |

---

## Anti-Patrones a Evitar

1. **No hardcodear dominios en providers** — Usar `self.base_url` (inyectado vía constructor) o `settings.*_DOMAIN`.
2. **No hacer requests síncronos** — Todo es `async/await`. Cloudscraper se ejecuta en `run_in_executor`.
3. **No propagar excepciones desde providers** — Devolver `[]` o `None`.
4. **No seguir enlaces de `profitablecpmgate.com`** — Es una trampa de anuncios en Ebookelo.
5. **No asumir que los dominios son estables** — Usar `DomainResolver` para providers con dominios cambiantes.

---

## Cómo Reportar un Bug

1. Verificar el log: `docker logs webtranslatorr` o `tail -f webtranslatorr.log`
2. Identificar el provider y el error específico
3. Consultar la estrategia del provider en `context/06-provider-strategies/{provider}.md`
4. Verificar si el dominio está actualizado: `GET /api/domains`
5. Si es un cambio en la web fuente, actualizar los selectores CSS en el provider

---

## Archivos Relevantes

| Archivo | Contenido |
|---------|-----------|
| `plans/analysis_and_improvement_plan.md` | Plan de análisis original con bugs y mejoras |
| `plans/coverage_improvement_plan.md` | Plan para mejorar cobertura de tests |
| `plans/new_providers_and_multi_indexer_plan.md` | Plan de nuevos providers e indexer múltiple |
