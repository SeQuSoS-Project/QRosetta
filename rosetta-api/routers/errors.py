"""Exception handlers: every error response body is ``{"detail": ...}``.

Validation errors list ``{loc, msg, type}`` per problem. Submitted values are never echoed
back, so a rejected password or a non-finite number cannot reach the response.
"""

import re

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-errors")

_PYDANTIC_PREFIXES = ("Value error, ", "Assertion failed, ")
_INTERNAL_LOC_RE = re.compile(
    r"^(?:function-(?:after|before|wrap|plain)|list|dict|set|tuple|union|tagged-union|"
    r"nullable|lax-or-strict|json-or-python|constrained-\w+|chain|definition-ref)\[|\bat 0x[0-9a-f]+")
_REPR_RE = re.compile(r"<[^<>]*\bat 0x[0-9a-f]+>")

_DETAIL_BODY = " Body: {\"detail\": str}."

ERROR_RESPONSES = {
    400: "The request is well formed but cannot be run (e.g. the circuit does not parse, or names an unknown or unavailable runner).",
    401: ("Missing, invalid or expired bearer token (a token lasts expires_in seconds from "
          "POST /auth/token). Sent with WWW-Authenticate: Bearer."),
    403: "The account is deactivated, or the resource belongs to another account.",
    404: "Unknown or expired job id.",
    409: "The job exists but is in the wrong state or of the wrong kind for this request.",
    413: "Request body over the upload limit, or circuit text over MAX_QASM_SIZE.",
    429: ("Too many requests: this client address has used up the route's rate limit "
          "(Retry-After gives the seconds until the window resets), or, for a run with "
          "exclusive=true, this client already has an exclusive job that has not finished. "
          "Every response of a rate-limited route carries X-RateLimit-Limit, "
          "X-RateLimit-Remaining and X-RateLimit-Reset (Unix time)."),
}

_VALIDATION_422 = ("Request validation failed. Body: {\"detail\": [{\"loc\": [...], \"msg\": str, "
                   "\"type\": str}]}; submitted values are not echoed.")


def responses(*codes) -> dict:
    """OpenAPI ``responses`` entries. Each item is a status code (generic description) or
    ``(code, description)`` for a route-specific one."""
    out = {}
    for item in codes:
        code, text = item if isinstance(item, tuple) else (item, None)
        if code == 422:
            out[code] = {"description": text or _VALIDATION_422}
        else:
            out[code] = {"description": (text or ERROR_RESPONSES[code]) + _DETAIL_BODY}
    return out


def _depends_on(dependant, target) -> bool:
    return any(dep.call is target or _depends_on(dep, target) for dep in dependant.dependencies)


def document_route_errors(app: FastAPI) -> None:
    """Declare the codes that shared machinery returns: 413 on routes with a request body
    (the upload limit), 401 and 403 on routes that require a bearer token, 429 on
    rate-limited routes. A code a route already declares keeps its description."""
    from fastapi.routing import APIRoute
    from routers.rate_limit import is_rate_limited
    from services.security import get_current_user
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        extra = []
        if route.body_field is not None:
            extra.append(413)
        if _depends_on(route.dependant, get_current_user):
            extra += [401, 403]
        if is_rate_limited(route.endpoint):
            extra.append(429)
        for code, entry in responses(*extra).items():
            route.responses.setdefault(code, entry)
    app.openapi_schema = None


def _clean_msg(msg: str) -> str:
    for prefix in _PYDANTIC_PREFIXES:
        if msg.startswith(prefix):
            msg = msg[len(prefix):]
            break
    return _REPR_RE.sub("<internal>", msg)


def _clean_loc(loc) -> list:
    """``loc`` without pydantic's internal validator tags (union members, function
    validators, memory addresses)."""
    return [part if isinstance(part, int) else str(part) for part in loc
            if isinstance(part, int) or not _INTERNAL_LOC_RE.search(str(part))]


def validation_error_items(errors) -> list:
    """``[{loc, msg, type}]`` from pydantic errors, without ``input``, ``ctx`` or internal
    validator names; identical items are listed once."""
    items, seen = [], set()
    for err in errors:
        item = {"loc": _clean_loc(err.get("loc", ())),
                "msg": _clean_msg(str(err.get("msg", ""))),
                "type": str(err.get("type", ""))}
        key = (tuple(item["loc"]), item["msg"], item["type"])
        if key not in seen:
            seen.add(key)
            items.append(item)
    return items


async def _validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": validation_error_items(exc.errors())})


async def _http_exception_handler(request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    if exc.status_code == 422 and not isinstance(detail, list):
        detail = [{"loc": [], "msg": str(detail), "type": "value_error"}]
    return JSONResponse(status_code=exc.status_code, content={"detail": detail},
                        headers=getattr(exc, "headers", None))


async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    from routers.rate_limit import rate_limit_headers
    headers = {}
    view_limit = getattr(request.state, "view_rate_limit", None)
    if view_limit is not None:
        try:
            values, retry_after = rate_limit_headers(view_limit)
            headers = {**values, "Retry-After": str(retry_after)}
        except Exception:
            logger.warning("Could not read the rate-limit window", exc_info=True)
    return JSONResponse(status_code=429, content={"detail": f"Rate limit exceeded: {exc.detail}"},
                        headers=headers)


async def _unhandled_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url.path}", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def register_error_handlers(app: FastAPI) -> None:
    """Install the validation, HTTP-error (422 detail always a list), rate-limit and
    fallback 500 handlers on ``app``."""
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_exception_handler(Exception, _unhandled_handler)
