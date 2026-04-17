"""
Endpoint principal Torznab.
Compatible con el estándar Newznab/Torznab para *Arr apps.

URL que se configura en Sonarr/Radarr/Readarr:
  http://localhost:9117/api?apikey=tu_api_key

Parámetros que los *Arr envían:
  - t: tipo de función (caps, search, tvsearch, movie, book)
  - q: query de búsqueda
  - cat: categorías (comma-separated)
  - apikey: autenticación
  - offset/limit: paginación
  - imdbid: ID de IMDb (Radarr)
  - tvdbid: ID de TVDB (Sonarr)
  - season/ep: temporada y episodio (Sonarr)
"""
import asyncio
import logging

from fastapi import APIRouter, Query, Request, Response

from config import settings
from app.providers.registry import registry
from app.providers.books.ebookelo import EbookeloProvider
from app.providers.books.epublibre import EpubLibreProvider
from app.providers.books.lectulandia import LectulandiaProvider
from app.providers.books.espaebook import EspaebookProvider
from app.providers.books.holaebook import HolaEbookProvider
from app.providers.books.annas_archive import AnnasArchiveProvider
from app.providers.video.mejortorrent import MejorTorrentProvider
from app.providers.video.dontorrent import DonTorrentProvider
from app.routing.smart_router import smart_router
from app.utils.zip_extractor import ZipExtractor
from app.torznab.mapper import TorznabMapper
from app.torznab.caps import CapsGenerator
from app.torznab.errors import TorznabErrors
from app.scraping.http_client import HttpClient
from app.core.categories import CategoryMapper

router = APIRouter()

# Inicializar providers en startup
_http_client = None


def _get_http_client():
    global _http_client
    if _http_client is None:
        _http_client = HttpClient(
            rate_limit_per_second=settings.RATE_LIMIT_PER_SECOND,
            max_retries=settings.MAX_RETRIES,
            timeout=settings.REQUEST_TIMEOUT,
        )
    return _http_client


def _init_providers(resolver=None):
    """Inicializa los providers según configuración."""
    http_client = _get_http_client()

    # Limpiar registro antes de inicializar para ser idempotente
    registry.clear()

    if settings.EBOOKELO_ENABLED:
        registry.register(EbookeloProvider(http_client, resolver))

    if settings.EPUBLIBRE_ENABLED:
        registry.register(EpubLibreProvider(http_client, resolver))

    if settings.LECTULANDIA_ENABLED:
        registry.register(LectulandiaProvider(http_client, resolver))

    if settings.ESPAEBOOK_ENABLED:
        registry.register(EspaebookProvider(http_client, resolver))

    if settings.HOLAEBOOK_ENABLED:
        registry.register(HolaEbookProvider(http_client, resolver))

    if settings.ANNASARCHIVE_ENABLED:
        registry.register(AnnasArchiveProvider(http_client, resolver))

    if settings.MEJORTORRENT_ENABLED:
        registry.register(MejorTorrentProvider(http_client, resolver))

    if settings.DONTORRENT_ENABLED:
        registry.register(DonTorrentProvider(http_client, resolver))


def _validate_apikey(apikey: str) -> bool:
    """Valida la API key."""
    return apikey == settings.API_KEY


def _parse_cats(cat_str: str) -> list[int]:
    """Parsea string de categorías a lista de enteros."""
    if not cat_str:
        return []
    return [int(c) for c in cat_str.split(",") if c.isdigit()]


@router.get("/api")
async def torznab_api(
    request: Request,
    t: str = Query("", description="Función: caps|search|tvsearch|movie|book"),
    q: str = Query("", description="Query de búsqueda"),
    cat: str = Query("", description="Categorías (comma-separated)"),
    apikey: str = Query("", description="API Key"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    imdbid: str = Query("", description="IMDb ID (ej: tt1234567)"),
    tvdbid: str = Query("", description="TVDB ID"),
    season: str = Query("", description="Número de temporada"),
    ep: str = Query("", description="Número de episodio"),
    author: str = Query("", description="Autor (book-search)"),
    title: str = Query("", description="Título (book-search)"),
):
    # Validar API key
    if not _validate_apikey(apikey):
        return Response(
            content=TorznabErrors.incorrect_api_key(),
            media_type="application/xml"
        )

    # t=caps → devolver capabilities
    if t and t.lower() == "caps":
        capabilities = [p.get_capabilities() for p in registry.get_all()]
        xml = CapsGenerator.generate(capabilities)
        return Response(content=xml, media_type="application/xml")

    # Routing: determinar qué providers usar
    params = dict(request.query_params)
    providers = await smart_router.route(params)

    if not providers:
        return Response(
            content=TorznabMapper.results_to_xml([], offset, 0),
            media_type="application/xml"
        )

    # Ejecutar búsqueda en todos los providers seleccionados en paralelo
    tasks = [
        provider.search(
            query=q,
            categories=_parse_cats(cat),
            offset=offset,
            limit=limit,
            imdb_id=imdbid or None,
            tvdb_id=int(tvdbid) if tvdbid and tvdbid.isdigit() else None,
            season=int(season) if season and season.isdigit() else None,
            episode=int(ep) if ep and ep.isdigit() else None,
            author=author or None,
            title=title or None,
        )
        for provider in providers
    ]

    results_lists = await asyncio.gather(*tasks, return_exceptions=True)

    # Merge de resultados, ignorando errores
    all_results = []
    for result in results_lists:
        if isinstance(result, list):
            all_results.extend(result)
        elif isinstance(result, Exception):
            logging.error(f"Provider error: {result}")

    # Aplicar paginación
    total = len(all_results)
    paginated = all_results[offset:offset + limit]

    xml = TorznabMapper.results_to_xml(paginated, offset, total)
    return Response(content=xml, media_type="application/xml")


@router.get("/api/download")
async def download_proxy(
    provider: str = Query(..., description="ID del provider"),
    id: str = Query(..., description="ID interno del contenido"),
    fmt: str = Query("epub", description="Formato del archivo"),
):
    """
    Proxy de descarga. Los *Arr llaman a este endpoint cuando
    el usuario selecciona un resultado.
    """
    try:
        prov = registry.get(provider)
        
        # Retrocompatibilidad con providers antiguos que esperaban id/fmt
        internal_id = id if provider != "ebookelo" else f"{id}/{fmt}"

        final_url = await prov.get_download_url(internal_id, fmt=fmt)

        if not final_url:
            raise Exception("No URL found")

        # Descargar el archivo. Usar scraper en caso de Anna's o webs bloqueadas
        http_client = _get_http_client()
        file_bytes = await http_client.download_file(final_url, use_scraper=getattr(prov, 'is_zipped', False) or provider == "annasarchive")

        # Extracción on-the-fly si el provider devuelve ZIPs pero queremos el EPUB
        if getattr(prov, 'is_zipped', False):
            extracted = ZipExtractor.extract_epub_from_memory(file_bytes)
            if extracted:
                file_bytes = extracted
                fmt = "epub"

        content_types = {
            "epub": "application/epub+zip",
            "mobi": "application/x-mobipocket-ebook",
            "pdf": "application/pdf",
            "torrent": "application/x-bittorrent",
        }

        return Response(
            content=file_bytes,
            media_type=content_types.get(fmt, "application/octet-stream"),
            headers={
                "Content-Disposition": f'attachment; filename="download.{fmt}"'
            }
        )
    except Exception as e:
        logging.error(f"Error en descarga: {e}")
        return Response(
            content=TorznabErrors.server_error(str(e)),
            media_type="application/xml"
        )
