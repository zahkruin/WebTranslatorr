# 03 — Modelos de Datos

## Propósito

Referencia de todos los modelos de datos compartidos: `SearchResult`, `ProviderCapabilities`, enums y excepciones. Define la estructura de datos que fluye entre providers, el router, el mapper Torznab, y las *Arr apps.

Cuándo consultar: para entender qué campos tiene SearchResult, cómo declarar capabilities de un provider, qué excepciones lanzar, o qué enums usar.

---

## SearchResult

**Archivo:** `app/core/models.py`

Dataclass que representa un resultado de búsqueda, agnóstico al provider de origen.

```python
@dataclass
class SearchResult:
    # ─── Campos obligatorios ───
    title: str                              # Título visible en *Arr
    guid: str                               # ID único (formato: "{provider_id}-{internal_id}")
    link: str                               # URL de la página de detalle en el sitio fuente
    download_url: str                       # URL del proxy de descarga o URL directa del archivo

    # ─── Metadatos básicos ───
    size_bytes: int = 0                     # Tamaño en bytes (0 = desconocido)
    pub_date: datetime = field(default_factory=datetime.now)
    categories: list[int] = field(default_factory=lambda: [8010])  # IDs Newznab
    description: str = ""                   # Descripción para el item RSS

    # ─── Campos opcionales por tipo de contenido ───
    author: Optional[str] = None            # Autor (libros)
    imdb_id: Optional[str] = None           # IMDb ID (películas, ej: "tt1234567")
    tvdb_id: Optional[int] = None           # TVDB ID (series)
    season: Optional[int] = None            # Número de temporada
    episode: Optional[int] = None           # Número de episodio

    # ─── Campos Torznab (simulados para DDL) ───
    seeders: Optional[int] = None           # Seeders simulados (típicamente 50-100)
    peers: Optional[int] = None             # Peers simulados
    info_hash: Optional[str] = None         # Hash del torrent (solo providers de torrent)
    magnet_uri: Optional[str] = None        # Magnet link (solo providers de torrent)

    # ─── Metadatos extra (flexibles, van a torznab:attr) ───
    extra_attrs: dict[str, str] = field(default_factory=dict)
```

### Convenciones de GUID

Formato: `"{provider_id}-{internal_id}"`

| Provider | Ejemplo GUID | Internal ID |
|----------|-------------|-------------|
| ebookelo | `ebookelo-1828` | ID numérico del libro |
| epublibre | `epublibre-el-quijote` | Slug del libro |
| lectulandia | `lectulandia-12345` | ID del libro |
| libgen | `libgen-a1b2c3d4e5f6...` | MD5 hash |
| annasarchive | `annasarchive-a1b2c3d4...` | MD5 hash |
| mejortorrent | `mejortorrent-30403` | ID numérico de película/serie |
| mejortorrent (episodio) | `mejortorrent-30403-e01` | ID + número de episodio |
| zlibrary | `zlibrary-1234567` | ID numérico del libro |

### Convenciones de download_url

**Para providers de libros:**
```python
download_url = f"{settings.EXTERNAL_URL}/api/download?provider={self.provider_id}&id={internal_id}&fmt=epub"
```

**Para providers de video con .torrent directo:**
```python
download_url = torrent_url  # URL directa al archivo .torrent
```

---

## ProviderCapabilities

**Archivo:** `app/core/models.py`

```python
@dataclass
class ProviderCapabilities:
    provider_id: str                        # ID del provider (ej: "ebookelo")
    display_name: str                       # Nombre legible (ej: "Ebookelo")
    supported_categories: list[int]         # IDs Newznab que soporta
    supported_search_params: list[str]      # Parámetros de búsqueda (ej: ["q", "author"])
    supports_book_search: bool = False      # Soporta t=book
    supports_tv_search: bool = False        # Soporta t=tvsearch
    supports_movie_search: bool = False     # Soporta t=movie
```

### Ejemplos

**Provider de libros:**
```python
ProviderCapabilities(
    provider_id="epublibre",
    display_name="EpubLibre",
    supported_categories=[7000, 7020, 8000, 8010],
    supported_search_params=["q"],
    supports_book_search=True,
)
```

