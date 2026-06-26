"""
API endpoints for provider discovery and health.

Used by indexer applications (Ebookerr, Prowlarr, etc.) to discover
available providers and their capabilities programmatically.
"""

from fastapi import APIRouter, Query, Response

from app.api.torznab import _validate_apikey
from app.providers.registry import registry

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("")
async def list_providers(apikey: str = Query("", description="API Key")):
    """List all registered providers with their capabilities.

    Returns JSON array with provider_id, display_name, enabled,
    and search capabilities for each provider.

    Used by Ebookerr/Prowlarr to auto-discover and sync indexers.
    """
    if not _validate_apikey(apikey):
        from app.torznab.errors import TorznabErrors
        return Response(
            content=TorznabErrors.incorrect_api_key(),
            media_type="application/xml",
        )

    providers = []
    for pid, provider in registry._providers.items():
        caps = provider.get_capabilities()
        providers.append({
            "provider_id": pid,
            "display_name": caps.display_name,
            "supports_book_search": caps.supports_book_search,
            "supports_movie_search": caps.supports_movie_search,
            "supports_tv_search": caps.supports_tv_search,
            "categories": caps.supported_categories,
            "supported_search_params": caps.supported_search_params,
        })

    return {"providers": providers}


@router.get("/{provider_id}")
async def get_provider(provider_id: str, apikey: str = Query("", description="API Key")):
    """Get details for a single provider."""
    if not _validate_apikey(apikey):
        from app.torznab.errors import TorznabErrors
        return Response(
            content=TorznabErrors.incorrect_api_key(),
            media_type="application/xml",
        )

    provider_id_lower = provider_id.lower()
    from app.core.exceptions import ProviderNotFoundError

    try:
        provider = registry.get(provider_id_lower)
    except ProviderNotFoundError:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=404,
            content={"error": f"Provider '{provider_id}' not found"},
        )

    caps = provider.get_capabilities()
    return {
        "provider_id": provider_id_lower,
        "display_name": caps.display_name,
        "supports_book_search": caps.supports_book_search,
        "supports_movie_search": caps.supports_movie_search,
        "supports_tv_search": caps.supports_tv_search,
        "categories": caps.supported_categories,
        "supported_search_params": caps.supported_search_params,
    }
