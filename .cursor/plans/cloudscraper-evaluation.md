# Evaluación de Cloudscraper para Bypass Cloudflare

> **Fecha**: 2026-07-02
> **Plan relacionado**: [PLAN-20260701-003](./PLAN-20260701-003-plan.md) — Paso 8
> **Script**: [`scripts/test_cloudscraper.py`](../../scripts/test_cloudscraper.py)
> **Depende de**: Ejecución del script (Paso 7 del plan)
> **Agente**: `scraping`

---

## 1. Resumen de Hallazgos

> ⚠️ **Estado**: Los resultados reales requieren ejecutar `scripts/test_cloudscraper.py`. La tabla siguiente refleja el **status esperado** basado en el comportamiento observado durante el desarrollo de los providers de manga (bloqueo 403 + challenge Cloudflare en todos los intentos con httpx estándar).

| Sitio | URL | Status Cloudscraper | Notas |
|-------|-----|---------------------|-------|
| TuMangaOnline (TMO) | <https://visortmo.com> | **Pendiente de ejecución** | Cloudflare agresivo (Turnstile/JS challenge). Requiere login para scraping funcional. Misma infraestructura que LectorManga. |
| LectorManga | <https://lectortmo.com> | **Pendiente de ejecución** | Misma infraestructura que TMO (dominio espejo). Mismo challenge Cloudflare. Login requerido. |
| LeerManga | <https://leermanga.net> | **Pendiente de ejecución** | Infraestructura independiente. También protegido por Cloudflare. No requiere login para catálogo público. |

### Clasificación del veredicto

El script `test_cloudscraper.py` emite uno de estos veredictos por sitio:

| Veredicto | Significado | Criterio |
|-----------|-------------|----------|
| `BYPASS_OK` | Cloudscraper rompe el challenge | Al menos un intento con cloudscraper devuelve HTML con contenido real (no challenge) |
| `BYPASS_WORKAROUND` | Cloudscraper no bloqueado, pero resultado incierto | HTML sin firma de challenge pero tampoco con contenido reconocible de manga |
| `BYPASS_FAILED` | Cloudscraper no puede romper el challenge | Todas las respuestas contienen página de bloqueo/challenge Cloudflare o error HTTP |

---

## 2. Protocolo de Prueba

El script `scripts/test_cloudscraper.py` implementa un protocolo de **4 intentos progresivos** por cada dominio, diseñado para aislar la causa de fallo y determinar si cloudscraper —con o sin parámetros adicionales— logra el bypass.

### 2.1. Intentos

| # | Nombre | Método | Descripción |
|---|--------|--------|-------------|
| 1 | `http_simple` | `HttpClient.get(url, use_scraper=False)` | HTTP estándar con httpx. Sirve como **baseline**: establece que el sitio está efectivamente protegido. |
| 2 | `cloudscraper_default` | `HttpClient.get(url, use_scraper=True)` | Cloudscraper con su configuración por defecto (browser emulado: Chrome 120 / Windows). Evalúa si la librería, sin ayuda adicional, puede resolver el challenge. |
| 3 | `cloudscraper_headers` | `HttpClient.get(url, use_scraper=True, headers=extra_headers)` | Cloudscraper + headers contextuales (`Referer`, `Origin`, `Cache-Control: no-cache`, `Pragma: no-cache`). Evalúa si el bypass requiere contexto de navegación simulado. |
| 4 | `cloudscraper_cookies` | `HttpClient.get(url, use_scraper=True)` + cookies pre-establecidas | Cloudscraper con cookies de sesión simuladas (`_ga`, `_gid`, `language=es`, `consent=accepted`). Evalúa si el bypass depende de un estado de sesión previo. |

### 2.2. Análisis de cada intento

Para cada intento, `analyze_response()` extrae:

- **`status`**: `SUCCESS`, `BLOCKED`, `UNKNOWN`, `HTTP_{code}`, o `ERROR`
- **`is_challenge`**: `True` si el HTML contiene firmas de challenge Cloudflare (ver §2.3)
- **`has_content`**: `True` si el HTML parece contenido real de manga (ver §2.4)
- **`http_status`**, **`html_length`**, **`elapsed_ms`**, **`content_type`**
- **`notable_headers`**: Headers relevantes (`cf-ray`, `cf-cache-status`, `server`, `set-cookie`)
- **`html_snippet`**: Primeros 200 bytes del HTML (para inspección manual)

### 2.3. Firmas de Challenge Cloudflare

El script detecta challenge/bloqueo mediante 12 firmas en el HTML:

