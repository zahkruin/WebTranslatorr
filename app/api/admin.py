"""
Admin API endpoints for managing providers, settings, and Readarr instances.

These endpoints are intended for the local administration frontend and do
**not** require API key authentication.
"""
import logging
from typing import Any

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.providers.registry import registry
from app.core.exceptions import ProviderNotFoundError
from app.scraping.http_client import HttpClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ProviderUpdate(BaseModel):
    enabled: bool | None = None
    domain: str | None = None


class SettingUpdate(BaseModel):
    value: str


class ReadarrInstanceCreate(BaseModel):
    name: str
    url: str
    api_key: str
    external_url: str = ""


class ReadarrInstanceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    api_key: str | None = None
    enabled: bool | None = None
    external_url: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_provider_capabilities(provider_id: str) -> dict[str, Any] | None:
    """Return capabilities info for a provider if it is registered, else None."""
    try:
        provider = registry.get(provider_id)
        caps = provider.get_capabilities()
        return {
            "display_name": caps.display_name,
            "supports_book_search": caps.supports_book_search,
            "supports_movie_search": caps.supports_movie_search,
            "supports_tv_search": caps.supports_tv_search,
            "categories": caps.supported_categories,
            "supported_search_params": caps.supported_search_params,
        }
    except ProviderNotFoundError:
        return None


# ---------------------------------------------------------------------------
# Provider endpoints
# ---------------------------------------------------------------------------

@router.get("/providers")
async def list_providers(request: Request):
    """List all providers from DB, enriched with registry capabilities."""
    config_manager = request.app.state.config_manager
    db_providers = await config_manager.get_all_providers()

    enriched = []
    for p in db_providers:
        provider_id = p["provider_id"]
        caps = _get_provider_capabilities(provider_id)
        entry: dict[str, Any] = {
            "provider_id": provider_id,
            "enabled": p["enabled"],
            "domain": p.get("domain", ""),
            "display_name": p.get("display_name", ""),
            "last_test_status": p.get("last_test_status"),
            "last_test_http_status": p.get("last_test_http_status"),
            "last_test_latency_ms": p.get("last_test_latency_ms"),
            "last_test_error": p.get("last_test_error"),
            "last_test_at": p.get("last_test_at"),
            "last_test_url": p.get("last_test_url"),
        }
        if caps is not None:
            entry["capabilities"] = caps
        enriched.append(entry)

    return {"providers": enriched}


