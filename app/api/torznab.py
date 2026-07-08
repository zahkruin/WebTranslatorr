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
# Plan 003 — new book providers
from app.providers.books.booksee import BookseeProvider
from app.providers.books.oceanofpdf import OceanOfPDFProvider
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

# In-memory download cache — avoids downloading the same file twice
# (once for torrent generation, once for webseed delivery).
# Key: "provider\x00id\x00fmt", Value: bytes
# TTL: 10 minutes, cleaned on access.
_download_cache: dict[str, tuple[float, bytes]] = {}
_download_cache_lock = asyncio.Lock()
_DOWNLOAD_CACHE_TTL = 600  # seconds

# Provider registry: maps provider_id → Provider class
_PROVIDER_CLASSES: dict[str, type] = {
    "ebookelo": EbookeloProvider,
    "epublibre": EpubLibreProvider,
    "lectulandia": LectulandiaProvider,
    "espaebook": EspaebookProvider,
    "holaebook": HolaEbookProvider,
    "annasarchive": AnnasArchiveProvider,
    "mejortorrent": MejorTorrentProvider,
    "dontorrent": DonTorrentProvider,
    "epubflix1": Epubflix1Provider,
    "libgen": LibgenProvider,
    "booobook": BooobookProvider,
    "lectuepublibre5": LectuEpubLibre5Provider,
    "mundoepublibre1": MundoEpubLibre1Provider,
    "zlibrary": ZLibraryProvider,
    "lelibros": LeLibrosProvider,
    "bajaebooks": BajaebooksProvider,
    "ebiblioteca": EbibliotecaProvider,
    "epubgratis": EpubgratisProvider,
    "divxtotal": DivxtotalProvider,
    "elitetorrent": EliteTorrentProvider,
    "booksee": BookseeProvider,
    "oceanofpdf": OceanOfPDFProvider,
}

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


def _init_providers_from_env(resolver=None):
    """Inicializa los providers según variables de entorno (fallback sin DB)."""
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

    # --- Plan 003 — new book providers ---
    if settings.BOOKSEE_ENABLED:
        registry.register(BookseeProvider(http_client, resolver))

    if settings.OCEANOFPDF_ENABLED:
        registry.register(OceanOfPDFProvider(http_client, resolver))

    # Providers configurados pero no implementados aún
    if settings.ELEJANDRIA_ENABLED:
        logging.warning("Elejandria provider is configured as enabled but not yet implemented")
    if settings.GUTENBERG_ENABLED:
        logging.warning("Gutenberg provider is configured as enabled but not yet implemented")


async def _init_providers(resolver=None, config_manager=None):
    """Inicializa los providers según configuración en base de datos."""
    http_client = _get_http_client()
    registry.clear()

    if config_manager is None:
        # Fallback: si no hay ConfigManager, usar env vars directamente
        # (compatibilidad con tests que no tienen DB)
        from config import settings
        _init_providers_from_env(resolver)
        return

    # Leer providers habilitados desde la DB
    providers = await config_manager.get_all_enabled_providers()

    for p in providers:
        provider_id = p["provider_id"]
        provider_cls = _PROVIDER_CLASSES.get(provider_id)
        if provider_cls is not None:
            if resolver and p.get("domain"):
                # Actualizar dominio del resolver si el provider tiene dominio en DB
                pass  # DomainResolver se maneja en server.py
            registry.register(provider_cls(http_client, resolver))
            logging.info(f"Provider {provider_id} registered from DB config")
        else:
            logging.warning(f"Unknown provider_id '{provider_id}' in DB — no class mapping")


async def _validate_apikey(apikey: str, config_manager=None) -> bool:
    """Valida la API key contra la DB o env vars."""
    if config_manager is not None:
        return await config_manager.validate_api_key(apikey)
    # Fallback: usar env var
    from config import settings
    return apikey == settings.API_KEY


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
from app.services.cache import normalize_query_key

_translation_request_cache: dict[str, tuple[float, str | None]] = {}
_TRANSLATION_CACHE_TTL = 5.0