```
challenge-platform, cf_chl_opt, cf-browser-verification, checking your browser,
_cf_chl_, jschl-answer, just a moment..., window._cf_chl_opt, cf_captcha,
cf-wrapper, attention required, security check
```

Si **cualquiera** de estas cadenas aparece (case-insensitive), el intento se clasifica como `BLOCKED`.

### 2.4. Heurística de Contenido Real

Para determinar si el HTML contiene contenido de manga (no una página de bloqueo vacía/placeholder), se usa una heurística compuesta:

- **Keyword scoring**: cuenta palabras clave de manga (`manga`, `capítulo`, `leer`, `género`, `scanlation`, `biblioteca`, `catálogo`, etc.) — hasta 14 puntos
- **Estructura HTML**: presencia de `<!DOCTYPE>`, `<html>`, `<body>`, `<head>` — hasta 2 puntos
- **Tamaño del HTML**: > 5000 bytes suma 1 punto
- **Umbral**: ≥ 3 puntos → contenido real

### 2.5. Configuración del HttpClient durante la prueba

La instancia de `HttpClient` usada en el script se configura con parámetros **conservadores** para evitar bans durante las pruebas:

```python
HttpClient(
    rate_limit_per_second=1.0,    # 1 req/s por dominio
    max_retries=1,                # Sin reintentos (falla rápido)
    timeout=15,                   # 15s timeout
)
```

El cloudscraper subyacente se crea con emulación de **Chrome 120 / Windows** (`browser: 'chrome', platform: 'windows', mobile: False`), igual que en producción.

### 2.6. Artefactos generados

El script produce dos salidas:

1. **Consola**: progreso en tiempo real con iconos (`✅` SUCCESS, `🚫` BLOCKED, `❓` UNKNOWN, `❌` ERROR) y un resumen final con recomendación
2. **JSON**: `scripts/cloudscraper_report_{timestamp}.json` con resultados completos (intentos, headers notables, snippets HTML, veredictos)

---

## 3. Resultados Esperados por Escenario

### 3.1. Escenario A: Cloudscraper funciona (`BYPASS_OK`)

#### Evidencia esperada

- El intento `cloudscraper_default` (o uno posterior) devuelve `status=SUCCESS`
- `is_challenge=False` (no contiene firmas de challenge)
- `has_content=True` (HTML con palabras clave de manga + estructura)
- `http_status=200`
- `html_length > 5000`
- Headers notables: presencia de `cf-ray` o `cf-cache-status` indica que la respuesta pasó por Cloudflare pero el challenge fue resuelto

#### "Happy path" documentado

Si cloudscraper funciona, la configuración mínima sería:

```python
# En el provider:
resp = await self.http_client.get(
    "https://visortmo.com/library",
    use_scraper=True,
)
```

El `HttpClient` ya inyecta automáticamente:
- User-Agent rotado (Chrome 120 / Windows)
- Headers HTTP estándar (`Accept`, `Accept-Language`, `Accept-Encoding`, `DNT`, `Connection`)
- Cloudscraper con browser emulado

#### Recomendación en este escenario

1. **Crear plan de implementación** para providers TMO y LeerManga (o al menos el que haya funcionado)
2. **Diseñar estrategia de login**: TMO/LectorManga requieren autenticación para acceder al contenido. Opciones:
   - **Credenciales en `.env`**: `WTR_TMO_USERNAME`, `WTR_TMO_PASSWORD` — simple pero requiere mantenimiento manual
   - **Cookie de sesión persistente**: obtener una cookie de sesión válida manualmente y configurarla en `.env` (`WTR_TMO_SESSION_COOKIE`). La cookie se inyecta en cada request vía cloudscraper. Ventaja: no requiere login programático. Desventaja: expira y requiere renovación manual
   - **Login programático**: el provider hace POST de login en `__init__` o lazy-login en el primer `search()`. Complejo pero completamente autónomo
3. **Evaluar LeerManga**: si solo funciona para LeerManga (no requiere login), priorizar su implementación por ser más simple
4. **Documentar parámetros exactos** del intento exitoso (headers adicionales, cookies) para replicar en el provider

#### Riesgos persistentes incluso con bypass

- **Rate limiting de Cloudflare**: aunque se pase el challenge, Cloudflare puede imponer rate limits secundarios (basados en `cf-ray` header)
- **Rotación de challenges**: Cloudflare actualiza sus mecanismos periódicamente; un bypass que funciona hoy puede fallar mañana
- **Bloqueo por fingerprinting**: si el patrón de requests es detectable (mismo UA, misma IP, misma secuencia de endpoints), Cloudflare puede escalar a bloqueo total

