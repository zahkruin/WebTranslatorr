import secrets

from fastapi import HTTPException, Query

from config import settings


def validate_apikey(apikey: str) -> bool:
    return secrets.compare_digest(apikey, settings.API_KEY)


def require_apikey(apikey: str = Query("")) -> None:
    if not validate_apikey(apikey):
        raise HTTPException(status_code=401, detail="Invalid API key")
