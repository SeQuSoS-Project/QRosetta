"""The local lifecycle token: a secret the qrosetta command writes at start and compose mounts
as a file (QROSETTA_LIFECYCLE_TOKEN_FILE). Without the file no request matches it."""

import hmac
import os


def lifecycle_token():
    """The token from QROSETTA_LIFECYCLE_TOKEN_FILE, or None when unset, unreadable or empty."""
    path = os.getenv("QROSETTA_LIFECYCLE_TOKEN_FILE", "").strip()
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            token = fh.read().strip()
    except OSError:
        return None
    return token or None


def matches_lifecycle_token(candidate: str) -> bool:
    """True when ``candidate`` is the lifecycle token (constant-time comparison)."""
    token = lifecycle_token()
    return bool(token and candidate) and hmac.compare_digest(candidate.encode(), token.encode())