### 3.2. Escenario B: Cloudscraper NO funciona (`BYPASS_FAILED`)

#### Evidencia esperada

- Los 3 intentos con cloudscraper devuelven `status=BLOCKED`
- `is_challenge=True` en todos los intentos
- `has_content=False`
- HTML contiene firmas como `just a moment...`, `window._cf_chl_opt`, `challenge-platform`
- Posibles códigos HTTP: `403` (Forbidden con challenge), `503` (Service Unavailable / challenge timeout), `200` (página de challenge servida como 200)

#### Análisis de por qué falla

Si cloudscraper no logra el bypass, las causas más probables son:

| Causa | Mecanismo | Por qué cloudscraper no lo maneja |
|-------|-----------|-----------------------------------|
| **Cloudflare Turnstile** | CAPTCHA interactivo que requiere resolver un puzzle visual o hacer clic en casillas | Cloudscraper puede resolver JS challenges automáticos pero **no puede resolver CAPTCHAs interactivos**. Turnstile es el sucesor de reCAPTCHA/hCaptcha y requiere interacción humana o un solver externo. |
| **JA3 / TLS Fingerprinting** | Cloudflare identifica el cliente por la firma TLS (JA3 hash) de la librería TLS subyacente | Aunque cloudscraper modifica el TLS handshake, versiones recientes de Cloudflare pueden detectar la firma TLS de `requests`/`urllib3` y bloquear incluso con browser emulado. |
| **HTTP/2 fingerprinting** | Cloudflare inspecciona el orden y valores de los pseudo-headers HTTP/2 | Cloudscraper usa `requests` que opera sobre HTTP/1.1; si el sitio fuerza HTTP/2, la ausencia de pseudo-headers HTTP/2 delata al cliente. |
| **Behavioral analysis** | Cloudflare analiza patrones de navegación (orden de requests, tiempos entre requests, URLs visitadas) | Cloudscraper no simula navegación; hace requests aislados que no replican el comportamiento de un navegador real (sin cargar CSS/JS/imágenes, sin respetar el orden de carga de recursos). |
| **IP reputation** | Cloudflare bloquea basado en la reputación de la IP (datacenter, VPN, hosting) | Independiente de cloudscraper; requiere proxy residencial o rotación de IPs. |

#### Evaluación de alternativas

Si cloudscraper falla, hay tres caminos viables:

##### Alternativa 1: FlareSolverr

FlareSolverr es un servicio externo (Docker) que resuelve challenges de Cloudflare usando un navegador headless (Firefox/Chromium) controlado vía Puppeteer/Playwright.

| Ventajas | Desventajas |
|----------|-------------|
| No añade dependencias pesadas al proyecto WebTranslatorr | Componente externo: requiere otro contenedor Docker |
| Resuelve Turnstile y JS challenges complejos | Latencia adicional: ~5-10s por request (el navegador debe cargar la página y esperar el challenge) |
| Se deploya como servicio separado, desacoplado | Punto único de fallo: si FlareSolverr no está disponible, los providers de manga fallan |
| Proyecto activo con comunidad (GitHub: FlareSolverr/FlareSolverr) | Consume más recursos (RAM/CPU) que cloudscraper |
| Expone API HTTP simple: `POST /v1` con `{"cmd": "request.get", "url": "..."}` | Overhead de red: request a FlareSolverr → navegador → Cloudflare → respuesta → FlareSolverr → WebTranslatorr |

**Configuración Docker necesaria** (docker-compose.yml):

```yaml
services:
  webtranslatorr:
    # ... existing config ...
    environment:
      - WTR_FLARESOLVERR_URL=http://flaresolverr:8191/v1

  flaresolverr:
    image: flaresolverr/flaresolverr:latest
    container_name: flaresolverr
    ports:
      - "8191:8191"
    environment:
      - LOG_LEVEL=info
      - HEADLESS=true
    restart: unless-stopped
```

**Integración en HttpClient**: se añadiría un flag `use_flaresolverr=True` que enruta el request a FlareSolverr en lugar de cloudscraper, con un `ScraperResponse` adaptado.

##### Alternativa 2: Actualizar cloudscraper

Verificar si hay una versión más reciente de `cloudscraper` que soporte los challenges actuales de Cloudflare.

```bash
pip install --upgrade cloudscraper
python -c "import cloudscraper; print(cloudscraper.__version__)"
```

