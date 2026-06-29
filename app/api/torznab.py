"""
Endpoint principal Torznab.
Compatibile con el estándar Newznab/Torznab para *Arr apps.

URL que se configura en Sonarr/Radarr/Readarr:
  http://localhost:9117/api?apikey=tu_api_key

Para usar providers individuales (multi-indexer):
  http://localhost:9117/api/epublibre?apikey=tu_api_key
  http://localhost:9117/api/lectulandia?apikey=tu_api_key
  ...

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
# New providers
from app.providers.books.epubflix1 import Epubflix1Provider
from app.providers.books.libgen import LibgenProvider
from app.providers.books.booobook import BooobookProvider
from app.providers.books.lectuepublibre5 import LectuEpubLibre5Provider
from app.providers.books.mundoepublibre1 import MundoEpubLibre1Provider
from app.providers.books.zlibrary import ZLibraryProvider
# Integration plan — new book providers
from app.providers.books.lelibros import LeLibrosProvider
from app.providers.books.bajaebooks import BajaebooksProvider
from app.providers.books.ebiblioteca import EbibliotecaProvider
from app.providers.books.epubgratis import EpubgratisProvider
# Integration plan — new video/torrent providers
from app.providers.video.divxtotal import DivxtotalProvider
from app.providers.video.elitetorrent import EliteTorrentProvider
from app.routing.smart_router import smart_router
from app.utils.zip_extractor import ZipExtractor
from app.utils.torrent_generator import generate_torrent
from app.torznab.mapper import TorznabMapper
from app.torznab.caps import CapsGenerator
from app.torznab.errors import TorznabErrors
from app.scraping.http_client import HttpClient
from app.core.categories import CategoryMapper
from app.services.cache import search_cache

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
            proxy=settings.HTTP_PROXY or None,
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

    # --- New providers ---
    if settings.EPUBFLIX1_ENABLED:
        registry.register(Epubflix1Provider(http_client, resolver))

    if settings.LIBGEN_ENABLED:
        registry.register(LibgenProvider(http_client, resolver))

    if settings.BOOOBOOK_ENABLED:
        registry.register(BooobookProvider(http_client, resolver))

    if settings.LECTUEPUBLIBRE5_ENABLED:
        registry.register(LectuEpubLibre5Provider(http_client, resolver))

    if settings.MUNDOEPUBLIBRE1_ENABLED:
        registry.register(MundoEpubLibre1Provider(http_client, resolver))

    if settings.ZLIBRARY_ENABLED:
        registry.register(ZLibraryProvider(http_client, resolver))

    # --- Integration plan — new book providers ---
    if settings.LELIBROS_ENABLED:
        registry.register(LeLibrosProvider(http_client, resolver))

    if settings.BAJAEEBOOKS_ENABLED:
        registry.register(BajaebooksProvider(http_client, resolver))

    if settings.EBIBLIOTECA_ENABLED:
        registry.register(EbibliotecaProvider(http_client, resolver))

    if settings.EPUBGRATIS_ENABLED:
        registry.register(EpubgratisProvider(http_client, resolver))

    # --- Integration plan — new video/torrent providers ---
    if settings.DIVXTOTAL_ENABLED:
        registry.register(DivxtotalProvider(http_client, resolver))

    if settings.ELITETORRENT_ENABLED:
        registry.register(EliteTorrentProvider(http_client, resolver))

    # Providers configurados pero no implementados aún
    if settings.ELEJANDRIA_ENABLED:
        logging.warning("Elejandria provider is configured as enabled but not yet implemented")
    if settings.GUTENBERG_ENABLED:
        logging.warning("Gutenberg provider is configured as enabled but not yet implemented")


def _validate_apikey(apikey: str) -> bool:
    """Valida la API key."""
    return apikey == settings.API_KEY


def _parse_cats(cat_str: str) -> list[int]:
    """Parsea string de categorías a lista de enteros."""
    if not cat_str:
        return []
    return [int(c) for c in cat_str.split(",") if c.isdigit()]


async def _handle_torznab_request(
    providers: list,
    params: dict,
    q: str = "",
    cat: str = "",
    offset: int = 0,
    limit: int = 50,
    imdbid: str = "",
    tvdbid: str = "",
    season: str = "",
    ep: str = "",
    author: str = "",
    title: str = "",
) -> Response:
    """
    Núcleo compartido de la lógica Torznab.
    Busca en la lista de providers dada y devuelve el XML de respuesta.

    Usado por:
      - /api   (todos los providers)
      - /api/{provider_id}  (un solo provider)
    """
    # Ejecutar búsqueda en todos los providers seleccionados en paralelo
    # con un timeout global para evitar que un provider lento bloquee todo
    SEARCH_TIMEOUT_SECONDS = 45
    parsed_cats = _parse_cats(cat)

    async def search_with_cache(provider, **kw):
        """Busca con cache intermedio y timeout."""
        # Intentar cache primero
        cached = search_cache.get(provider.provider_id, q, parsed_cats)
        if cached is not None:
            logging.debug(f"Cache hit for {provider.provider_id} / '{q}'")
            return cached

        try:
            results = await asyncio.wait_for(
                provider.search(**kw),
                timeout=SEARCH_TIMEOUT_SECONDS,
            )
            # Guardar en cache
            if isinstance(results, list):
                search_cache.set(provider.provider_id, q, results, parsed_cats)
            return results
        except asyncio.TimeoutError:
            logging.warning(f"Provider {provider.provider_id} timed out after {SEARCH_TIMEOUT_SECONDS}s")
            return []
        except Exception as e:
            logging.error(f"Provider {provider.provider_id} error: {e}")
            return []

    # Determinar si es una búsqueda real o un RSS sync sin query.
    # Readarr envía t=book sin q= para sincronización periódica (RSS feed).
    # En ese caso usamos browse() para devolver listados recientes en lugar
    # de search() que requiere query.
    has_query = bool(q and q.strip()) or bool(author and author.strip()) or bool(title and title.strip())

    if has_query:
        tasks = [
            search_with_cache(
                provider,
                query=q,
                categories=parsed_cats,
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
    else:
        # RSS sync mode: browse recent listings from each provider
        logging.info(f"RSS sync — browsing recent listings from {len(providers)} providers")

        async def browse_provider(provider):
            try:
                return await asyncio.wait_for(
                    provider.browse(
                        categories=parsed_cats,
                        offset=offset,
                        limit=limit,
                    ),
                    timeout=SEARCH_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                logging.warning(f"Provider {provider.provider_id} browse timed out")
                return []
            except Exception as e:
                logging.error(f"Provider {provider.provider_id} browse error: {e}")
                return []

        tasks = [browse_provider(provider) for provider in providers]

    results_lists = await asyncio.gather(*tasks)

    # Merge de resultados con logging de diagnóstico
    all_results = []
    provider_stats = {}
    for i, result_list in enumerate(results_lists):
        provider_id = providers[i].provider_id if i < len(providers) else "unknown"
        if isinstance(result_list, list):
            count = len(result_list)
            all_results.extend(result_list)
            provider_stats[provider_id] = count
        else:
            provider_stats[provider_id] = "error (non-list)"

    # Log diagnóstico: cuántos resultados devolvió cada provider
    if all_results:
        logging.info(
            f"Search '{q}' → {len(all_results)} total results from "
            f"{sum(1 for v in provider_stats.values() if isinstance(v, int) and v > 0)}/"
            f"{len(providers)} providers: {provider_stats}"
        )
    else:
        logging.warning(
            f"Search '{q}' → 0 results. All {len(providers)} providers returned empty: {provider_stats}"
        )

    # Aplicar paginación
    total_before_filter = len(all_results)

    # Filtrar resultados por categorías solicitadas (server-side).
    # Readarr filtra client-side, pero un filtro server-side evita que
    # resultados de categorías no solicitadas (ej: video en búsqueda de
    # libros) contaminen la respuesta y causen "no results in configured
    # categories" en el lado del cliente.
    if parsed_cats:
        filtered = []
        filtered_out = []
        for r in all_results:
            if any(
                c in parsed_cats or (c // 1000 * 1000) in parsed_cats
                for c in r.categories
            ):
                filtered.append(r)
            else:
                filtered_out.append(r)
        if filtered_out:
            logging.debug(
                f"Category filter: removed {len(filtered_out)} results "
                f"(categories {set(c for r in filtered_out for c in r.categories)} "
                f"not in requested {parsed_cats})"
            )
        all_results = filtered

    total = len(all_results)
    paginated = all_results[offset:offset + limit]

    xml = TorznabMapper.results_to_xml(paginated, offset, total)
    return Response(content=xml, media_type="application/xml")


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------


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
    """
    Endpoint Torznab principal.
    Busca en TODOS los providers registrados (comportamiento original).

    También responde a t=caps con las capabilities agregadas de todos los providers.
    """
    # Validar API key
    if not _validate_apikey(apikey):
        # t=caps sin API key: devolver caps básicas para permitir
        # que las *Arr apps detecten el servicio (como hace Jackett)
        if t and t.lower() == "caps":
            capabilities = [p.get_capabilities() for p in registry.get_all()]
            xml = CapsGenerator.generate(capabilities)
            return Response(content=xml, media_type="application/xml")
        
        error_xml = TorznabErrors.incorrect_api_key()
        error_headers = TorznabErrors.error_headers(
            TorznabErrors.INCORRECT_API_KEY, "Incorrect API Key"
        )
        return Response(
            content=error_xml,
            media_type="application/xml",
            headers=error_headers,
        )

    # t=caps → devolver capabilities agregadas de todos los providers
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

    return await _handle_torznab_request(
        providers=providers,
        params=params,
        q=q,
        cat=cat,
        offset=offset,
        limit=limit,
        imdbid=imdbid,
        tvdbid=tvdbid,
        season=season,
        ep=ep,
        author=author,
        title=title,
    )


@router.get("/api/download")
async def download_proxy(
    provider: str = Query(..., description="ID del provider"),
    id: str = Query(..., description="ID interno del contenido"),
    fmt: str = Query("epub", description="Formato del archivo"),
):
    """
    Proxy de descarga. Los *Arr llaman a este endpoint cuando
    el usuario selecciona un resultado.

    Para book providers (no-video), genera un archivo .torrent
    on-the-fly que envuelve el EPUB/PDF/MOBI con un web seed.
    Readarr espera siempre un archivo .torrent válido de los
    indexers Torznab y falla si recibe otro tipo de archivo.
    """
    try:
        prov = registry.get(provider)

        caps = prov.get_capabilities()
        is_video = caps.supports_movie_search or caps.supports_tv_search

        internal_id = id if provider != "ebookelo" else f"{id}/{fmt}"

        final_url = await prov.get_download_url(internal_id, fmt=fmt)

        if not final_url:
            raise Exception("No URL found")

        http_client = _get_http_client()
        file_bytes = await http_client.download_file(final_url, use_scraper=getattr(prov, 'is_zipped', False) or provider == "annasarchive")

        if getattr(prov, 'is_zipped', False):
            extracted = ZipExtractor.extract_epub_from_memory(file_bytes)
            if extracted:
                file_bytes = extracted
                fmt = "epub"

        if is_video:
            return Response(
                content=file_bytes,
                media_type="application/x-bittorrent",
                headers={
                    "Content-Disposition": 'attachment; filename="download.torrent"'
                }
            )

        ext = fmt if fmt in ("epub", "mobi", "pdf") else "epub"
        file_name = f"{prov.display_name}_{id}.{ext}"

        web_seed_url = (
            f"{settings.EXTERNAL_URL.rstrip('/')}/api/download-content"
            f"?provider={provider}&id={id}&fmt={fmt}"
        )

        torrent_bytes, info_hash, magnet_uri = generate_torrent(
            file_name=file_name,
            file_data=file_bytes,
            web_seed_url=web_seed_url,
            comment=f"WebTranslatorr book download: {prov.display_name}",
        )

        return Response(
            content=torrent_bytes,
            media_type="application/x-bittorrent",
            headers={
                "Content-Disposition": f'attachment; filename="{file_name}.torrent"'
            }
        )
    except Exception as e:
        logging.error(f"Error en descarga: {e}")
        return Response(
            content=TorznabErrors.server_error(str(e)),
            media_type="application/xml"
        )


@router.get("/api/download-content")
async def download_content(
    provider: str = Query(..., description="ID del provider"),
    id: str = Query(..., description="ID interno del contenido"),
    fmt: str = Query("epub", description="Formato del archivo"),
):
    """
    Endpoint interno para el web seed del torrent.
    Devuelve el contenido real (EPUB/PDF/MOBI) para que
    el cliente torrent lo descargue via web seed.
    """
    try:
        prov = registry.get(provider)

        internal_id = id if provider != "ebookelo" else f"{id}/{fmt}"

        final_url = await prov.get_download_url(internal_id, fmt=fmt)

        if not final_url:
            raise Exception("No URL found")

        http_client = _get_http_client()
        file_bytes = await http_client.download_file(final_url, use_scraper=getattr(prov, 'is_zipped', False) or provider == "annasarchive")

        if getattr(prov, 'is_zipped', False):
            extracted = ZipExtractor.extract_epub_from_memory(file_bytes)
            if extracted:
                file_bytes = extracted
                fmt = "epub"

        content_types = {
            "epub": "application/epub+zip",
            "mobi": "application/x-mobipocket-ebook",
            "pdf": "application/pdf",
        }

        ext = fmt if fmt in ("epub", "mobi", "pdf") else "epub"

        return Response(
            content=file_bytes,
            media_type=content_types.get(fmt, "application/octet-stream"),
            headers={
                "Content-Disposition": f'attachment; filename="download.{ext}"'
            }
        )
    except Exception as e:
        logging.error(f"Error en descarga de contenido: {e}")
        return Response(
            content=TorznabErrors.server_error(str(e)),
            media_type="application/xml"
        )


@router.get("/api/{provider_id}")
async def provider_torznab_api(
    provider_id: str,
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
    """
    Endpoint Torznab para un UNICO provider.
    Permite configurar indexers individuales en Readarr/Radarr/Sonarr.

    Ejemplo de URL en Readarr:
      http://webtranslatorr:9811/api/epublibre?apikey=xxx
      http://webtranslatorr:9811/api/lectulandia?apikey=xxx
      http://webtranslatorr:9811/api/libgen?apikey=xxx
    """
    provider_id_lower = provider_id.lower()

    # Validar API key
    if not _validate_apikey(apikey):
        # t=caps sin API key: permitir detección del servicio
        if t and t.lower() == "caps":
            try:
                provider = registry.get(provider_id_lower)
                caps = provider.get_capabilities()
                server_url = settings.EXTERNAL_URL.rstrip("/") + f"/api/{provider_id_lower}"
                xml = CapsGenerator.generate(
                    [caps],
                    server_title=f"WebTranslatorr - {caps.display_name}",
                    server_url=server_url,
                )
                return Response(content=xml, media_type="application/xml")
            except Exception:
                pass
        
        error_xml = TorznabErrors.incorrect_api_key()
        error_headers = TorznabErrors.error_headers(
            TorznabErrors.INCORRECT_API_KEY, "Incorrect API Key"
        )
        return Response(
            content=error_xml,
            media_type="application/xml",
            headers=error_headers,
        )

    # Obtener el provider específico
    try:
        provider = registry.get(provider_id_lower)
    except Exception:
        return Response(
            content=TorznabErrors.server_error(f"Provider '{provider_id}' not found"),
            media_type="application/xml"
        )

    # t=caps → devolver capabilities de este provider individual,
    # con título y URL personalizados para que Readarr lo muestre
    # como un indexer independiente con su nombre real
    if t and t.lower() == "caps":
        caps = provider.get_capabilities()
        server_url = settings.EXTERNAL_URL.rstrip("/") + f"/api/{provider_id_lower}"
        xml = CapsGenerator.generate(
            [caps],
            server_title=f"WebTranslatorr - {caps.display_name}",
            server_url=server_url,
        )
        return Response(content=xml, media_type="application/xml")

    params = dict(request.query_params)

    return await _handle_torznab_request(
        providers=[provider],
        params=params,
        q=q,
        cat=cat,
        offset=offset,
        limit=limit,
        imdbid=imdbid,
        tvdbid=tvdbid,
        season=season,
        ep=ep,
        author=author,
        title=title,
    )


