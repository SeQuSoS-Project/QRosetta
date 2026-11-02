"""Security events of the API, one JSON object per line on the ``rosetta-security-events`` logger
(stdout): sign-ins and failed sign-ins, registrations, sign-outs, password changes, account
deletions, refused requests (401, 403, cross-site, rate limit). Each line carries a UTC
timestamp with its offset, the event, the method, path and client address, and the account id
when known; never a password, token or request body. An email appears only as the first 16 hex
digits of its SHA-256. JSON escaping keeps control characters out of the line."""

import hashlib
import json
import logging
import sys
from datetime import datetime, timezone

LOGGER = logging.getLogger("rosetta-security-events")
if not LOGGER.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(_handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False


def email_digest(email: str) -> str:
    return hashlib.sha256(str(email or "").strip().lower().encode()).hexdigest()[:16]


def _request_fields(request) -> dict:
    from services.security import client_address
    fields = {"method": request.method, "path": request.url.path}
    try:
        fields["client"] = client_address(request)
    except Exception:
        fields["client"] = None
    return fields


def security_event(event: str, request=None, **fields) -> None:
    """Write one event line; ``fields`` with the value None are left out."""
    record = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "event": event}
    if request is not None:
        record.update(_request_fields(request))
    record.update({k: v for k, v in fields.items() if v is not None})
    LOGGER.info(json.dumps(record, ensure_ascii=True, default=str))