**Provider de video:**
```python
ProviderCapabilities(
    provider_id="mejortorrent",
    display_name="MejorTorrent",
    supported_categories=[2000, 2030, 2040, 2045, 5000, 5030, 5040, 5045],
    supported_search_params=["q", "season", "ep", "imdbid"],
    supports_tv_search=True,
    supports_movie_search=True,
)
```

---

## Enums

**Archivo:** `app/core/enums.py`

### ContentType
```python
class ContentType(Enum):
    BOOK = "book"
    MOVIE = "movie"
    TV = "tv"
```

### SearchType
```python
class SearchType(Enum):
    GENERIC = "search"    # t=search
    TV = "tvsearch"       # t=tvsearch
    MOVIE = "movie"       # t=movie
    BOOK = "book"         # t=book
```

**Mapeo de parámetro `t` a SearchType:**
| Parámetro `t` | SearchType | Usado por |
|---------------|------------|-----------|
| `search` | `GENERIC` | Cualquier *Arr |
| `tvsearch` | `TV` | Sonarr |
| `movie` | `MOVIE` | Radarr |
| `book` | `BOOK` | Readarr |

---

## Jerarquía de Excepciones

**Archivo:** `app/core/exceptions.py`

```
WebTranslatorrError (base)
├── ProviderNotFoundError    # Provider no registrado en el registry
├── ProviderError            # Fallo genérico de provider
├── ScrapingError            # Fallo en web scraping
├── DownloadError            # Fallo en descarga
└── ValidationError          # Fallo en validación de request
```

### Cuándo usar cada una

| Excepción | Cuándo | Ejemplo |
|-----------|--------|---------|
| `ProviderNotFoundError` | `registry.get("id_inexistente")` | Provider mal escrito en URL |
| `ProviderError` | Un provider falla su operación principal | `search()` no puede conectar |
| `ScrapingError` | El parsing HTML falla | Selector CSS no encuentra elementos |
| `DownloadError` | La descarga del archivo falla | Timeout descargando EPUB |
| `ValidationError` | Parámetros de request inválidos | API key incorrecta |

**IMPORTANTE:** Los providers nunca deben propagar excepciones crudas. En `search()`, devolver lista vacía. En `get_download_url()`, devolver `None`.

---

## ScraperResponse

**Archivo:** `app/scraping/http_client.py`

Wrapper que normaliza `requests.Response` (cloudscraper) a una interfaz común:

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
        """Convierte requests.Response → ScraperResponse."""
```

Todos los métodos de HttpClient (`get`, `post`, `head`) devuelven `ScraperResponse`.

---

## DomainConfig

**Archivo:** `app/services/domain_strategies.py`

```python
@dataclass
class DomainConfig:
    provider_id: str                    # ID del provider
    default_domain: str                 # Dominio por defecto (fallback)
    privtree_path: Optional[str] = None # Ruta en privtr.ee (ej: "@mejortorrent")
    telegram_channel: Optional[str] = None  # Canal de Telegram (ej: "MejorTorrentAp")
    known_domain_pattern: str = ""      # Regex para identificar el dominio (ej: r"mejortorrent\.\w+")
```

---

## ResolvedDomain

**Archivo:** `app/services/domain_resolver.py`

```python
@dataclass
class ResolvedDomain:
    url: str                            # URL resuelta (ej: "https://www42.mejortorrent.eu")
    resolved_at: str                    # ISO 8601 timestamp
    source: str                         # "privtree" | "telegram" | "healthcheck" | "config" | "persisted"
    healthy: bool = True                # ¿Pasó el último health check?
    last_health_check: Optional[str] = None  # Timestamp del último check
```

---

## Archivos Relevantes

| Archivo | Contenido |
|---------|-----------|
| `app/core/models.py` | SearchResult, ProviderCapabilities |
| `app/core/enums.py` | ContentType, SearchType |
| `app/core/exceptions.py` | Jerarquía de excepciones |
| `app/scraping/http_client.py` | ScraperResponse |
| `app/services/domain_strategies.py` | DomainConfig |
| `app/services/domain_resolver.py` | ResolvedDomain |
