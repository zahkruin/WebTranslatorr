"""
FastAPI application factory and middleware configuration.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from app.api import torznab, health, domains, providers
from app.scraping.http_client import HttpClient
from app.services.domain_resolver import DomainResolver, domain_check_loop
from app.services.domain_strategies import DomainConfig


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown lifecycle."""
    logger = logging.getLogger("webtranslatorr")

    # --- Startup ---
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

    # Register providers with dynamic domains
    if settings.MEJORTORRENT_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="mejortorrent",
            default_domain=settings.MEJORTORRENT_DOMAIN,
            privtree_path="@mejortorrent",
            telegram_channel="MejorTorrentAp",
            known_domain_pattern=r"mejortorrent\.\w+",
        ))

    if settings.DONTORRENT_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="dontorrent",
            default_domain=settings.DONTORRENT_DOMAIN,
            privtree_path="@dontorrent",
            telegram_channel="DonTorrent",
            known_domain_pattern=r"dontorrent\.(?!blog)\w+",
        ))

    if settings.EBOOKELO_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="ebookelo",
            default_domain=settings.EBOOKELO_DOMAIN,
            known_domain_pattern=r"ebookelo\.\w+",
        ))

    if settings.EPUBLIBRE_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="epublibre",
            default_domain=settings.EPUBLIBRE_DOMAIN,
            privtree_path="@epublibre", # if exists
            known_domain_pattern=r"epublibre\.\w+",
        ))

    if settings.LECTULANDIA_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="lectulandia",
            default_domain=settings.LECTULANDIA_DOMAIN,
            privtree_path="@lectulandia", # if exists
            known_domain_pattern=r"lectulandia\.\w+",
        ))

    if settings.ESPAEBOOK_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="espaebook",
            default_domain=settings.ESPAEBOOK_DOMAIN,
            known_domain_pattern=r"espaebook\.\w+",
        ))

    if settings.HOLAEBOOK_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="holaebook",
            default_domain=settings.HOLAEBOOK_DOMAIN,
            known_domain_pattern=r"holaebook\.\w+",
        ))

    if settings.ANNASARCHIVE_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="annasarchive",
            default_domain=settings.ANNASARCHIVE_DOMAIN,
            known_domain_pattern=r"annas-archive\.\w+",
        ))

    # --- New providers ---
    if settings.EPUBFLIX1_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="epubflix1",
            default_domain=settings.EPUBFLIX1_DOMAIN,
            known_domain_pattern=r"epubflix1\.\w+",
        ))

    if settings.LIBGEN_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="libgen",
            default_domain=settings.LIBGEN_DOMAIN,
            known_domain_pattern=r"libgen\.\w+",
        ))

    if settings.BOOOBOOK_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="booobook",
            default_domain=settings.BOOOBOOK_DOMAIN,
            known_domain_pattern=r"booobook\.\w+",
        ))

    if settings.LECTUEPUBLIBRE5_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="lectuepublibre5",
            default_domain=settings.LECTUEPUBLIBRE5_DOMAIN,
            known_domain_pattern=r"lectuepublibre5\.\w+",
        ))

    if settings.MUNDOEPUBLIBRE1_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="mundoepublibre1",
            default_domain=settings.MUNDOEPUBLIBRE1_DOMAIN,
            known_domain_pattern=r"mundoepublibre1\.\w+",
        ))

    if settings.ZLIBRARY_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="zlibrary",
            default_domain=settings.ZLIBRARY_DOMAIN,
            known_domain_pattern=r"z-library\.\w+|singlelogin\.\w+",
        ))

    # --- Integration plan — new book providers ---
    if settings.EPUBGRATIS_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="epubgratis",
            default_domain=settings.EPUBGRATIS_DOMAIN,
            known_domain_pattern=r"epubgratis\.\w+",
        ))

    if settings.EBIBLIOTECA_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="ebiblioteca",
            default_domain=settings.EBIBLIOTECA_DOMAIN,
            known_domain_pattern=r"ebiblioteca\.\w+",
        ))

    if settings.BAJAEEBOOKS_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="bajaebooks",
            default_domain=settings.BAJAEEBOOKS_DOMAIN,
            known_domain_pattern=r"bajaebooks\.\w+",
        ))

    if settings.LELIBROS_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="lelibros",
            default_domain=settings.LELIBROS_DOMAIN,
            known_domain_pattern=r"lelibros\.\w+",
        ))

    # --- Integration plan — new video/torrent providers ---
    if settings.DIVXTOTAL_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="divxtotal",
            default_domain=settings.DIVXTOTAL_DOMAIN,
            known_domain_pattern=r"divxtotal\.\w+",
        ))

    if settings.ELITETORRENT_ENABLED:
        resolver.register_provider(DomainConfig(
            provider_id="elitetorrent",
            default_domain=settings.ELITETORRENT_DOMAIN,
            known_domain_pattern=r"elitetorrent\.\w+",
        ))

    app.state.domain_resolver = resolver
    
    # Initialize providers using the resolver
    torznab._init_providers(resolver)

    # Initial domain resolution at startup
    logger.info("Running initial domain resolution...")
    resolved = await resolver.resolve_all()
    for pid, domain in resolved.items():
        logger.info(f"  {pid} → {domain}")

    # Start background domain check loop
    check_task = asyncio.create_task(
        domain_check_loop(resolver, interval=settings.DOMAIN_CHECK_INTERVAL)
    )

    yield

    # --- Shutdown ---
    check_task.cancel()
    try:
        await check_task
    except asyncio.CancelledError:
        pass
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
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers — providers must come before torznab so
    # /api/providers (literal) is matched before /api/{provider_id} (dynamic)
    app.include_router(health.router)
    app.include_router(providers.router)
    app.include_router(torznab.router)
    app.include_router(domains.router)

    return app


app = create_app()
