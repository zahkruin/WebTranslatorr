# 02 — Configuración

## Propósito

Referencia completa de todas las variables de configuración de WebTranslatorr. Cubre el archivo `config.py` (Pydantic Settings), el archivo `.env`, y cómo se mapean las variables de entorno.

Cuándo consultar: para añadir/quitar providers, cambiar timeouts, configurar dominios, habilitar cache, o depurar problemas de entorno.

---

## Archivos de Configuración

| Archivo | Rol |
|---------|-----|
| `config.py` | Definición de settings con Pydantic + defaults |
| `.env` | Variables de entorno (no commiteado) |
| `.env.example` | Template de variables (commiteado, referencia) |

**Prefijo:** Todas las variables de entorno usan el prefijo `WTR_`.

---

## Tabla Completa de Variables

### Server

| Variable env | Campo Python | Default | Descripción |
|-------------|-------------|---------|-------------|
| `WTR_HOST` | `HOST` | `0.0.0.0` | Dirección de escucha |
| `WTR_PORT` | `PORT` | `9811` | Puerto (estándar Jackett) |
| `WTR_API_KEY` | `API_KEY` | `changeme` | API key para autenticación *Arr |
| `WTR_LOG_LEVEL` | `LOG_LEVEL` | `INFO` | Nivel de logging (DEBUG, INFO, WARNING, ERROR) |
| `WTR_EXTERNAL_URL` | `EXTERNAL_URL` | `http://localhost:9811` | URL externa visible por las apps *Arr (usada en download_url de SearchResult) |

### Providers — Enable/Disable

| Variable env | Campo Python | Default | Provider |
|-------------|-------------|---------|----------|
| `WTR_EBOOKELO_ENABLED` | `EBOOKELO_ENABLED` | `True` | Ebookelo |
| `WTR_EPUBLIBRE_ENABLED` | `EPUBLIBRE_ENABLED` | `True` | EpubLibre |
| `WTR_LECTULANDIA_ENABLED` | `LECTULANDIA_ENABLED` | `True` | Lectulandia |
| `WTR_ESPAEBOOK_ENABLED` | `ESPAEBOOK_ENABLED` | `True` | Espaebook |
| `WTR_HOLAEBOOK_ENABLED` | `HOLAEBOOK_ENABLED` | `True` | HolaEbook |
| `WTR_ELEJANDRIA_ENABLED` | `ELEJANDRIA_ENABLED` | `True` | Elejandria (NO IMPLEMENTADO) |
| `WTR_ANNASARCHIVE_ENABLED` | `ANNASARCHIVE_ENABLED` | `True` | Anna's Archive |
| `WTR_GUTENBERG_ENABLED` | `GUTENBERG_ENABLED` | `True` | Gutenberg (NO IMPLEMENTADO) |
| `WTR_MEJORTORRENT_ENABLED` | `MEJORTORRENT_ENABLED` | `True` | MejorTorrent |
| `WTR_DONTORRENT_ENABLED` | `DONTORRENT_ENABLED` | `False` | DonTorrent |
| `WTR_EPUBFLIX1_ENABLED` | `EPUBFLIX1_ENABLED` | `True` | Epubflix1 (NUEVO) |
| `WTR_LIBGEN_ENABLED` | `LIBGEN_ENABLED` | `True` | Library Genesis (NUEVO) |
| `WTR_BOOOBOOK_ENABLED` | `BOOOBOOK_ENABLED` | `True` | B00k.Bond (NUEVO) |
| `WTR_LECTUEPUBLIBRE5_ENABLED` | `LECTUEPUBLIBRE5_ENABLED` | `True` | LectuEpubLibre5 (NUEVO) |
| `WTR_MUNDOEPUBLIBRE1_ENABLED` | `MUNDOEPUBLIBRE1_ENABLED` | `True` | MundoEpubLibre1 (NUEVO) |
| `WTR_ZLIBRARY_ENABLED` | `ZLIBRARY_ENABLED` | `True` | Z-Library (NUEVO) |

### Providers — Dominios

