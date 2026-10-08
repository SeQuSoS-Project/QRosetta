"""OpenAPI contract: every status code a route can raise is declared in /openapi.json, and
the shared 401/413/429 machinery is declared and sends its headers."""
import ast
import inspect
import re
import textwrap

import pytest

pytest.importorskip("pytket")

from fastapi import HTTPException  # noqa: E402
from fastapi.routing import APIRoute  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

_OWN_MODULES = ("services.", "routers.")


def _status_of(node) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    text = ast.unparse(node)
    match = re.search(r"HTTP_(\d{3})_", text)
    return int(match.group(1)) if match else None


def _callee(node, scope: dict):
    if isinstance(node, ast.Name):
        return scope.get(node.id)
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        owner = scope.get(node.value.id)
        return getattr(owner, node.attr, None) if inspect.ismodule(owner) else None
    return None


def raised_codes(func, seen=None) -> set:
    """Status codes of every ``HTTPException`` raised by ``func`` and by the functions of
    this code base it calls (static, so a superset of what one request can return)."""
    seen = set() if seen is None else seen
    func = inspect.unwrap(func)
    if func in seen or not inspect.isfunction(func):
        return set()
    seen.add(func)
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    except (OSError, TypeError):
        return set()
    codes = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = _callee(node.func, func.__globals__)
        if target is HTTPException:
            for kw in node.keywords:
                if kw.arg == "status_code" and _status_of(kw.value):
                    codes.add(_status_of(kw.value))
            if node.args and _status_of(node.args[0]):
                codes.add(_status_of(node.args[0]))
        elif inspect.isfunction(target) and target.__module__.startswith(_OWN_MODULES):
            codes |= raised_codes(target, seen)
    return codes


def _routes():
    return [r for r in app.routes if isinstance(r, APIRoute) and r.include_in_schema]


@pytest.fixture(scope="module")
def spec():
    app.openapi_schema = None
    return TestClient(app).get("/openapi.json").json()


@pytest.mark.parametrize("route", _routes(), ids=lambda r: f"{sorted(r.methods)[0]} {r.path}")
def test_every_raised_status_code_is_declared(route, spec):
    declared = {int(code) for code in
                spec["paths"][route.path][sorted(route.methods)[0].lower()]["responses"]}
    missing = raised_codes(route.endpoint) - declared - {500}
    assert not missing, f"{route.path} raises {sorted(missing)} without declaring them"


@pytest.mark.parametrize("route", _routes(), ids=lambda r: f"{sorted(r.methods)[0]} {r.path}")
def test_body_routes_declare_413(route, spec):
    if route.body_field is None:
        pytest.skip("no request body")
    responses = spec["paths"][route.path][sorted(route.methods)[0].lower()]["responses"]
    assert "413" in responses


def test_job_404_wording_only_on_job_routes(spec):
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            text = op["responses"].get("404", {}).get("description", "")
            if "{job_id}" not in path:
                assert "job id" not in text, (method, path, text)


def test_authenticated_and_rate_limited_routes_declare_401_and_429(spec):
    paths = spec["paths"]
    assert "401" in paths["/history/runs"]["get"]["responses"]
    assert "401" in paths["/auth/me"]["get"]["responses"]
    for path, method in [("/compare", "post"), ("/jobs/{job_id}/report", "get"),
                         ("/shared/circuits", "post"), ("/generate_circuit", "post")]:
        assert "429" in paths[path][method]["responses"], path
        assert "Retry-After" in paths[path][method]["responses"]["429"]["description"]


def test_rate_limited_routes_send_rate_limit_headers_and_retry_after():
    client = TestClient(app)
    headers = {"x-forwarded-for": "203.0.113.77"}
    first = client.get("/jobs/no-such-job/report", headers=headers)
    assert first.status_code == 404
    assert first.headers["X-RateLimit-Limit"] == "30"
    assert int(first.headers["X-RateLimit-Remaining"]) == 29
    for _ in range(30):
        last = client.get("/jobs/no-such-job/report", headers=headers)
    assert last.status_code == 429
    assert 1 <= int(last.headers["Retry-After"]) <= 60
    assert last.headers["X-RateLimit-Remaining"] == "0"
    assert last.json()["detail"].startswith("Rate limit exceeded")


def test_unlimited_routes_carry_no_rate_limit_headers():
    assert "X-RateLimit-Limit" not in TestClient(app).get("/config").headers


def test_exclusive_slot_429_has_retry_after(monkeypatch):
    import services.job_manager as job_manager
    monkeypatch.setattr(job_manager.settings, "EXCLUSIVE_ENABLED", True)
    monkeypatch.setattr(job_manager, "claim_exclusive", lambda client, job_id: "held-job")

    class Payload:
        exclusive = True
    with pytest.raises(HTTPException) as caught:
        job_manager.require_exclusive_slot(Payload(), "c", "j")
    assert caught.value.status_code == 429
    assert caught.value.headers["Retry-After"] == str(job_manager.EXCLUSIVE_RETRY_AFTER_SEC)
