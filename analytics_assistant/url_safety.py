"""Guards for outbound URL fetches (SSRF mitigation)."""

import ipaddress
import logging
import socket
from typing import Callable
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

_BLOCKED_HOSTS = frozenset({"localhost", "metadata.google.internal"})
# ponytail: stdlib DNS only; upgrade path is custom resolver with timeout/TTL cache.
_DEFAULT_PORTS = {"http": 80, "https": 443}


def _is_blocked_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
    )


def _check_ip_literal(host: str) -> None:
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return
    if _is_blocked_ip(addr):
        raise ValueError("Private or reserved network URLs are not allowed.")


def resolve_host_addresses(
    hostname: str,
    port: int,
    resolver: Callable | None = None,
) -> list[str]:
    """Resolve hostname to IP strings. Injectable resolver for tests."""
    lookup = resolver or socket.getaddrinfo
    try:
        results = lookup(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        logger.warning("DNS resolution failed for %s: %s", hostname, exc)
        raise ValueError("Unable to resolve URL hostname.") from exc

    addresses: list[str] = []
    for _family, _socktype, _proto, _canonname, sockaddr in results:
        addresses.append(sockaddr[0])
    if not addresses:
        raise ValueError("Unable to resolve URL hostname.")
    return addresses


def validate_resolved_addresses(addresses: list[str]) -> None:
    for ip_str in addresses:
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            logger.warning("Skipping non-IP resolve result: %s", ip_str)
            continue
        if _is_blocked_ip(addr):
            raise ValueError("URL resolves to a private or reserved network address.")


def validate_hostname_resolves_public(
    hostname: str,
    port: int,
    resolver: Callable | None = None,
) -> None:
    validate_resolved_addresses(resolve_host_addresses(hostname, port, resolver=resolver))


def validate_public_http_url(url: str, resolver: Callable | None = None) -> str:
    cleaned = url.strip()
    parsed = urlparse(cleaned)

    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http and https URLs are allowed.")
    if not parsed.hostname:
        raise ValueError("URL must include a hostname.")
    if parsed.username or parsed.password:
        raise ValueError("URLs with embedded credentials are not allowed.")

    host = parsed.hostname.lower().rstrip(".")
    if host in _BLOCKED_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        raise ValueError("This URL host is not allowed.")

    _check_ip_literal(host)

    port = parsed.port or _DEFAULT_PORTS[parsed.scheme]
    validate_hostname_resolves_public(host, port, resolver=resolver)

    return cleaned


def _redirect_hook(response, *args, **kwargs) -> None:  # noqa: ANN002
    """Requests event hook: validate every redirect destination before following it."""
    if response.is_redirect:
        next_url = response.headers.get("Location", "")
        if next_url:
            try:
                validate_public_http_url(next_url)
            except ValueError as exc:
                # Abort the request chain by raising inside the hook.
                raise ValueError(
                    f"SSRF redirect protection blocked redirect to {next_url!r}: {exc}"
                ) from exc


def build_safe_session() -> requests.Session:
    """Return a requests.Session with SSRF redirect validation enabled.

    Every redirect is checked by `validate_public_http_url` before being
    followed, preventing redirect-based SSRF bypass (TD-019).
    """
    session = requests.Session()
    session.hooks["response"].append(_redirect_hook)
    return session
