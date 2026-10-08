"""Rate-limit headers: X-RateLimit-* on every response of a limited route, Retry-After on 429."""

import math
import time

from starlette.datastructures import MutableHeaders

from services.security import limiter


def rate_limit_headers(view_limit) -> tuple[dict, int]:
    """``(X-RateLimit-* headers, seconds until the window resets)`` for the limit a request
    was counted against (slowapi's ``request.state.view_rate_limit``)."""
    item, identifiers = view_limit
    reset_at, remaining = limiter.limiter.get_window_stats(item, *identifiers)
    retry_after = max(1, math.ceil(reset_at - time.time()))
    return ({"X-RateLimit-Limit": str(item.amount),
             "X-RateLimit-Remaining": str(remaining),
             "X-RateLimit-Reset": str(int(math.ceil(reset_at)))}, retry_after)


def is_rate_limited(endpoint) -> bool:
    """True when ``endpoint`` carries a ``@limiter.limit`` decorator."""
    name = f"{endpoint.__module__}.{endpoint.__name__}"
    return name in limiter._route_limits or name in limiter._dynamic_route_limits


class RateLimitHeaders:
    """ASGI middleware adding X-RateLimit-Limit/Remaining/Reset to responses of limited
    routes (the 429 handler sets its own, with Retry-After)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                view_limit = (scope.get("state") or {}).get("view_rate_limit")
                if view_limit is not None:
                    headers = MutableHeaders(scope=message)
                    if "x-ratelimit-limit" not in headers:
                        try:
                            values, _ = rate_limit_headers(view_limit)
                        except Exception:
                            values = {}
                        for key, value in values.items():
                            headers[key] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)
