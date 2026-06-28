"""
Health check and diagnostics endpoints.
"""
import logging
from fastapi import APIRouter, Query

from app.providers.registry import registry

router = APIRouter()


@router.get("/")
async def root():
    """
    Root endpoint: used by *Arr apps for basic connectivity checks.
    Returns a simple JSON response so Readarr/Radarr/Sonarr can detect
    the service is alive before attempting Torznab API calls.
    """
    return {
        "service": "WebTranslatorr",
        "version": "1.0.0",
        "type": "torznab",
        "docs": "/api?t=caps",
        "health": "/health",
    }


@router.get("/health")
async def health_check(brief: bool = Query(False, description="Brief mode: just status")):
    """
    Health check con diagnóstico de providers.
    Por defecto muestra estado detallado.
    Usa ?brief=true para el check rápido de Docker/Readarr.
    """
    providers_status = {}
    all_providers = registry.get_all()

    for provider in all_providers:
        pid = provider.provider_id
        try:
            # Verificar que el provider tiene capabilities y está registrado
            caps = provider.get_capabilities()
            providers_status[pid] = {
                "registered": True,
                "display_name": provider.display_name,
                "categories": caps.supported_categories[:4],  # primeros 4
                "book_search": caps.supports_book_search,
            }
        except Exception as e:
            providers_status[pid] = {
                "registered": True,
                "error": str(e),
            }

    if brief:
        return {"status": "healthy", "service": "WebTranslatorr"}

    return {
        "status": "healthy",
        "service": "WebTranslatorr",
        "providers": len(all_providers),
        "details": providers_status,
    }


@router.get("/health/search")
async def health_search(
    q: str = Query("quijote", description="Test query"),
):
    """
    Health check profundo: ejecuta una búsqueda real en todos los providers
    y reporta cuántos resultados devuelve cada uno.
    """
    from app.routing.smart_router import smart_router

    params = {"t": "search", "q": q, "cat": "7000,7020,8000,8010"}
    providers = await smart_router.route(params)

    results = {}
    from app.services.cache import search_cache

    for provider in providers:
        pid = provider.provider_id
        try:
            provider_results = await provider.search(
                query=q, categories=[7020], limit=5
            )
            results[pid] = {
                "results": len(provider_results) if isinstance(provider_results, list) else 0,
                "healthy": True,
            }
        except Exception as e:
            results[pid] = {
                "results": 0,
                "healthy": False,
                "error": str(e)[:200],
            }

    total_results = sum(r["results"] for r in results.values())
    healthy_providers = sum(1 for r in results.values() if r.get("healthy"))

    return {
        "query": q,
        "total_results": total_results,
        "providers_tested": len(providers),
        "healthy_providers": healthy_providers,
        "details": results,
    }