@router.put("/providers/{provider_id}")
async def update_provider(provider_id: str, body: ProviderUpdate, request: Request):
    """Enable/disable a provider or update its domain."""
    config_manager = request.app.state.config_manager

    # Check provider exists
    existing = await config_manager.get_provider_config(provider_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found in database")

    if body.enabled is not None:
        await config_manager.set_provider_enabled(provider_id, body.enabled)
    if body.domain is not None:
        await config_manager.set_provider_domain(provider_id, body.domain)

    return {"status": "ok", "provider_id": provider_id}


@router.post("/providers/reload")
async def reload_providers(request: Request):
    """Force reload all providers from the database into the registry."""
    resolver = request.app.state.domain_resolver
    config_manager = request.app.state.config_manager
    http_client = request.app.state.http_client

    # Lazy import to avoid circular dependencies at module level
    from app.api import torznab as torznab_module

    await torznab_module._init_providers(resolver, http_client, config_manager)

    provider_count = len(registry.get_all())
    return {"status": "reloaded", "provider_count": provider_count}


# ---------------------------------------------------------------------------
# Settings endpoints
# ---------------------------------------------------------------------------

@router.get("/settings")
async def get_settings(request: Request):
    """Return all stored settings."""
    config_manager = request.app.state.config_manager
    settings = await config_manager.get_all_settings()
    return {"settings": settings}


@router.put("/settings/{key}")
async def update_setting(key: str, body: SettingUpdate, request: Request):
    """Update a single setting value."""
    config_manager = request.app.state.config_manager
    await config_manager.set_setting(key, body.value)
    return {"status": "ok", "key": key, "value": body.value}


# ---------------------------------------------------------------------------
# Readarr instance endpoints
# ---------------------------------------------------------------------------

@router.get("/readarr")
async def list_readarr_instances(request: Request):
    """List all configured Readarr instances."""
    from app.persistence.database import get_db
    from app.persistence.models import get_readarr_instances

    db = await get_db()
    instances = await get_readarr_instances(db)
    return {"instances": instances}


@router.post("/readarr", status_code=201)
async def create_readarr_instance(body: ReadarrInstanceCreate, request: Request):
    """Register a new Readarr instance."""
    from app.persistence.database import get_db
    from app.persistence.models import add_readarr_instance

    # Validate URL and API key are ASCII-safe (HTTP mandates ASCII headers)
    try:
        body.url.encode("ascii")
    except UnicodeEncodeError:
        raise HTTPException(status_code=400, detail="Readarr URL contains non-ASCII characters. Use only ASCII characters.")
    try:
        body.api_key.encode("ascii")
    except UnicodeEncodeError:
        raise HTTPException(status_code=400, detail="Readarr API key contains non-ASCII characters.")

    db = await get_db()
    instance_id = await add_readarr_instance(db, body.name, body.url, body.api_key, body.external_url)
    return {"status": "created", "id": instance_id}


@router.put("/readarr/{instance_id}")
async def update_readarr_instance(instance_id: int, body: ReadarrInstanceUpdate, request: Request):
    """Update an existing Readarr instance."""
    from app.persistence.database import get_db
    from app.persistence.models import update_readarr_instance

    # Build kwargs from non-null fields
    kwargs: dict[str, Any] = {}
    if body.name is not None:
        kwargs["name"] = body.name
    if body.url is not None:
        kwargs["url"] = body.url
    if body.api_key is not None:
        kwargs["api_key"] = body.api_key
    if body.enabled is not None:
        kwargs["enabled"] = int(body.enabled)

    if not kwargs:
        raise HTTPException(status_code=400, detail="No fields to update")

    db = await get_db()
    await update_readarr_instance(db, instance_id, **kwargs)
    return {"status": "updated", "id": instance_id}


@router.delete("/readarr/{instance_id}")
async def delete_readarr_instance(instance_id: int, request: Request):
    """Remove a Readarr instance."""
    from app.persistence.database import get_db
    from app.persistence.models import delete_readarr_instance

    db = await get_db()
    await delete_readarr_instance(db, instance_id)
    return {"status": "deleted", "id": instance_id}


@router.post("/readarr/{instance_id}/sync")
async def sync_readarr_instance(instance_id: int, request: Request):
    """Sync all enabled book providers as Torznab indexers to a Readarr instance."""
    from app.persistence.database import get_db
    from app.persistence.models import get_readarr_instances
    from app.services.readarr_syncer import ReadarrSyncer
    from config import settings as app_settings

    config_manager = request.app.state.config_manager

    # Look up the Readarr instance
    db = await get_db()
    instances = await get_readarr_instances(db)
    instance = next((i for i in instances if i["id"] == instance_id), None)
    if instance is None:
        raise HTTPException(
            status_code=404, detail=f"Readarr instance {instance_id} not found"
        )

    # Resolve external URL — per-instance setting takes priority,
    # then global DB setting, then env var fallback.
    external_url = instance.get("external_url") or ""
    if not external_url:
        external_url = await config_manager.get_setting("external_url") or ""
    if not external_url:
        external_url = app_settings.EXTERNAL_URL

    wtr_api_key = await config_manager.get_setting("api_key") or ""
    if not wtr_api_key:
        wtr_api_key = app_settings.API_KEY

    syncer = ReadarrSyncer(config_manager)
    result = await syncer.sync_all(
        readarr_url=instance["url"],
        api_key=instance["api_key"],
        external_url=external_url,
        wtr_api_key=wtr_api_key,
    )
    return result


@router.post("/readarr/{instance_id}/test")
async def test_readarr_instance(instance_id: int, request: Request):
    """Test connectivity with a Readarr instance."""
    from app.persistence.database import get_db
    from app.persistence.models import get_readarr_instances
    from app.services.readarr_syncer import ReadarrSyncer

    config_manager = request.app.state.config_manager

    # Look up the Readarr instance
    db = await get_db()
    instances = await get_readarr_instances(db)
    instance = next((i for i in instances if i["id"] == instance_id), None)
    if instance is None:
        raise HTTPException(
            status_code=404, detail=f"Readarr instance {instance_id} not found"
        )

    syncer = ReadarrSyncer(config_manager)
    result = await syncer.test_connection(
        readarr_url=instance["url"],
        api_key=instance["api_key"],
    )
    return result


# ---------------------------------------------------------------------------
# Provider test endpoints
# ---------------------------------------------------------------------------

@router.post("/providers/{provider_id}/test")
async def test_provider(provider_id: str, request: Request):
    """Run a connectivity test against a single provider's base URL.

    Returns a ``ProviderTestResult`` with status, HTTP status code,
    latency in ms, and an optional error message.
    """
    http_client: HttpClient = request.app.state.http_client
    config_manager = request.app.state.config_manager

    from app.services.provider_tester import ProviderTester, ProviderTestResult
    from dataclasses import asdict

    tester = ProviderTester(http_client, config_manager)
    result: ProviderTestResult = await tester.test_provider(provider_id)

    response = asdict(result)
    response["provider_id"] = provider_id
    return response


@router.post("/providers/test-all")
async def test_all_providers(request: Request):
    """Run connectivity tests against every enabled provider in parallel.

    Returns a list of per-provider results plus a summary with counts.
    """
    http_client = request.app.state.http_client
    config_manager = request.app.state.config_manager

    from app.services.provider_tester import ProviderTester
    from dataclasses import asdict

    tester = ProviderTester(http_client, config_manager)
    results = await tester.test_all_providers()

    ok = sum(1 for r in results if r.status == "ok")
    failed = len(results) - ok

    return {
        "results": [asdict(r) for r in results],
        "summary": {
            "total": len(results),
            "ok": ok,
            "failed": failed,
        },
    }


@router.get("/providers/test-results")
async def get_test_results(request: Request):
    """Return the last stored test result for every provider that has been tested.

    The response is a dict keyed by ``provider_id``.  Each value matches the
    ``ProviderTestResult`` shape (status, http_status, latency_ms, …).
    """
    from app.persistence.database import get_db
    from app.persistence.models import get_test_results as _get_test_results

    db = await get_db()
    results = await _get_test_results(db)
    return {"results": results}
