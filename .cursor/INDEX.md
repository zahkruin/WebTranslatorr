# WebTranslatorr — Índice de Documentación Agéntica

> **Para agentes de IA que trabajan en este proyecto.**
> Usa esta guía para determinar qué documentación consultar según tu tarea.

---

## Mapa de Casos de Uso → Documentación

### 🆕 "Quiero crear un nuevo provider"
1. `context/05-providers-base.md` — Interfaz BaseProvider, contrato, ciclo de vida
2. `context/17-adding-providers.md` — Guía paso a paso con template
3. `context/06-provider-strategies/ebookelo.md` — Ejemplo de referencia (provider complejo)
4. `context/06-provider-strategies/epublibre.md` — Ejemplo de referencia (provider simple)
5. `context/02-configuration.md` — Variables de entorno que necesitas añadir
6. `context/03-data-models.md` — SearchResult, ProviderCapabilities
7. `context/09-categories.md` — IDs de categoría Newznab

### 🐛 "Un provider específico está fallando"
1. `context/06-provider-strategies/{nombre_del_provider}.md` — Estrategia de scraping (selectores, URLs, trampas)
2. `context/16-known-issues.md` — Bugs conocidos y workarounds
3. `context/10-domain-resolver.md` — Si es problema de dominio cambiado
4. `context/04-http-client.md` — Si hay errores de rate-limit, timeout, o cloudscraper

### 🔍 "Quiero entender cómo se rutean las peticiones"
1. `context/07-smart-router.md` — Algoritmo de inferencia de contenido, keywords, heurísticas
2. `context/01-architecture.md` — Diagrama de flujo completo
3. `context/13-api-endpoints.md` — Cómo llegan los parámetros desde las *Arr apps

### ⚙️ "Necesito cambiar la configuración"
1. `context/02-configuration.md` — Todas las variables, defaults, prefijo `WTR_`
2. `config.py` — Archivo fuente de configuración Pydantic

### 📡 "Quiero depurar el protocolo Torznab"
1. `context/08-torznab-protocol.md` — Especificación del protocolo, namespaces, formato XML
2. `context/09-categories.md` — IDs de categoría y cómo las usan Readarr/Sonarr/Radarr
3. `context/13-api-endpoints.md` — Endpoints que exponen el XML

### 🌐 "El dominio de un provider cambió"
1. `context/10-domain-resolver.md` — Cadena de estrategias (privtr.ee → Telegram → healthcheck)
2. `context/02-configuration.md` — Variables `*_DOMAIN` y `DOMAIN_CHECK_INTERVAL`
3. `context/13-api-endpoints.md` — Endpoints `/api/domains/*` para forzar resolución

### 📦 "Cómo funciona la descarga de archivos"
1. `context/13-api-endpoints.md` — Endpoint `/api/download`, parámetros, flujo
2. `context/12-zip-extractor.md` — Extracción on-the-fly de EPUBs desde ZIPs
3. `context/04-http-client.md` — Cómo se descargan los archivos (cloudscraper vs httpx)

### 🧪 "Necesito escribir/ejecutar tests"
1. `context/15-testing.md` — pytest, fixtures, asyncio, patrones de test
2. `context/03-data-models.md` — Cómo construir SearchResult en tests
3. `context/05-providers-base.md` — Cómo mockear HttpClient para tests de provider

### 🚀 "Quiero desplegar"
1. `context/14-deployment.md` — Docker Compose, build local, deploy.sh
2. `context/02-configuration.md` — Variables de entorno requeridas para producción

### 🏗️ "Quiero entender la arquitectura global"
1. `context/01-architecture.md` — Diagrama, flujo de datos, dependencias entre módulos
2. `context/05-providers-base.md` — Sistema de providers
3. `context/03-data-models.md` — Modelos de datos compartidos
4. `AGENTS.md` — Visión general y convenciones

### 🧵 "Cómo funciona el HTTP client"
1. `context/04-http-client.md` — Rate limiting, User-Agent rotation, cloudscraper wrapper, retries

### 📊 "Entender los modelos de datos"
1. `context/03-data-models.md` — SearchResult, ProviderCapabilities, Enums, Excepciones

### 🔒 "El scraping está roto (cambió la web del provider)"
1. `context/06-provider-strategies/{provider}.md` — Selectores CSS, URLs, estructura HTML esperada
2. `context/04-http-client.md` — Si es problema de Cloudflare/rate-limiting

### 🩺 "Problema de rendimiento o caché"
1. `context/11-cache.md` — TTLCache, keys, invalidación
2. `context/04-http-client.md` — Rate limiting, timeouts
3. `context/07-smart-router.md` — Si se están consultando providers innecesarios

### 🗺️ "Navegar la base de código por primera vez"
1. `AGENTS.md` — Visión general, stack, estructura de módulos, anti-patrones
2. `context/01-architecture.md` — Diagrama de arquitectura
3. `styleguide.md` — Convenciones de código

---

## Índice Completo de Documentos

| # | Documento | Descripción |
|---|-----------|-------------|
| | `INDEX.md` | Este documento. Mapa casos de uso → docs. |
| | `AGENTS.md` | Guía general del proyecto para agentes. |
| | `styleguide.md` | Convenciones de código. |
| **01** | `context/01-architecture.md` | Arquitectura global y flujo de datos. |
| **02** | `context/02-configuration.md` | Todas las variables de configuración. |
| **03** | `context/03-data-models.md` | Modelos de datos: SearchResult, ProviderCapabilities, enums, excepciones. |
| **04** | `context/04-http-client.md` | HttpClient: rate limiting, retries, cloudscraper. |
| **05** | `context/05-providers-base.md` | Sistema de providers y BaseProvider. |
| **06** | `context/06-provider-strategies/` | Estrategias de scraping por provider (14 archivos). |
| **07** | `context/07-smart-router.md` | SmartRouter: inferencia de contenido y routing. |
| **08** | `context/08-torznab-protocol.md` | Protocolo Torznab/Newznab, mapper y caps. |
| **09** | `context/09-categories.md` | Mapeo de categorías Newznab. |
| **10** | `context/10-domain-resolver.md` | Resolución dinámica de dominios. |
| **11** | `context/11-cache.md` | SearchCache: TTL y estructura. |
| **12** | `context/12-zip-extractor.md` | Extracción on-the-fly de ZIPs. |
| **13** | `context/13-api-endpoints.md` | Endpoints FastAPI documentados. |
| **14** | `context/14-deployment.md` | Guía de despliegue. |
| **15** | `context/15-testing.md` | Guía de testing. |
| **16** | `context/16-known-issues.md` | Bugs y problemas conocidos. |
| **17** | `context/17-adding-providers.md` | Guía completa para añadir providers. |
