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
import re

from fastapi import APIRouter, Query, Request, Response

from config import settings
from app.api.auth import validate_apikey
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
from app.core.exceptions import DownloadTooLargeError
from app.services.cache import search_cache
from app.services.download_tokens import (
    build_download_content_url,
    verify_download,
)

router = APIRouter()


def _init_providers(resolver=None, http_client: HttpClient | None = None):
    """Inicializa los providers según configuración."""
    if http_client is None:
        raise ValueError("http_client is required for provider initialization")

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


def _parse_cats(cat_str: str) -> list[int]:
    """Parsea string de categorías a lista de enteros."""
    if not cat_str:
        return []
    return [int(c) for c in cat_str.split(",") if c.isdigit()]


# ---- Request-scoped translation cache ----
# WebTranslatorr creates one provider-specific HTTP call per provider
# per Readarr request, but each call re-executes the full translation
# pipeline.  This dict deduplicates translation lookups within a short
# time window (5 s) so that N providers for the same query only trigger
# one Wikidata/GoogleBooks cascade.
import time as _time
_translation_request_cache: dict[str, tuple[float, str | None]] = {}
_TRANSLATION_CACHE_TTL = 5.0


def _cached_translate(
    translation_title: str, translation_author: str | None
) -> str | None:
    """Return cached translation or None. Cleans expired entries."""
    now = _time.monotonic()
    key = f"{translation_title}\x00{translation_author or ''}"
    if key in _translation_request_cache:
        ts, result = _translation_request_cache[key]
        if now - ts < _TRANSLATION_CACHE_TTL:
            return result
        del _translation_request_cache[key]
    expired = [k for k, (t, _) in _translation_request_cache.items() if now - t >= _TRANSLATION_CACHE_TTL]
    for k in expired:
        del _translation_request_cache[k]
    return None


