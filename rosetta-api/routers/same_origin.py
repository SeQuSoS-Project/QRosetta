"""Cross-site request refusal: a POST, PUT, PATCH or DELETE whose Origin is neither the
server's own nor an allowed CORS origin is a 403 before any route, body or rate limit runs."""

import hmac
from urllib.parse import urlsplit

from fastapi.responses import JSONResponse

from config import settings
from services.security import PROXY_TOKEN_HEADER

STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
CROSS_SITE_DETAIL = "Requests from other sites are refused."
_DEFAULT_PORTS = {"http": 80, "https": 443}


def _origin_parts(origin: str):
    """``(host, port, scheme)`` of a serialised origin, or None when it is not one."""
    try:
        parts = urlsplit(origin)
        port = parts.port
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    if scheme not in _DEFAULT_PORTS or not parts.hostname or parts.path or parts.query \
            or parts.fragment or parts.username is not None or parts.password is not None:
        return None
    return parts.hostname.lower(), port if port is not None else _DEFAULT_PORTS[scheme], scheme


def _authority_parts(authority: str):
    """``(host, port or None)`` of a Host header value, or None when it is not one."""
    try:
        parts = urlsplit(f"//{authority.strip()}")
        port = parts.port
    except ValueError:
        return None
    if not parts.hostname or parts.path or parts.username is not None:
        return None
    return parts.hostname.lower(), port


def _own_authority(headers: dict) -> str:
    """The host the browser addressed: X-Forwarded-Host from the Cloud Run frontend when the
    request carries its QROSETTA_PROXY_TOKEN, else the Host header."""
    token = settings.PROXY_TOKEN
    if token:
        sent = headers.get(PROXY_TOKEN_HEADER.encode(), b"").decode("latin-1")
        forwarded = headers.get(b"x-forwarded-host", b"").decode("latin-1").split(",")[0].strip()
        if forwarded and hmac.compare_digest(sent.encode(), token.encode()):
            return forwarded
    return headers.get(b"host", b"").decode("latin-1")


def _same_authority(origin, authority) -> bool:
    if authority is None:
        return False
    host, port = authority
    return host == origin[0] and (port if port is not None else _DEFAULT_PORTS[origin[2]]) == origin[1]


def allowed_origins() -> set:
    """The CORS origins as ``(host, port, scheme)``."""
    return {parts for parts in map(_origin_parts, settings.get_cors_origins()) if parts is not None}


def request_is_cross_site(headers: dict) -> bool:
    """True when a request's raw ASGI headers show a browser sent it from another site.

    With an Origin header: true unless it is an allowed CORS origin or names the same host
    and port as the request (scheme not compared: the API sees plain http behind the TLS
    proxies). ``Origin: null`` is cross-site. Without one: true only for Sec-Fetch-Site
    cross-site or same-site. A request with neither (the CLI, curl) is not cross-site.
    """
    origin = headers.get(b"origin")
    if origin is None:
        return headers.get(b"sec-fetch-site", b"").strip().lower() in (b"cross-site", b"same-site")
    parts = _origin_parts(origin.decode("latin-1").strip())
    if parts is None:
        return True
    if parts in allowed_origins():
        return False
    return not _same_authority(parts, _authority_parts(_own_authority(headers)))


class RefuseCrossSite:
    """ASGI middleware: 403 for a state-changing request that ``request_is_cross_site``."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] in STATE_CHANGING_METHODS \
                and request_is_cross_site(dict(scope.get("headers") or [])):
            from starlette.requests import Request
            from services.security_events import security_event
            origin = dict(scope.get("headers") or []).get(b"origin", b"").decode("latin-1")[:200]
            security_event("cross_site.refused", Request(scope), origin=origin or None)
            await JSONResponse(status_code=403, content={"detail": CROSS_SITE_DETAIL})(scope, receive, send)
            return
        await self.app(scope, receive, send)
