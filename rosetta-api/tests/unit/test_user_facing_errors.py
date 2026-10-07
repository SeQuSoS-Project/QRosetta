"""userFacingError (static/js/run_status.js) rewrites the operator hints in the messages the
dispatchers produce today into steps a UI user can take."""
import asyncio

import httpx

from services.dispatcher_http import safe_request
from tests.unit.frontend_harness import call_js, requires_node

pytestmark = requires_node


class _RaisingClient:
    def __init__(self, exc):
        self._exc = exc

    async def post(self, url, json, timeout=None):
        raise self._exc


def _error(exc, timeout_s=300):
    return asyncio.run(safe_request(_RaisingClient(exc), "http://runner/run", {}, "qiskit", timeout_s))["error"]


def _rewrite(*messages):
    return call_js(["run_status.js"], [("userFacingError", [m]) for m in messages])


def test_dispatcher_messages_lose_operator_instructions():
    messages = [
        _error(httpx.ConnectError("refused")),
        _error(httpx.TimeoutException("slow")),
        _error(httpx.RemoteProtocolError("peer closed"), timeout_s=0),
        _error(httpx.ReadError("reset"), timeout_s=10**9),
        "The runner pod exited with an error before returning a result (likely out of memory or time). "
        "Server operators can see details in the runner pod logs.",
    ]
    rewritten = _rewrite(*messages)
    for original, text in zip(messages, rewritten):
        assert "Server operators" not in text, text
        assert text != original or "raise the timeout" not in original
    assert "try again in a minute" in rewritten[0]
    assert "raise the timeout in the Execution chip." in rewritten[1]
    assert all("administrator" in t for t in rewritten[2:])


def test_messages_without_hints_are_unchanged():
    msg = "Circuit uses reset ('reset q[0]')."
    assert _rewrite(msg, None) == [msg, None]
