from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="WTR_",
    )

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 9811
    API_KEY: str = "changeme"
    LOG_LEVEL: str = "INFO"
    # External URL visible to *Arr apps (e.g. "http://localhost:9811")
    # If empty, falls back to "http://HOST:PORT" (but HOST may be 0.0.0.0)
    EXTERNAL_URL: str = "http://localhost:9811"

    # Providers
    EBOOKELO_ENABLED: bool = True
    EPUBLIBRE_ENABLED: bool = True
    LECTULANDIA_ENABLED: bool = True
    ESPAEBOOK_ENABLED: bool = True
    HOLAEBOOK_ENABLED: bool = True
    ELEJANDRIA_ENABLED: bool = True
    ANNASARCHIVE_ENABLED: bool = True
    GUTENBERG_ENABLED: bool = True
    MEJORTORRENT_ENABLED: bool = True
    DONTORRENT_ENABLED: bool = False
    # New providers
    EPUBFLIX1_ENABLED: bool = True
    LIBGEN_ENABLED: bool = True
    BOOOBOOK_ENABLED: bool = True
    LECTUEPUBLIBRE5_ENABLED: bool = True
    MUNDOEPUBLIBRE1_ENABLED: bool = True
    ZLIBRARY_ENABLED: bool = True
    # Integration plan Phase 1 & 2 — new providers
    EPUBGRATIS_ENABLED: bool = True
    EBIBLIOTECA_ENABLED: bool = True
    BAJAEEBOOKS_ENABLED: bool = True
    LELIBROS_ENABLED: bool = True
    DIVXTOTAL_ENABLED: bool = False  # Domain very unstable, disabled by default
    ELITETORRENT_ENABLED: bool = False  # Unverified, disabled by default

    # Dominios (actualizables sin redesplegar)
    MEJORTORRENT_DOMAIN: str = "https://www42.mejortorrent.eu"
    DONTORRENT_DOMAIN: str = "https://dontorrent.reisen"
    EBOOKELO_DOMAIN: str = "https://ww2.ebookelo.com"
    EPUBLIBRE_DOMAIN: str = "https://epublibre.bid"
    LECTULANDIA_DOMAIN: str = "https://ww3.lectulandia.co"
    ESPAEBOOK_DOMAIN: str = "https://espaebook.cc"
    HOLAEBOOK_DOMAIN: str = "https://holaebook.com"
    ELEJANDRIA_DOMAIN: str = "https://www.elejandria.com"
    ANNASARCHIVE_DOMAIN: str = "https://annas-archive.gl"
    GUTENBERG_DOMAIN: str = "https://gutenberg.org"
    # New provider domains
    EPUBFLIX1_DOMAIN: str = "https://epubflix1.com"
    LIBGEN_DOMAIN: str = "https://libgen.ee"
    BOOOBOOK_DOMAIN: str = "https://es.booobook.bond"
    LECTUEPUBLIBRE5_DOMAIN: str = "https://lectuepublibre5.com"
    MUNDOEPUBLIBRE1_DOMAIN: str = "https://mundoepublibre1.com"
    ZLIBRARY_DOMAIN: str = "https://z-library.sk"
    # Integration plan — new provider domains
    EPUBGRATIS_DOMAIN: str = "https://www.epubgratis.org"
    EBIBLIOTECA_DOMAIN: str = "https://ebiblioteca.org"
    BAJAEEBOOKS_DOMAIN: str = "https://bajaebooks.info"
    LELIBROS_DOMAIN: str = "https://lelibros.online"
    DIVXTOTAL_DOMAIN: str = "https://divxtotal.wtf"
    ELITETORRENT_DOMAIN: str = "https://www.elitetorrent.com"
    # BookSee & OceanOfPDF (Plan 003)
    BOOKSEE_ENABLED: bool = True
    BOOKSEE_DOMAIN: str = "https://en.booksee.org"
    OCEANOFPDF_ENABLED: bool = True
    OCEANOFPDF_DOMAIN: str = "https://oceanofpdf.com"

    # TMDB (para resolver IMDb ID → título español)
    TMDB_API_KEY: str = ""

    # Scraping
    RATE_LIMIT_PER_SECOND: float = 2.0
    MAX_RETRIES: int = 3
    REQUEST_TIMEOUT: int = 30

    # FlareSolverr (bypass Cloudflare Turnstile vía navegador headless externo)
    # Dejar vacío para deshabilitar. Ejemplo: "http://192.168.0.102:8191"
    FLARESOLVERR_URL: str = ""

    # Torrent Blackhole watcher — monitors a directory for .torrent files
    # dropped by Readarr and downloads the actual files via webseed.
    # Dejar vacío para deshabilitar.
    BLACKHOLE_DIR: str = ""
    BLACKHOLE_OUTPUT_DIR: str = ""  # default: same as BLACKHOLE_DIR

    # Cache
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 300

    # Domain Resolution (auto-detección de dominios)
    DOMAIN_CHECK_INTERVAL: int = 1800      # Segundos entre checks (30 min)
    DOMAIN_VALIDATION_TIMEOUT: int = 10    # Timeout para HTTP HEAD de validación

    # Proxy (opcional)
    HTTP_PROXY: str = ""

    # Translation Pipeline
    TRANSLATION_CACHE_PATH: str = ""
    TRANSLATION_PIPELINE_TIMEOUT: int = 10
    GOOGLE_BOOKS_API_KEY: str = ""
    TRANSLATION_PIPELINE_WIKIDATA_ENABLED: bool = True
    TRANSLATION_PIPELINE_GOOGLE_BOOKS_ENABLED: bool = True
    TRANSLATION_PIPELINE_SEARCH_ENABLED: bool = False

    # Search language (ISO 639-1 code: es, en, fr, de, it, pt)
    # Controls which target language Wikidata / Google Books lookups
    # use when translating book titles from English.
    DEFAULT_SEARCH_LANGUAGE: str = "es"


settings = Settings()
