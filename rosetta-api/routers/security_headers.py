"""Browser security headers on every response the API serves: a Content-Security-Policy chosen
by path and media type, nosniff, no referrer, a same-origin opener policy and no framing.

nginx sends the same policies for the files it serves itself (`nginx/nginx.conf`,
`infra/nginx-frontend.conf`); `tests/unit/test_security_headers.py` keeps them equal."""

from urllib.parse import urlsplit

from starlette.datastructures import MutableHeaders

from services.quirk_converter import QUIRK_URL

_QUIRK = urlsplit(QUIRK_URL)
QUIRK_ORIGIN = f"{_QUIRK.scheme}://{_QUIRK.netloc}"

PAGE_CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
            f"connect-src 'self'; font-src 'self'; frame-src {QUIRK_ORIGIN}; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'")

SHARE_CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
             "object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")

SWAGGER_CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
               "connect-src 'self'; font-src 'self'; object-src 'none'; frame-ancestors 'none'; "
               "base-uri 'none'; form-action 'self'")

REDOC_SCRIPT_URL = "https://cdn.jsdelivr.net/npm/redoc@2.1.5/bundles/redoc.standalone.js"
REDOC_LOGO_URL = "https://cdn.redoc.ly/redoc/logo-mini.svg"

REDOC_CSP = (f"default-src 'self'; script-src {REDOC_SCRIPT_URL}; style-src 'self' 'unsafe-inline'; "
             f"img-src 'self' data: {REDOC_LOGO_URL}; connect-src 'self'; font-src 'self'; worker-src blob:; "
             "object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")

NON_HTML_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

COMMON_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "X-Frame-Options": "DENY",
}

_ROUTE_CSP = {"/docs": SWAGGER_CSP, "/redoc": REDOC_CSP}


def content_security_policy(path: str, content_type: str) -> str:
    """The policy for a response at ``path`` (without the root path) of ``content_type``."""
    if path in _ROUTE_CSP:
        return _ROUTE_CSP[path]
    if path.endswith("/share.html"):
        return SHARE_CSP
    if content_type.split(";")[0].strip().lower() == "text/html":
        return PAGE_CSP
    return NON_HTML_CSP


def security_headers(path: str, content_type: str) -> dict:
    """Every header above for a response at ``path`` of ``content_type``; the handler of
    unhandled errors, which runs outside the middleware stack, sends them itself."""
    return {"Content-Security-Policy": content_security_policy(path, content_type), **COMMON_HEADERS}


class SecurityHeaders:
    """ASGI middleware adding the headers above to every HTTP response; a header the route
    set itself is kept. The share page is also sent with Cache-Control: no-store."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        root = scope.get("root_path", "")
        if root and path.startswith(root):
            path = path[len(root):] or "/"

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                policy = content_security_policy(path, headers.get("content-type", ""))
                headers.setdefault("Content-Security-Policy", policy)
                for key, value in COMMON_HEADERS.items():
                    headers.setdefault(key, value)
                if path.endswith("/share.html"):
                    headers.setdefault("Cache-Control", "no-store")
            await send(message)

        await self.app(scope, receive, send_with_headers)