**Limitaciones**:
- El proyecto `cloudscraper` tiene actividad intermitente en GitHub; puede estar desactualizado frente a las últimas protecciones de Cloudflare
- Incluso con actualización, no resuelve Turnstile (limitación inherente de operar sin navegador real)
- Si el problema es JA3 fingerprinting a nivel TLS, una actualización de `cloudscraper` puede no ser suficiente (depende de `requests`/`urllib3`)

##### Alternativa 3: Headless browser (Playwright / Selenium)

Implementar un navegador headless directamente (sin FlareSolverr como intermediario):

| Ventajas | Desventajas |
|----------|-------------|
| Control total sobre la sesión de navegación | Añade dependencia pesada al proyecto (chromium + driver) |
| Puede manejar login interactivo, cookies, y navegación multi-página | Aumenta significativamente el tiempo de respuesta |
| Resuelve cualquier challenge (es un navegador real) | Complejidad de implementación: manejo de sesiones, concurrencia, limpieza de recursos |
| No depende de servicio externo | Requiere `playwright` o `selenium` + `chromium` en el contenedor Docker |

**Comparativa con FlareSolverr**:

| Criterio | Playwright directo | FlareSolverr |
|----------|-------------------|--------------|
| Dependencias | `playwright` + `chromium` (~300MB) | Solo cliente HTTP |
| Complejidad de código | Alta (gestión de browser pool) | Baja (API HTTP) |
| Latencia | ~3-8s | ~5-10s (incluye overhead de red) |
| Mantenimiento | Interno (nosotros) | Externo (comunidad FlareSolverr) |
| Escalabilidad | Acoplada al proceso de WebTranslatorr | Independiente |

**Recomendación**: **FlareSolverr** es preferible a Playwright directo porque:
1. Desacopla la complejidad del navegador del código de WebTranslatorr
2. La comunidad mantiene las actualizaciones contra nuevos challenges de Cloudflare
3. La integración es trivial (API HTTP)
4. El contenedor Docker es auto-contenido

### 3.3. Escenario C: Cloudscraper necesita workaround (`BYPASS_WORKAROUND`)

#### Evidencia esperada

- Al menos un intento con cloudscraper devuelve `status=UNKNOWN` y `is_challenge=False`
- No hay firmas de challenge en el HTML
- Pero `has_content=False`: el HTML no contiene contenido reconocible de manga (podría ser un placeholder, página de login, o página de mantenimiento)

#### Interpretación

Este resultado sugiere que cloudscraper **pasó el challenge de Cloudflare** pero el contenido devuelto no es el esperado. Posibles causas:

1. **Redirección a login**: TMO/LectorManga redirigen a la página de login si no hay sesión autenticada
2. **Redirección geográfica**: el sitio redirige a un dominio diferente o muestra contenido localizado
3. **Bot detection secundaria**: Cloudflare pasó, pero el sitio tiene su propia protección (WAF, análisis de comportamiento)
4. **Rate limiting sin challenge**: Cloudflare limita la tasa pero no muestra challenge explícito

#### Parámetros adicionales necesarios

- **Cookies de sesión reales**: en lugar de cookies simuladas, obtener una cookie de sesión válida de un navegador real y configurarla en `.env`
- **Login previo**: hacer un POST de login con credenciales antes del request de búsqueda
- **Headers específicos del sitio**: `X-Requested-With: XMLHttpRequest` para endpoints AJAX, o headers custom que el frontend envía

#### Viabilidad de implementar con workaround

Si el bypass requiere solo parámetros adicionales (cookies, headers), la implementación es viable:

- **Complejidad**: Baja-Media (inyectar cookies/headers en el request)
- **Mantenimiento**: Las cookies expiran; requiere mecanismo de renovación
- **Riesgo**: Si Cloudflare escala la protección, el workaround puede dejar de funcionar

En este escenario, se recomienda **proceder con la implementación pero planificar FlareSolverr como fallback**.

---

## 4. Recomendación Final

La recomendación depende del resultado de ejecutar `scripts/test_cloudscraper.py`. Se presentan tres caminos:

### Si cloudscraper funciona (`BYPASS_OK`) para ≥1 sitio

✅ **Implementar providers con cloudscraper**, priorizando:

1. **LeerManga** primero (no requiere login → implementación más simple)
2. **TMO/LectorManga** después (requiere estrategia de login con cookies de sesión en `.env`)
3. Mantener FlareSolverr como **plan B documentado** para cuando cloudscraper eventualmente falle