| Variable env | Campo Python | Default |
|-------------|-------------|---------|
| `WTR_MEJORTORRENT_DOMAIN` | `MEJORTORRENT_DOMAIN` | `https://www42.mejortorrent.eu` |
| `WTR_DONTORRENT_DOMAIN` | `DONTORRENT_DOMAIN` | `https://dontorrent.reisen` |
| `WTR_EBOOKELO_DOMAIN` | `EBOOKELO_DOMAIN` | `https://ww2.ebookelo.com` |
| `WTR_EPUBLIBRE_DOMAIN` | `EPUBLIBRE_DOMAIN` | `https://epublibre.bid` |
| `WTR_LECTULANDIA_DOMAIN` | `LECTULANDIA_DOMAIN` | `https://ww3.lectulandia.co` |
| `WTR_ESPAEBOOK_DOMAIN` | `ESPAEBOOK_DOMAIN` | `https://espaebook.cc` |
| `WTR_HOLAEBOOK_DOMAIN` | `HOLAEBOOK_DOMAIN` | `https://holaebook.com` |
| `WTR_ELEJANDRIA_DOMAIN` | `ELEJANDRIA_DOMAIN` | `https://www.elejandria.com` |
| `WTR_ANNASARCHIVE_DOMAIN` | `ANNASARCHIVE_DOMAIN` | `https://annas-archive.org` |
| `WTR_GUTENBERG_DOMAIN` | `GUTENBERG_DOMAIN` | `https://gutenberg.org` |
| `WTR_EPUBFLIX1_DOMAIN` | `EPUBFLIX1_DOMAIN` | `https://epubflix1.com` |
| `WTR_LIBGEN_DOMAIN` | `LIBGEN_DOMAIN` | `https://libgen.ee` |
| `WTR_BOOOBOOK_DOMAIN` | `BOOOBOOK_DOMAIN` | `https://es.booobook.bond` |
| `WTR_LECTUEPUBLIBRE5_DOMAIN` | `LECTUEPUBLIBRE5_DOMAIN` | `https://lectuepublibre5.com` |
| `WTR_MUNDOEPUBLIBRE1_DOMAIN` | `MUNDOEPUBLIBRE1_DOMAIN` | `https://mundoepublibre1.com` |
| `WTR_ZLIBRARY_DOMAIN` | `ZLIBRARY_DOMAIN` | `https://z-library.sk` |

### TMDB API

| Variable env | Campo Python | Default | Descripción |
|-------------|-------------|---------|-------------|
| `WTR_TMDB_API_KEY` | `TMDB_API_KEY` | `""` | API key de TMDB para resolver IMDb ID → título español |

### Scraping

| Variable env | Campo Python | Default | Descripción |
|-------------|-------------|---------|-------------|
| `WTR_RATE_LIMIT_PER_SECOND` | `RATE_LIMIT_PER_SECOND` | `2.0` | Requests por segundo por dominio |
| `WTR_MAX_RETRIES` | `MAX_RETRIES` | `3` | Reintentos máximos por request |
| `WTR_REQUEST_TIMEOUT` | `REQUEST_TIMEOUT` | `30` | Timeout HTTP en segundos |

### Cache

| Variable env | Campo Python | Default | Descripción |
|-------------|-------------|---------|-------------|
| `WTR_CACHE_ENABLED` | `CACHE_ENABLED` | `True` | Habilitar cache de resultados |
| `WTR_CACHE_TTL_SECONDS` | `CACHE_TTL_SECONDS` | `300` | TTL de la cache en segundos (5 min) |

### Domain Resolution

| Variable env | Campo Python | Default | Descripción |
|-------------|-------------|---------|-------------|
| `WTR_DOMAIN_CHECK_INTERVAL` | `DOMAIN_CHECK_INTERVAL` | `1800` | Segundos entre chequeos de dominio (30 min) |
| `WTR_DOMAIN_VALIDATION_TIMEOUT` | `DOMAIN_VALIDATION_TIMEOUT` | `10` | Timeout HTTP HEAD para validación de dominio |

### Proxy

| Variable env | Campo Python | Default | Descripción |
|-------------|-------------|---------|-------------|
| `WTR_HTTP_PROXY` | `HTTP_PROXY` | `""` | Proxy HTTP (ej: `http://proxy:8080`) |

---

## Cómo Añadir Configuración para un Nuevo Provider

1. **`config.py`**: Añadir 3 campos:
   ```python
   NUEVO_ENABLED: bool = True
   NUEVO_DOMAIN: str = "https://nuevo.com"
   ```

2. **`.env.example`**: Añadir entradas:
   ```bash
   WTR_NUEVO_ENABLED=true
   WTR_NUEVO_DOMAIN=https://nuevo.com
   ```

3. **`app/api/torznab.py`**: Añadir en `_init_providers()`:
   ```python
   if settings.NUEVO_ENABLED:
       registry.register(NuevoProvider(http_client, resolver))
   ```

4. **`app/server.py`**: Si usa DomainResolver, añadir DomainConfig en `lifespan()`:
   ```python
   if settings.NUEVO_ENABLED:
       resolver.register_provider(DomainConfig(
           provider_id="nuevo",
           default_domain=settings.NUEVO_DOMAIN,
           known_domain_pattern=r"nuevo\.\w+",
       ))
   ```

---

## Jerarquía de Carga de Configuración

1. **Defaults** en `config.py` (clase `Settings`)
2. **Archivo `.env`** (si existe, cargado por `python-dotenv` via `pydantic-settings`)
3. **Variables de entorno** del sistema (tienen prioridad máxima)

El prefijo `WTR_` se configura en:
```python
class Config:
    env_file = ".env"
    env_prefix = "WTR_"
```

---

## Archivos Relevantes

| Archivo | Rol |
|---------|-----|
| `config.py` | Definición de Settings (Pydantic) |
| `.env.example` | Template de variables de entorno |
| `.env` | Variables de entorno reales (gitignored) |
| `app/server.py` | Usa settings para crear HttpClient y DomainResolver |
| `app/api/torznab.py` | Usa settings para decidir qué providers registrar |
