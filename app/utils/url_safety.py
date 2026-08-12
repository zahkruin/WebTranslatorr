import ipaddress
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_BLOCKED_HOSTNAMES = frozenset({
    "localhost",
    "metadata.google.internal",
    "metadata.goog",
})


def _is_blocked_ip(hostname: str) -> bool:
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
    )


def is_safe_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    lowered = hostname.lower().rstrip(".")
    if lowered in _BLOCKED_HOSTNAMES:
        return False
    if lowered.endswith(".local") or lowered.endswith(".internal"):
        return False

    return not _is_blocked_ip(lowered)


def is_safe_redirect(from_url: str, to_url: str) -> bool:
    return is_safe_url(to_url)
