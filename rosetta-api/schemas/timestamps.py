"""Datetime type serialised as timezone-aware UTC ISO 8601 ending in 'Z'."""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import PlainSerializer


def utc_iso(value: datetime) -> str:
    """``value`` in UTC as ISO 8601 with a 'Z' suffix; a naive value is taken as UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


UtcDatetime = Annotated[datetime, PlainSerializer(utc_iso, return_type=str, when_used="json-unless-none")]
