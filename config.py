from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 9811
    API_KEY: str = "changeme"
    LOG_LEVEL: str = "INFO"

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

    # Dominios (actualizables sin redesplegar)
    MEJORTORRENT_DOMAIN: str = "https://www42.mejortorrent.eu"
    DONTORRENT_DOMAIN: str = "https://dontorrent.reisen"
    EBOOKELO_DOMAIN: str = "https://ww2.ebookelo.com"
    EPUBLIBRE_DOMAIN: str = "https://epublibre.bid"
    LECTULANDIA_DOMAIN: str = "https://ww3.lectulandia.co"
    ESPAEBOOK_DOMAIN: str = "https://espaebook.cc"
    HOLAEBOOK_DOMAIN: str = "https://holaebook.com"
    ELEJANDRIA_DOMAIN: str = "https://www.elejandria.com"
    ANNASARCHIVE_DOMAIN: str = "https://annas-archive.org"
    GUTENBERG_DOMAIN: str = "https://gutenberg.org"

    # TMDB (para resolver IMDb ID → título español)
    TMDB_API_KEY: str = ""

    # Scraping
    RATE_LIMIT_PER_SECOND: float = 2.0
    MAX_RETRIES: int = 3
    REQUEST_TIMEOUT: int = 30

    # Cache
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 300

    # Domain Resolution (auto-detección de dominios)
    DOMAIN_CHECK_INTERVAL: int = 1800      # Segundos entre checks (30 min)
    DOMAIN_VALIDATION_TIMEOUT: int = 10    # Timeout para HTTP HEAD de validación

    # Proxy (opcional)
    HTTP_PROXY: str = ""

    class Config:
        env_file = ".env"
        env_prefix = "WTR_"


settings = Settings()
