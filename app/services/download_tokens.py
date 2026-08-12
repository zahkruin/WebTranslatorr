import base64
import hashlib
import hmac
import time

from config import settings


def sign_download(
    provider: str,
    internal_id: str,
    fmt: str,
    ttl_seconds: int | None = None,
) -> str:
    ttl = ttl_seconds if ttl_seconds is not None else settings.DOWNLOAD_TOKEN_TTL
    exp = int(time.time()) + ttl
    message = f"{provider}:{internal_id}:{fmt}:{exp}"
    sig = hmac.new(
        settings.API_KEY.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    raw = f"{exp}.{sig}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def verify_download(token: str, provider: str, internal_id: str, fmt: str) -> bool:
    try:
        padding = "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(token + padding).decode()
        exp_str, sig = decoded.split(".", 1)
        exp = int(exp_str)
        if exp < time.time():
            return False
        message = f"{provider}:{internal_id}:{fmt}:{exp}"
        expected = hmac.new(
            settings.API_KEY.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False


def build_download_url(provider: str, internal_id: str, fmt: str = "epub") -> str:
    base = settings.EXTERNAL_URL.rstrip("/")
    return (
        f"{base}/api/download?provider={provider}&id={internal_id}"
        f"&fmt={fmt}&apikey={settings.API_KEY}"
    )


def build_download_content_url(provider: str, internal_id: str, fmt: str = "epub") -> str:
    base = settings.EXTERNAL_URL.rstrip("/")
    token = sign_download(provider, internal_id, fmt)
    return (
        f"{base}/api/download-content?provider={provider}&id={internal_id}"
        f"&fmt={fmt}&token={token}"
    )
