"""
API endpoints para consultar y gestionar la resolución dinámica de dominios.
"""

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/domains", tags=["domains"])


@router.get("")
async def get_domains(request: Request):
    """
    Devuelve el estado actual de todos los dominios resueltos.

    Response:
    {
      "mejortorrent": {
        "url": "https://www42.mejortorrent.eu",
        "resolved_at": "2026-04-17T19:30:00Z",
        "source": "privtree",
        "healthy": true,
        "last_health_check": "2026-04-17T19:30:00Z"
      },
      ...
    }
    """
    resolver = request.app.state.domain_resolver
    return resolver.get_status()


@router.post("/refresh")
async def refresh_domains(request: Request):
    """
    Fuerza la resolución de todos los dominios inmediatamente.
    Útil para debugging o cuando se sabe que un dominio ha cambiado.
    """
    resolver = request.app.state.domain_resolver
    results = await resolver.resolve_all()
    status = resolver.get_status()
    return {
        "message": "Domain resolution complete",
        "domains": status,
    }


@router.post("/refresh/{provider_id}")
async def refresh_provider_domain(provider_id: str, request: Request):
    """Fuerza la resolución del dominio de un provider específico."""
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
async def check_provider_health(provider_id: str, request: Request):
    """Ejecuta un health check del dominio actual de un provider."""
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
