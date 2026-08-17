# WebTranslatorr — AI Agent Instructions

> **Cursor lee este archivo automáticamente como instrucción global del proyecto.**
> Esta es la fuente de verdad de la documentación agéntica del proyecto.

## 📚 Documentación agéntica — Dónde está todo

Toda la documentación agéntica vive bajo **`.cursor/`**:

| Ubicación | Contenido |
|-----------|-----------|
| `.cursor/rules/*.mdc` | Reglas activas cargadas automáticamente por Cursor |
| `.cursor/context/` | Documentos de contexto del código (arquitectura, módulos, protocolo, providers) |
| `.cursor/analysis/` | Análisis estático del proyecto |
| `.cursor/agent/` | Definiciones de agentes especializados y orquestador |
| `.cursor/learning/` | Registro de errores, experiencias y patrones |
| `.cursor/plans/` | Planes de implementación |
| `.cursor/legacy/` | Documentación antigua (referencia histórica) |
| `.cursor/methodology.md` | Metodología de Documentación Agéntica (MDA) |

**Regla inviolable:** antes de leer, planificar, modificar o ejecutar *cualquier cosa*
sobre este proyecto, debes leer `.cursor/README.md` y este `AGENTS.md`.

---

## Visión General

WebTranslatorr es un proxy Torznab universal que actúa como capa de traducción entre
aplicaciones *Arr (Readarr, Sonarr, Radarr) y fuentes de contenido heterogéneas.
Traduce fuentes de descarga directa (DDL) al formato Torznab.

**Providers implementados:** 16 de libros + 4 de video = 20 providers activos.

## Stack Tecnológico

- **Framework**: FastAPI (Python 3.11+)
- **HTTP Client**: httpx con rate-limiting y retry + cloudscraper para bypass Cloudflare
- **Parsing HTML**: BeautifulSoup4 + lxml
- **Configuración**: Pydantic Settings (.env, prefijo `WTR_`)
- **Testing**: pytest + pytest-asyncio
- **Cache**: cachetools (TTLCache)

## Cómo Arrancar

```bash
pip install -r requirements.txt
python main.py         # → http://localhost:9811
# o
docker-compose up -d
```

El servidor escucha en `http://localhost:9811` (puerto estándar Jackett).

## Estructura de Módulos

```
app/
├── api/           # Endpoints FastAPI (torznab.py, health.py, domains.py)
├── core/          # Modelos (SearchResult), categorías, enums, excepciones
├── providers/     # 20 implementaciones de providers (books/ + video/)
├── routing/       # SmartRouter - enrutamiento por tipo de contenido
├── scraping/      # HttpClient, parser helpers
├── services/      # DomainResolver, SearchCache, translation pipeline
├── torznab/       # Mapeo a XML (mapper, caps, errors)
└── utils/         # ZipExtractor, torrent generator, url safety
```

## Documentación por caso de uso

Consulta `.cursor/INDEX.md` para el mapa completo de casos de uso → documentación.

| Tarea | Documento principal |
|-------|-------------------|
| Crear un provider nuevo | `.cursor/context/17-adding-providers.md` |
| Depurar un provider roto | `.cursor/context/06-provider-strategies/{provider}.md` |
| Cambió un dominio | `.cursor/context/10-domain-resolver.md` |
| Error en el XML Torznab | `.cursor/context/08-torznab-protocol.md` |
| Problema de rendimiento | `.cursor/context/11-cache.md` |
| Escribir tests | `.cursor/context/15-testing.md` |
| Desplegar | `.cursor/context/14-deployment.md` |
| Entender la arquitectura | `.cursor/context/01-architecture.md` |

## Convenciones Importantes

### Providers
- Heredar de `BaseProvider` (ABC)
- Implementar: `search()`, `get_download_url()`, `get_capabilities()`
- No interactuar directamente con formato Torznab — solo devolver `SearchResult`
- Usar `self.http_client` para requests (rate-limiting integrado)
- NUNCA propagar excepciones — devolver `[]` o `None`

### Categorías Newznab
- Libros: 7000, 7020, 8000, 8010
- Películas: 2000, 2030, 2040, 2045
- TV: 5000, 5030, 5040, 5045

### Código
- Async/await para todo I/O
- Type hints en todos los métodos públicos
- snake_case para variables, PascalCase para clases
- Google-style docstrings
- Logging con `self.logger` (no print)

## Qué NO Hacer

- **NUNCA seguir enlaces de profitablecpmgate.com** (trampa publicitaria de Ebookelo)
- No hardcodear URLs de providers — usar configuración o DomainResolver
- No hacer requests síncronos — todo es async/await
- No parsear XML manualmente — usar ElementTree
- No devolver diccionarios desde search() — usar SearchResult dataclass
- No propagar excepciones desde providers

## Regla de mantenimiento obligatorio

Todo cambio en archivos fuente (`app/`, `config.py`, `main.py`, `Dockerfile`,
`docker-compose*.yml`) **debe** ir acompañado de la actualización de los documentos
agénticos correspondientes en `.cursor/`. Usa `.cursor/doc-mapping.json` para
identificar qué documentos actualizar y ejecuta `python scripts/validate_docs.py --strict`
antes de hacer commit.