def _set_cached_translate(
    translation_title: str, translation_author: str | None, result: str | None
) -> None:
    key = f"{translation_title}\x00{translation_author or ''}"
    _translation_request_cache[key] = (_time.monotonic(), result)


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
        cache_query = kw.get("query", q)
        cache_offset = kw.get("offset", offset)
        cache_limit = kw.get("limit", limit)
        cached = await search_cache.get(
            provider.provider_id,
            cache_query,
            parsed_cats,
            cache_offset,
            cache_limit,
        )
        if cached is not None:
            logging.debug(f"Cache hit for {provider.provider_id} / '{cache_query}'")
            return cached

        try:
            # Important: wrap provider.search() in a Task before passing
            # it to `asyncio.wait_for`. Tests monkeypatch `asyncio.wait_for`
            # and raise without awaiting the awaitable argument; if we pass
            # the raw coroutine, it can leak as "coroutine was never
            # awaited". Using a Task ensures it is always scheduled and
            # can be cancelled deterministically.
            search_task = asyncio.create_task(provider.search(**kw))
            try:
                results = await asyncio.wait_for(
                    search_task,
                    timeout=SEARCH_TIMEOUT_SECONDS,
                )
            finally:
                if not search_task.done():
                    search_task.cancel()
                    # Ensure cancellation completes (avoid "task was destroyed")
                    await asyncio.gather(search_task, return_exceptions=True)
            if isinstance(results, list):
                await search_cache.set(
                    provider.provider_id,
                    cache_query,
                    results,
                    parsed_cats,
                    cache_offset,
                    cache_limit,
                )
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

    # ---- Translation Pipeline integration (Phase 8) ----
    from app.services.translation_pipeline import get_translation_pipeline

    effective_q = q
    # Determine the English title for translation.
    # Readarr sends t=book with separate author=/title= params (no q=),
    # and t=search with q= combining title+author but no author=/title=.
    translation_title = (q or title or "").strip()
    translation_author = (author or "").strip() or None

    is_generic_search = len(parsed_cats) == 0 and not imdbid and not tvdbid
    is_book_search = any(7000 <= c <= 8999 for c in parsed_cats)

    if translation_title and (is_book_search or is_generic_search):
        cached = _cached_translate(translation_title, translation_author)
        if cached is not None:
            if cached:
                effective_q = cached
                logging.debug(
                    "Translation (cached): '%s' -> '%s'",
                    translation_title, effective_q,
                )
        else:
            try:
                translation_pipeline = await get_translation_pipeline()
                if translation_pipeline is not None:
                    result = await translation_pipeline.translate(translation_title, translation_author)
                    if result is not None:
                        translated = result.title_es
                        tl_lower = translated.lower()
                        tt_lower = translation_title.lower()
                        author_lower = (translation_author or "").lower()
                        if tl_lower == tt_lower:
                            logging.debug(
                                "Translation '%s' unchanged, using original query",
                                translated,
                            )
                            _set_cached_translate(translation_title, translation_author, None)
                        elif author_lower and tl_lower == author_lower:
                            logging.debug(
                                "Translation '%s' is the author name, using original query",
                                translated,
                            )
                            _set_cached_translate(translation_title, translation_author, None)
                        elif (
                            result.confidence < 0.8
                            and author_lower
                            and author_lower in tl_lower
                        ):
                            logging.debug(
                                "Translation '%s' looks like a collection (contains author name), using original query",
                                translated,
                            )
                            _set_cached_translate(translation_title, translation_author, None)
                        else:
                            effective_q = translated
                            logging.info(
                                f"Translation: '%s' -> '%s' (source=%s, confidence=%s)",
                                translation_title, effective_q, result.source, result.confidence
                            )
                            _set_cached_translate(translation_title, translation_author, effective_q)
                    else:
                        _set_cached_translate(translation_title, translation_author, None)
            except Exception as e:
                _set_cached_translate(translation_title, translation_author, None)
                logging.warning(f"Translation pipeline error (using original query): {e}")

    has_query = bool(q and q.strip()) or bool(author and author.strip()) or bool(title and title.strip())

    if has_query:
        tasks = [
            search_with_cache(
                provider,
                query=effective_q,
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
                browse_task = asyncio.create_task(
                    provider.browse(
                        categories=parsed_cats,
                        offset=offset,
                        limit=limit,
                    )
                )
                try:
                    return await asyncio.wait_for(
                        browse_task,
                        timeout=SEARCH_TIMEOUT_SECONDS,
                    )
                finally:
                    if not browse_task.done():
                        browse_task.cancel()
                        await asyncio.gather(browse_task, return_exceptions=True)
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
            f"Search '{effective_q}' → {len(all_results)} total results from "
            f"{sum(1 for v in provider_stats.values() if isinstance(v, int) and v > 0)}/"
            f"{len(providers)} providers: {provider_stats}"
        )
    else:
        logging.warning(
            f"Search '{effective_q}' → 0 results. All {len(providers)} providers returned empty: {provider_stats}"
        )
        # Log individual provider failures for diagnostics
        empty_providers = [pid for pid, count in provider_stats.items() if isinstance(count, int) and count == 0]
        if empty_providers:
            logging.warning(f"Providers returning 0 results: {', '.join(empty_providers)}")

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
    if not validate_apikey(apikey):
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
    request: Request,
    provider: str = Query(..., description="ID del provider"),
    id: str = Query(..., description="ID interno del contenido"),
    fmt: str = Query("epub", description="Formato del archivo"),
    apikey: str = Query("", description="API Key"),
):
    """
    Proxy de descarga. Los *Arr llaman a este endpoint cuando
    el usuario selecciona un resultado.

    Para book providers (no-video), genera un archivo .torrent
    on-the-fly que envuelve el EPUB/PDF/MOBI con un web seed.
    Readarr espera siempre un archivo .torrent válido de los
    indexers Torznab y falla si recibe otro tipo de archivo.
    """
    if not validate_apikey(apikey):
        return Response(
            content=TorznabErrors.incorrect_api_key(),
            media_type="application/xml",
            headers=TorznabErrors.error_headers(
                TorznabErrors.INCORRECT_API_KEY, "Incorrect API Key"
            ),
        )

    safe_id = re.sub(r'[^\w.\-]', '_', id)
    safe_fmt = re.sub(r'[^\w.\-]', '_', fmt)

    try:
        prov = registry.get(provider)

        caps = prov.get_capabilities()
        is_video = caps.supports_movie_search or caps.supports_tv_search

        final_url = await prov.get_download_url(id, fmt=fmt)

        if not final_url:
            raise Exception("No URL found")

        http_client: HttpClient = request.app.state.http_client
        max_bytes = (
            settings.MAX_VIDEO_DOWNLOAD_BYTES
            if is_video
            else settings.MAX_DOWNLOAD_BYTES
        )
        file_bytes = await http_client.download_file(
            final_url,
            max_bytes=max_bytes,
            use_scraper=getattr(prov, 'is_zipped', False) or provider == "annasarchive",
        )

        if getattr(prov, 'is_zipped', False):
            extracted = ZipExtractor.extract_epub_from_memory(file_bytes)
            if extracted:
                file_bytes = extracted
                safe_fmt = "epub"

        if is_video:
            return Response(
                content=file_bytes,
                media_type="application/x-bittorrent",
                headers={
                    "Content-Disposition": 'attachment; filename="download.torrent"'
                }
            )

        ext = safe_fmt if safe_fmt in ("epub", "mobi", "pdf") else "epub"
        file_name = f"{prov.display_name}_{safe_id}.{ext}"

        web_seed_url = build_download_content_url(provider, id, fmt)

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
    except DownloadTooLargeError as e:
        logging.error(f"Download too large: {e}")
        return Response(
            content=TorznabErrors.server_error("Download failed"),
            media_type="application/xml"
        )
    except Exception as e:
        logging.error(f"Error en descarga: {e}")
        return Response(
            content=TorznabErrors.server_error("Download failed"),
            media_type="application/xml"
        )


