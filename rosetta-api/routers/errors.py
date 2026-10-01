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

ERROR_RESPONSES = {
    400: {"description": "The request is well formed but cannot be run (e.g. the circuit does not parse, or names an unknown or unavailable runner). Body: {\"detail\": str}."},
    403: {"description": "The resource belongs to another account. Body: {\"detail\": str}."},
    404: {"description": "Unknown or expired job id. Body: {\"detail\": str}."},
    409: {"description": "The job exists but is in the wrong state or of the wrong kind for this request. Body: {\"detail\": str}."},
    413: {"description": "Request body over the upload limit, or circuit text over MAX_QASM_SIZE. Body: {\"detail\": str}."},
    422: {"description": "Request validation failed. Body: {\"detail\": [{\"loc\": [...], \"msg\": str, \"type\": str}]}; submitted values are not echoed."},
}


def responses(*codes: int) -> dict:
    """OpenAPI ``responses`` entries for the given status codes."""
    return {code: ERROR_RESPONSES[code] for code in codes}


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
    response = JSONResponse(status_code=429, content={"detail": f"Rate limit exceeded: {exc.detail}"})
    limiter = getattr(request.app.state, "limiter", None)
    view_limit = getattr(request.state, "view_rate_limit", None)
    if limiter is not None and view_limit is not None:
        response = limiter._inject_headers(response, view_limit)
    return response


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
