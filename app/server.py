"""
FastAPI application factory and middleware configuration.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from app.api import torznab, health, domains, providers, admin
from app.persistence.database import init_db
from app.providers.registry import registry
from app.scraping.http_client import HttpClient
from app.services.cache import search_cache
from app.services.config_manager import ConfigManager
from app.services.domain_resolver import DomainResolver, domain_check_loop
from app.services.domain_strategies import DomainConfig
from app.core.version import get_version


_DOMAIN_CONFIGS: dict[str, dict] = {
    "mejortorrent": {"default_domain": settings.MEJORTORRENT_DOMAIN, "privtree_path": "@mejortorrent", "telegram_channel": "MejorTorrentAp", "known_domain_pattern": r"mejortorrent\.\w+"},
    "dontorrent": {"default_domain": settings.DONTORRENT_DOMAIN, "privtree_path": "@dontorrent", "telegram_channel": "DonTorrent", "known_domain_pattern": r"dontorrent\.(?!blog)\w+"},
    "ebookelo": {"default_domain": settings.EBOOKELO_DOMAIN, "known_domain_pattern": r"ebookelo\.\w+"},
    "epublibre": {"default_domain": settings.EPUBLIBRE_DOMAIN, "privtree_path": "@epublibre", "known_domain_pattern": r"epublibre\.\w+"},
    "lectulandia": {"default_domain": settings.LECTULANDIA_DOMAIN, "privtree_path": "@lectulandia", "known_domain_pattern": r"lectulandia\.\w+"},
    "espaebook": {"default_domain": settings.ESPAEBOOK_DOMAIN, "known_domain_pattern": r"espaebook\.\w+"},
    "holaebook": {"default_domain": settings.HOLAEBOOK_DOMAIN, "known_domain_pattern": r"holaebook\.\w+"},
    "annasarchive": {
        "default_domain": settings.ANNASARCHIVE_DOMAIN,
        "known_domain_pattern": r"annas-archive\.\w+",
        "shadowlibraries_path": "DirectDownloads/AnnasArchive/",
        "mirrors": [
            "https://annas-archive.gl",
            "https://annas-archive.pk",
            "https://annas-archive.gd",
        ],
    },
    "epubflix1": {"default_domain": settings.EPUBFLIX1_DOMAIN, "known_domain_pattern": r"epubflix1\.\w+"},
    "libgen": {"default_domain": settings.LIBGEN_DOMAIN, "known_domain_pattern": r"libgen\.\w+"},
    "booobook": {"default_domain": settings.BOOOBOOK_DOMAIN, "known_domain_pattern": r"booobook\.\w+"},
    "lectuepublibre5": {"default_domain": settings.LECTUEPUBLIBRE5_DOMAIN, "known_domain_pattern": r"lectuepublibre5\.\w+"},
    "mundoepublibre1": {"default_domain": settings.MUNDOEPUBLIBRE1_DOMAIN, "known_domain_pattern": r"mundoepublibre1\.\w+"},
    "zlibrary": {"default_domain": settings.ZLIBRARY_DOMAIN, "known_domain_pattern": r"z-library\.\w+|singlelogin\.\w+"},
    "epubgratis": {"default_domain": settings.EPUBGRATIS_DOMAIN, "known_domain_pattern": r"epubgratis\.\w+"},
    "ebiblioteca": {"default_domain": settings.EBIBLIOTECA_DOMAIN, "known_domain_pattern": r"ebiblioteca\.\w+"},
    "bajaebooks": {"default_domain": settings.BAJAEEBOOKS_DOMAIN, "known_domain_pattern": r"bajaebooks\.\w+"},
    "lelibros": {"default_domain": settings.LELIBROS_DOMAIN, "known_domain_pattern": r"lelibros\.\w+"},
    "divxtotal": {"default_domain": settings.DIVXTOTAL_DOMAIN, "known_domain_pattern": r"divxtotal\.\w+"},
    "elitetorrent": {"default_domain": settings.ELITETORRENT_DOMAIN, "known_domain_pattern": r"elitetorrent\.\w+"},
    "booksee": {"default_domain": settings.BOOKSEE_DOMAIN, "known_domain_pattern": r"booksee\.\w+"},
    "oceanofpdf": {"default_domain": settings.OCEANOFPDF_DOMAIN, "known_domain_pattern": r"oceanofpdf\.\w+"},
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown lifecycle."""
    logger = logging.getLogger("webtranslatorr")
    version = get_version()

    logger.info("=" * 60)
    logger.info("  WebTranslatorr v%s", version)
    logger.info("  Universal Torznab Proxy for *Arr applications")
    logger.info("=" * 60)

    if settings.ENV == "production":
        if not settings.API_KEY or settings.API_KEY == "changeme":
            raise RuntimeError("WTR_API_KEY must be set in production")

    external_host = (urlparse(settings.EXTERNAL_URL or "").hostname or "").lower()
    if external_host in ("localhost", "127.0.0.1", "0.0.0.0"):
        logger.warning(
            "EXTERNAL_URL is %s — *Arr apps on other hosts cannot reach download links",
            settings.EXTERNAL_URL,
        )

    # --- Startup ---
    # Initialize SQLite database and run migration if needed
    await init_db()
    config_manager = ConfigManager()
    app.state.config_manager = config_manager

    # Create shared HTTP client
    http_client = HttpClient(
        rate_limit_per_second=settings.RATE_LIMIT_PER_SECOND,
        max_retries=settings.MAX_RETRIES,
        timeout=settings.REQUEST_TIMEOUT,
        proxy=settings.HTTP_PROXY or None,
    )
    app.state.http_client = http_client

    # Initialize DomainResolver
    resolver = DomainResolver(
        http_client=http_client,
        persistence_path="data/domains.json",
        validation_timeout=settings.DOMAIN_VALIDATION_TIMEOUT,
    )

    # Register providers with dynamic domains — driven by DB config
    # Register DomainConfigs for all enabled providers
    enabled_providers = await config_manager.get_all_enabled_providers()
    for p in enabled_providers:
        pid = p["provider_id"]
        dc = _DOMAIN_CONFIGS.get(pid)
        if dc:
            # Use domain from DB if set, otherwise use the hardcoded default
            domain = p.get("domain") or dc["default_domain"]
            resolver.register_provider(DomainConfig(
                provider_id=pid,
                default_domain=domain,
                privtree_path=dc.get("privtree_path"),
                telegram_channel=dc.get("telegram_channel"),
                shadowlibraries_path=dc.get("shadowlibraries_path"),
                known_domain_pattern=dc.get("known_domain_pattern") or "",
                mirrors=dc.get("mirrors") or [],
            ))

    app.state.domain_resolver = resolver

    async def _on_domain_change(provider_id: str, new_domain: str):
        try:
            provider = registry.get(provider_id)
            provider.base_url = new_domain.rstrip("/")
            logger.info("Updated base_url for %s → %s", provider_id, new_domain)
            await search_cache.invalidate(provider_id)
        except Exception as e:
            logger.warning("Could not update base_url for %s: %s", provider_id, e)

    resolver.on_domain_change(_on_domain_change)

    # Initialize providers using the resolver and config_manager
    await torznab._init_providers(resolver, http_client, config_manager)
    app.state.registry = registry

    # Initialize TranslationPipeline singleton (if enabled)
    from app.services.translation_pipeline import get_translation_pipeline
    pipeline = await get_translation_pipeline()
    if pipeline is not None:
        logger.info("TranslationPipeline enabled and initialised for search integration")

    # Initial domain resolution at startup
    logger.info("Running initial domain resolution...")
    resolved = await resolver.resolve_all()
    for pid, domain in resolved.items():
        logger.info(f"  {pid} → {domain}")
        await _on_domain_change(pid, domain)

    # Start background domain check loop
    check_task = asyncio.create_task(
        domain_check_loop(resolver, interval=settings.DOMAIN_CHECK_INTERVAL)
    )

    # Start torrent blackhole watcher (if configured)
    from app.services.blackhole_watcher import start_blackhole_watcher
    blackhole_task = start_blackhole_watcher()

    yield

    # --- Shutdown ---
    check_task.cancel()
    try:
        await check_task
    except asyncio.CancelledError:
        pass
    if blackhole_task is not None:
        blackhole_task.cancel()
        try:
            await blackhole_task
        except asyncio.CancelledError:
            pass
    # Shutdown TranslationPipeline
    from app.services.translation_pipeline import shutdown_translation_pipeline
    await shutdown_translation_pipeline()
    await http_client.close()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Application factory pattern."""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    app = FastAPI(
        title="WebTranslatorr",
        description="Universal Torznab Proxy for *Arr applications",
        version=get_version(),
        lifespan=lifespan,
        docs_url="/docs" if settings.ENABLE_DOCS else None,
        redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    )

    cors_origins = (
        [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
        if settings.CORS_ORIGINS
        else ["*"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers — order matters! FastAPI matches routes in registration order.
    # /api/providers, /api/domains, and /api/admin must be registered BEFORE torznab,
    # because torznab.router has a catch-all /api/{provider_id} dynamic route that would
    # intercept those path segments before the dedicated routers get a chance to respond.
    # Health/API routers must also be registered BEFORE the `/` StaticFiles mount.
    app.include_router(health.router)
    app.include_router(providers.router)
    app.include_router(domains.router)
    app.include_router(admin.router)
    app.include_router(torznab.router)

    # Mount static files LAST so they don't shadow API routes.
    # FastAPI prioritizes routes registered via include_router over StaticFiles mounts.
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.mount("/", StaticFiles(directory="static", html=True), name="frontend")

    return app


app = create_app()