def _cached_translate(
    translation_title: str, translation_author: str | None
) -> str | None:
    """Return cached translation or None. Cleans expired entries."""
    now = _time.monotonic()
    key = f"{normalize_query_key(translation_title)}\x00{normalize_query_key(translation_author or '')}"
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
    key = f"{normalize_query_key(translation_title)}\x00{normalize_query_key(translation_author or '')}"
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
    lang: str = "",
    server_url: str = "",
) -> Response:
    """
    Núcleo compartido de la lógica Torznab.
    Busca en la lista de providers dada y devuelve el XML de respuesta.

    Usado por:
      - /api   (todos los providers)
      - /api/{provider_id}  (un solo provider)

    Parámetros:
        server_url: URL pública del servidor (scheme + host) derivada del
                    request entrante.  Se usa para reescribir los enlaces
                    de descarga para que apunten al host correcto en lugar
                    de ``settings.EXTERNAL_URL`` (que puede ser localhost).
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

    # ---- Translation Pipeline integration (Phase 8) ----
    from app.services.translation_pipeline import get_translation_pipeline
    from app.core.languages import resolve_language

    # Resolve target language for translation lookups.
    # Priority: 1) explicit ?lang= param, 2) default from config.
    from app.core.languages import SUPPORTED_LANGUAGES

    _search_lang = resolve_language(lang or settings.DEFAULT_SEARCH_LANGUAGE)
    if lang and lang.strip().lower() not in SUPPORTED_LANGUAGES:
        logging.warning(
            "Unsupported language '%s', falling back to '%s'",
            lang, _search_lang.code,
        )
    logging.debug("Search language resolved: %s (%s)", _search_lang.code, _search_lang.display_name)

    effective_q = q
    # Determine the English title for translation.
    # Readarr sends t=book with separate author=/title= params (no q=),
    # and t=search with q= combining title+author but no author=/title=.
    #
    # Prefer the explicit title parameter when available, as it avoids
    # generating unnecessary title variants from combined queries.
    # If only q= is present, strip the author name from the combined
    # query to extract the pure title (reduces variant count).
    _title_param = (title or "").strip()
    _author_param = (author or "").strip()
    if _title_param:
        translation_title = _title_param
    elif q and _author_param:
        # Strip author words from the combined query to isolate the title
        author_words = set(_author_param.lower().split())
        q_words = q.strip().split()
        title_words = [w for w in q_words if w.lower() not in author_words]
        translation_title = " ".join(title_words).strip() or q.strip()
    else:
        translation_title = (q or "").strip()
    translation_author = _author_param or None

    if translation_title and parsed_cats:
        from app.core.categories import CategoryMapper
        is_book_search = any(7000 <= c <= 8999 for c in parsed_cats)
        is_generic_search = len(parsed_cats) == 0 and not imdbid and not tvdbid

        if is_book_search or is_generic_search:
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
                        result = await translation_pipeline.translate(
                            translation_title,
                            translation_author,
                            target_lang=_search_lang,
                        )
                        if result is not None:
                            translated = result.title_es
                            # Validate: skip if same as English input,
                            # if result is just the author name,
                            # or if result contains the author name with
                            # low confidence (likely a collected-works).
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
                results = await asyncio.wait_for(
                    provider.browse(
                        categories=parsed_cats,
                        offset=offset,
                        limit=limit,
                    ),
                    timeout=SEARCH_TIMEOUT_SECONDS,
                )
                # Fallback: if browse() returns empty, try a generic search
                # so that Readarr validation doesn't fail for providers whose
                # browse() doesn't match the homepage structure
                if not results:
                    logging.info(
                        f"Provider {provider.provider_id} browse returned 0 results, "
                        f"falling back to search with default query"
                    )
                    try:
                        results = await asyncio.wait_for(
                            provider.search(
                                query="test",
                                categories=parsed_cats,
                                offset=0,
                                limit=min(limit, 10),
                            ),
                            timeout=SEARCH_TIMEOUT_SECONDS,
                        )
                        if results:
                            logging.info(
                                f"Provider {provider.provider_id} search fallback: "
                                f"{len(results)} results"
                            )
                    except asyncio.TimeoutError:
                        logging.warning(
                            f"Provider {provider.provider_id} search fallback timed out"
                        )
                    except Exception as e:
                        logging.error(
                            f"Provider {provider.provider_id} search fallback error: {e}"
                        )
                return results
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

    # Rewrite download URLs so they point to the actual server address
    # that the client used to reach us, rather than settings.EXTERNAL_URL
    # (which might be http://localhost:9811 and unreachable from other hosts).
    if server_url:
        _rewrite_download_urls(paginated, server_url)

    xml = TorznabMapper.results_to_xml(paginated, offset, total)
    return Response(content=xml, media_type="application/xml")


def _rewrite_download_urls(results: list, server_url: str) -> None:
    """Rewrite ``download_url`` on every result to use *server_url*.

    Providers build download URLs using ``settings.EXTERNAL_URL``, but that
    value may point to ``localhost`` or an internal address.  We replace the
    scheme + host portion of every download URL with the *server_url*
    derived from the incoming request's ``Host`` header so that Readarr
    (or any other client on a different machine) can actually reach us.
    """
    configured = (settings.EXTERNAL_URL or "").rstrip("/")
    target = server_url.rstrip("/")

    # Skip if they already match (nothing to rewrite)
    if not configured or configured == target:
        return

    for r in results:
        if r.download_url and r.download_url.startswith(configured):
            r.download_url = target + r.download_url[len(configured):]


def _server_url_from_request(request: Request) -> str:
    """Derive the public base URL from the incoming request's scheme + Host header."""
    scheme = request.url.scheme or "http"
    host = request.headers.get("host", "")
    return f"{scheme}://{host}"


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
    lang: str = Query("", description="Idioma destino (es, en, fr, de, it, pt)"),
):
    """
    Endpoint Torznab principal.
    Busca en TODOS los providers registrados (comportamiento original).

    También responde a t=caps con las capabilities agregadas de todos los providers.
    """
    # Validar API key
    config_manager = request.app.state.config_manager
    if not await _validate_apikey(apikey, config_manager):
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
        lang=lang,
        server_url=_server_url_from_request(request),
    )


