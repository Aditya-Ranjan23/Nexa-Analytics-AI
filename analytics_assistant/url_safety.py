"""Guards for outbound URL fetches (SSRF mitigation)."""

import ipaddress
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_BLOCKED_HOSTS = frozenset({"localhost", "metadata.google.internal"})


def validate_public_http_url(url: str) -> str:
    cleaned = url.strip()
    parsed = urlparse(cleaned)

    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http and https URLs are allowed.")
    if not parsed.hostname:
        raise ValueError("URL must include a hostname.")

    host = parsed.hostname.lower().rstrip(".")
    if host in _BLOCKED_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        raise ValueError("This URL host is not allowed.")

    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            raise ValueError("Private or reserved network URLs are not allowed.")

    return cleaned