@router.get("/api/download-content")
async def download_content(
    request: Request,
    provider: str = Query(..., description="ID del provider"),
    id: str = Query(..., description="ID interno del contenido"),
    fmt: str = Query("epub", description="Formato del archivo"),
    token: str = Query("", description="Signed download token"),
):
    """
    Endpoint interno para el web seed del torrent.
    Devuelve el contenido real (EPUB/PDF/MOBI) para que
    el cliente torrent lo descargue via web seed.
    """
    if not verify_download(token, provider, id, fmt):
        return Response(
            content=TorznabErrors.incorrect_api_key(),
            media_type="application/xml",
            headers=TorznabErrors.error_headers(
                TorznabErrors.INCORRECT_API_KEY, "Invalid or expired download token"
            ),
        )

    safe_fmt = re.sub(r'[^\w.\-]', '_', fmt)

    try:
        prov = registry.get(provider)

        final_url = await prov.get_download_url(id, fmt=fmt)

        if not final_url:
            raise Exception("No URL found")

        http_client: HttpClient = request.app.state.http_client
        file_bytes = await http_client.download_file(
            final_url,
            use_scraper=getattr(prov, 'is_zipped', False) or provider == "annasarchive",
        )

        if getattr(prov, 'is_zipped', False):
            extracted = ZipExtractor.extract_epub_from_memory(file_bytes)
            if extracted:
                file_bytes = extracted
                safe_fmt = "epub"

        content_types = {
            "epub": "application/epub+zip",
            "mobi": "application/x-mobipocket-ebook",
            "pdf": "application/pdf",
        }

        ext = safe_fmt if safe_fmt in ("epub", "mobi", "pdf") else "epub"

        return Response(
            content=file_bytes,
            media_type=content_types.get(fmt, "application/octet-stream"),
            headers={
                "Content-Disposition": f'attachment; filename="download.{ext}"'
            }
        )
    except DownloadTooLargeError as e:
        logging.error(f"Download too large: {e}")
        return Response(
            content=TorznabErrors.server_error("Download failed"),
            media_type="application/xml"
        )
    except Exception as e:
        logging.error(f"Error en descarga de contenido: {e}")
        return Response(
            content=TorznabErrors.server_error("Download failed"),
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
    if not validate_apikey(apikey):
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


