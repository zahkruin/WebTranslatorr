"""
API endpoints para consultar y gestionar la resolución dinámica de dominios.
"""

from fastapi import APIRouter, Query, Request

from app.api.auth import require_apikey

router = APIRouter(prefix="/api/domains", tags=["domains"])


@router.get("")
async def get_domains(request: Request, apikey: str = Query("")):
    require_apikey(apikey)
    resolver = request.app.state.domain_resolver
    return resolver.get_status()


@router.post("/refresh")
async def refresh_domains(request: Request, apikey: str = Query("")):
    require_apikey(apikey)
    resolver = request.app.state.domain_resolver
    results = await resolver.resolve_all()
    status = resolver.get_status()
    return {
        "message": "Domain resolution complete",
        "domains": status,
    }


@router.post("/refresh/{provider_id}")
async def refresh_provider_domain(
    provider_id: str,
    request: Request,
    apikey: str = Query(""),
):
    require_apikey(apikey)
    resolver = request.app.state.domain_resolver
    try:
        new_domain = await resolver.resolve(provider_id)
        status = resolver.get_status(provider_id)
        return {
            "message": f"Domain resolved for {provider_id}",
            "domain": new_domain,
            "details": status,
        }
    except ValueError as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=404,
            content={"error": str(e)},
        )


@router.get("/health/{provider_id}")
async def check_provider_health(
    provider_id: str,
    request: Request,
    apikey: str = Query(""),
):
    require_apikey(apikey)
    resolver = request.app.state.domain_resolver
    try:
        is_healthy = await resolver.health_check(provider_id)
        status = resolver.get_status(provider_id)
        return {
            "provider_id": provider_id,
            "healthy": is_healthy,
            "details": status,
        }
    except ValueError as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=404,
            content={"error": str(e)},
        )
