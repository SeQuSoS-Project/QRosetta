"""Error text for clients and stored reports: messages the API writes for bad input, else the
exception type only."""

from fastapi import HTTPException

from qrosetta_commons.redact import strip_absolute_paths
from services.prep_worker import PreparationFailed


def is_client_error(exc: BaseException) -> bool:
    """True for the exceptions whose message the API writes for the client."""
    return isinstance(exc, (HTTPException, ValueError, PreparationFailed))


def client_error_text(exc: BaseException) -> str:
    """An HTTPException's detail, or the message of a ValueError or PreparationFailed (the
    errors circuit resolution and preparation raise for the circuit itself), with absolute
    paths replaced by ``<path>``; any other exception as ``<Type>`` only."""
    if isinstance(exc, HTTPException):
        return strip_absolute_paths(str(exc.detail))
    if is_client_error(exc) and str(exc):
        return strip_absolute_paths(str(exc))
    return type(exc).__name__


def internal_error_text(what: str, exc: BaseException) -> str:
    """``<what> failed (<Type>)``, for an error the client can do nothing about."""
    return f"{what} failed ({type(exc).__name__})"