### Si cloudscraper falla (`BYPASS_FAILED`) en todos los sitios

🔄 **Adoptar FlareSolverr** como solución de bypass:

1. Añadir servicio `flaresolverr` a `docker-compose.yml`
2. Implementar flag `use_flaresolverr=True` en `HttpClient` (similar a `use_scraper`)
3. Los providers de manga usarán `self.http_client.get(url, use_flaresolverr=True)`
4. Documentar la dependencia en `README.md` y `14-deployment.md`

### Si cloudscraper necesita workaround (`BYPASS_WORKAROUND`)

⚠️ **Implementar con workaround + monitoreo**:

1. Documentar los parámetros exactos necesarios (cookies, headers)
2. Implementar providers con esos parámetros
3. Añadir health check que verifique periódicamente que el bypass sigue funcionando
4. Tener FlareSolverr listo como fallback inmediato

---

## 5. Próximos Pasos

### Inmediatos (tras ejecutar el script)

1. **Ejecutar** `python scripts/test_cloudscraper.py` y revisar el informe JSON generado
2. **Clasificar** cada sitio según el veredicto obtenido (`BYPASS_OK` / `BYPASS_FAILED` / `BYPASS_WORKAROUND`)
3. **Completar** la tabla de la sección 1 con los resultados reales (reemplazar "Pendiente de ejecución")
4. **Decidir** el camino a seguir según la sección 4

### Si se decide implementar providers

1. **Crear plan de implementación** para el/los provider(s) de manga viables
2. **Diseñar estrategia de autenticación** (cookies de sesión, login programático, o credentials en `.env`)
3. **Implementar el provider** siguiendo `17-adding-providers.md` y `05-providers-base.md`
4. **Añadir tests** de integración para el provider (con mocks de HTTP o VCR)

### Si se decide adoptar FlareSolverr

1. **Añadir** `WTR_FLARESOLVERR_URL` a `config.py` y `.env.example`
2. **Implementar** soporte en `HttpClient` (método `_request_via_flaresolverr`)
3. **Añadir** servicio a `docker-compose.yml`
4. **Documentar** en `14-deployment.md` y `README.md`
5. **Probar** con los 3 dominios de manga

### Si se decide workaround con cloudscraper

1. **Documentar** parámetros exactos del intento exitoso (del JSON generado)
2. **Implementar** los parámetros en el provider
3. **Añadir health check** periódico para detectar rotura del bypass
4. **Preparar** FlareSolverr como fallback (tener `docker-compose.yml` y código listos)

---

## Apéndice: Artefactos del Sistema

### HttpClient — Cloudscraper integration

**Archivo**: `app/scraping/http_client.py` (206 líneas)

El `HttpClient` crea una instancia de cloudscraper en `__init__`:

```python
self._scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
)
```

Cuando un provider llama a `get(url, use_scraper=True)`, el request se ejecuta en un thread del executor:

```python
resp = await loop.run_in_executor(
    None,
    lambda: self._scraper.get(url, headers=headers, ...)
)
return ScraperResponse.from_requests_response(resp)
```

**Providers que ya usan cloudscraper**: Anna's Archive, EpubLibre, Lectulandia, Espaebook, HolaEbook, Z-Library (6 de 20 providers).

### Dominios y resolución para manga

Los dominios de los 3 sitios de manga **no están** actualmente en `config.py` ni en `DomainResolver`. Sería necesario:

1. Añadir `TMO_DOMAIN`, `LECTOR_MANGA_DOMAIN`, `LEER_MANGA_DOMAIN` a `config.py`
2. Registrar los dominios en `DomainResolver` si se desea resolución dinámica
3. Los providers usarían `self.base_url` inyectado con el dominio resuelto

### Login en TMO/LectorManga

TMO y LectorManga usan **WordPress** con el plugin **Madara** para gestión de manga. El endpoint de login típico es:

```
POST https://visortmo.com/wp-login.php
Content-Type: application/x-www-form-urlencoded

log={username}&pwd={password}&wp-submit=Log+In&redirect_to=&testcookie=1
```

La sesión se mantiene vía cookies de WordPress (`wordpress_logged_in_*`). Cloudscraper puede mantener estas cookies en `self._scraper.cookies` entre requests si se usa la misma instancia.

---

> **Nota**: Este documento es un marco de evaluación. Los veredictos reales (`BYPASS_OK` / `FAILED` / `WORKAROUND`) y la recomendación final deben completarse tras ejecutar `scripts/test_cloudscraper.py` y analizar el informe JSON generado.
