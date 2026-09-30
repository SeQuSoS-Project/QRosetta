"""Exception handlers: every error response body is ``{"detail": ...}``.

Validation errors list ``{loc, msg, type}`` per problem. Submitted values are never echoed
back, so a rejected password or a non-finite number cannot reach the response.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-errors")

_PYDANTIC_PREFIXES = ("Value error, ", "Assertion failed, ")

ERROR_RESPONSES = {
    400: {"description": "The request is well formed but cannot be run (e.g. the circuit does not parse, or names an unknown or unavailable runner). Body: {\"detail\": str}."},
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
            return msg[len(prefix):]
    return msg


def validation_error_items(errors) -> list:
    """``[{loc, msg, type}]`` from pydantic errors, without ``input`` or ``ctx``."""
    return [{"loc": [str(part) if not isinstance(part, int) else part for part in err.get("loc", ())],
             "msg": _clean_msg(str(err.get("msg", ""))),
             "type": str(err.get("type", ""))}
            for err in errors]


async def _validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": validation_error_items(exc.errors())})


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
    """Install the validation, rate-limit and fallback 500 handlers on ``app``."""
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_exception_handler(Exception, _unhandled_handler)