@router.get("/api/download")
async def download_proxy(
    request: Request,
    provider: str = Query(..., description="ID del provider"),
    id: str = Query(..., description="ID interno del contenido"),
    fmt: str = Query("epub", description="Formato del archivo"),
):
    """
    Proxy de descarga. Los *Arr llaman a este endpoint cuando
    el usuario selecciona un resultado.

    Genera un archivo .torrent por cada descarga.  El torrent contiene
    los hashes de pieza reales y un web seed que apunta al archivo.
    Un watcher externo lee el torrent y descarga el EPUB/PDF/MOBI real.
    """
    server_url = _server_url_from_request(request)

    cache_key = f"{provider}\x00{id}\x00{fmt}"
    try:
        prov = registry.get(provider)
        caps = prov.get_capabilities()
        is_video = caps.supports_movie_search or caps.supports_tv_search
        internal_id = id if provider != "ebookelo" else f"{id}/{fmt}"

        final_url = await prov.get_download_url(internal_id, fmt=fmt)
        if not final_url:
            raise Exception("No URL found")

        ext = fmt if fmt in ("epub", "mobi", "pdf") else "epub"

        http_client = _get_http_client()

        async with _download_cache_lock:
            now = _time.monotonic()
            expired = [k for k, (ts, _) in _download_cache.items() if now - ts > _DOWNLOAD_CACHE_TTL]
            for k in expired:
                del _download_cache[k]

            cached_entry = _download_cache.get(cache_key)
            if cached_entry is not None:
                _, file_bytes = cached_entry
            else:
                file_bytes = await http_client.download_file(
                    final_url,
                    use_scraper=getattr(prov, 'is_zipped', False) or provider == "annasarchive",
                )
                if getattr(prov, 'is_zipped', False):
                    extracted = ZipExtractor.extract_epub_from_memory(file_bytes)
                    if extracted:
                        file_bytes = extracted
                        fmt = "epub"
                _download_cache[cache_key] = (_time.monotonic(), file_bytes)

        if is_video:
            return Response(
                content=file_bytes,
                media_type="application/x-bittorrent",
                headers={"Content-Disposition": 'attachment; filename="download.torrent"'}
            )

        file_name = f"{prov.display_name}_{id}.{ext}"
        web_seed_url = (
            f"{server_url.rstrip('/')}/api/download-content"
            f"?provider={provider}&id={id}&fmt={fmt}"
        )

        torrent_bytes, info_hash, magnet_uri = generate_torrent(
            file_name=file_name,
            file_data=file_bytes,
            announce_url="udp://tracker.opentrackr.org:1337/announce",
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
    request: Request,
    provider: str = Query(..., description="ID del provider"),
    id: str = Query(..., description="ID interno del contenido"),
    fmt: str = Query("epub", description="Formato del archivo"),
):
    """
    Endpoint interno para el web seed del torrent.
    Devuelve el contenido real (EPUB/PDF/MOBI) para que
    el cliente torrent lo descargue via web seed.

    Soporta HTTP Range requests (necesario para qBittorrent/libtorrent).

    Si el archivo fue cacheado por :func:`download_proxy`, se
    sirve desde la caché para evitar una segunda descarga.
    """
    cache_key = f"{provider}\x00{id}\x00{fmt}"
    range_header = request.headers.get("range", "")
    logging.info(
        "download-content request: provider=%s id=%s client=%s range=%s",
        provider, id, request.client.host if request.client else "?",
        range_header[:80] if range_header else "none",
    )

    async def _get_file_bytes() -> bytes:
        prov = registry.get(provider)
        internal_id = id if provider != "ebookelo" else f"{id}/{fmt}"
        final_url = await prov.get_download_url(internal_id, fmt=fmt)
        if not final_url:
            raise Exception("No URL found")
        http_client = _get_http_client()
        data = await http_client.download_file(
            final_url,
            use_scraper=getattr(prov, 'is_zipped', False) or provider == "annasarchive",
        )
        if getattr(prov, 'is_zipped', False):
            extracted = ZipExtractor.extract_epub_from_memory(data)
            if extracted:
                data = extracted
        return data

    try:
        # Serve from cache if available
        file_bytes: bytes | None = None
        async with _download_cache_lock:
            cached_entry = _download_cache.get(cache_key)
            if cached_entry is not None:
                _, file_bytes = cached_entry
                # Keep in cache — torrent clients make multiple Range requests
                logging.debug(f"Serving download from cache: {provider}/{id}")

        if file_bytes is None:
            file_bytes = await _get_file_bytes()

        content_types = {
            "epub": "application/epub+zip",
            "mobi": "application/x-mobipocket-ebook",
            "pdf": "application/pdf",
        }
        ext = fmt if fmt in ("epub", "mobi", "pdf") else "epub"
        total_size = len(file_bytes)

        # HTTP Range request support (required for torrent webseed)
        if range_header:
            try:
                unit, _, ranges = range_header.partition("=")
                if unit.strip().lower() == "bytes" and ranges:
                    start_str, _, end_str = ranges.partition("-")
                    start = int(start_str.strip()) if start_str.strip() else 0
                    end = int(end_str.strip()) if end_str.strip() else total_size - 1
                    if start >= total_size:
                        return Response(status_code=416)
                    end = min(end, total_size - 1)
                    chunk = file_bytes[start:end + 1]
                    return Response(
                        content=chunk,
                        status_code=206,
                        media_type=content_types.get(ext, "application/octet-stream"),
                        headers={
                            "Content-Range": f"bytes {start}-{end}/{total_size}",
                            "Content-Length": str(len(chunk)),
                            "Accept-Ranges": "bytes",
                        }
                    )
            except (ValueError, IndexError):
                pass

        return Response(
            content=file_bytes,
            media_type=content_types.get(ext, "application/octet-stream"),
            headers={
                "Content-Length": str(total_size),
                "Accept-Ranges": "bytes",
            }
        )
    except Exception as e:
        logging.error(f"Error en download-content: {e}")
        return Response(status_code=500)


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
    lang: str = Query("", description="Idioma destino (es, en, fr, de, it, pt)"),
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
    config_manager = request.app.state.config_manager
    if not await _validate_apikey(apikey, config_manager):
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
        lang=lang,
        server_url=_server_url_from_request(request),
    )


# Prowlarr-compatible route: /{provider_id}/api?t=caps&apikey=...
# Readarr adds "/api" to the indexer baseUrl, so we provide
# /{provider_id} as baseUrl → Readarr calls /{provider_id}/api?t=caps
@router.get("/{provider_id}/api")
async def provider_torznab_api_prowlarr(
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
    lang: str = Query("", description="Idioma destino (es, en, fr, de, it, pt)"),
):
    """Prowlarr-compatible route — delegates to /api/{provider_id} handler."""
    return await provider_torznab_api(
        provider_id=provider_id,
        request=request,
        t=t, q=q, cat=cat, apikey=apikey, offset=offset, limit=limit,
        imdbid=imdbid, tvdbid=tvdbid, season=season, ep=ep,
        author=author, title=title, lang=lang,
    )


