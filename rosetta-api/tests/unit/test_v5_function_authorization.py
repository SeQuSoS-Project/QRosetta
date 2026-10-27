"""Function-level authorization (OWASP API5): bypass_limits needs an active, signed-in account
outside local mode; the host-load route answers 404 to everything but the lifecycle token; fresh
probes need a valid sign-in or the lifecycle token; the self-test plan starts nothing; CORS
preflights from other origins are not allowed."""
import pytest

import services.job_manager as job_manager
from config import settings
from tests.unit.authz_world import world

QASM = "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[1];\nh q[0];\n"
NOT_QASM = "this is not a circuit"
LIFECYCLE = "lifecycle-token-for-v5-tests"

BYPASS_ROUTES = {
    "/compare": {"qasm_string": NOT_QASM, "target_simulators": ["qiskit"], "bypass_limits": True},
    "/compare_measured": {"qasm_string": NOT_QASM, "target_simulators": ["qiskit"], "bypass_limits": True},
    "/run_batch_suite": {"tasks": [{"qasm_string": NOT_QASM, "name": "x"}], "target_simulators": ["qiskit"],
                         "mode": "statevector", "bypass_limits": True},
}


@pytest.fixture
def w(tmp_path, monkeypatch):
    token_file = tmp_path / "lifecycle.token"
    token_file.write_text(LIFECYCLE + "\n")
    monkeypatch.setenv("QROSETTA_LIFECYCLE_TOKEN_FILE", str(token_file))
    with world(tmp_path, monkeypatch) as built:
        yield built


def _identities(w):
    active, off, out = w.user(), w.user(), w.user()
    signed_out = w.token(out)
    assert w.client.post("/auth/logout", headers={"Authorization": f"Bearer {signed_out}"}).status_code == 204
    headers = {"anonymous": {}, "active": w.headers(active), "deactivated": w.headers(off),
               "signed_out": {"Authorization": f"Bearer {signed_out}"},
               "lifecycle": {"Authorization": f"Bearer {LIFECYCLE}"},
               "garbage": {"Authorization": "Bearer not-a-token"}}
    w.set_active(off, False)
    return headers


@pytest.mark.parametrize("route", sorted(BYPASS_ROUTES))
def test_bypass_limits_needs_an_active_account_outside_local_mode(w, monkeypatch, route):
    monkeypatch.setattr(settings, "EXECUTION_MODE", "kubernetes")
    headers = _identities(w)
    jobs_before = set(job_manager.ACTIVE_JOBS)
    for who in ("anonymous", "deactivated", "signed_out", "lifecycle", "garbage"):
        answer = w.client.post(route, json=BYPASS_ROUTES[route], headers=headers[who])
        assert answer.status_code == 401, (who, answer.text)
        assert answer.headers["www-authenticate"] == "Bearer"
    passed = w.client.post(route, json=BYPASS_ROUTES[route], headers=headers["active"])
    assert passed.status_code == 400, passed.text
    assert set(job_manager.ACTIVE_JOBS) == jobs_before


def test_bypass_limits_is_open_to_anyone_in_local_mode(w, monkeypatch):
    monkeypatch.setattr(settings, "EXECUTION_MODE", "local")
    answer = w.client.post("/compare", json=BYPASS_ROUTES["/compare"])
    assert answer.status_code == 400, answer.text
    assert w.client.get("/config").json()["bypass_limits_requires_account"] is False


@pytest.mark.parametrize("who", ["anonymous", "active", "deactivated", "signed_out", "garbage"])
def test_the_host_load_route_is_invisible_without_the_lifecycle_token(w, who):
    headers = _identities(w)
    answer = w.client.post("/local/host-load", json={"action": "open", "kind": "build"}, headers=headers[who])
    assert answer.status_code == 404 and answer.json() == {"detail": "Not Found"}
    unknown = w.client.post("/local/no-such-route", json={}, headers=headers[who])
    assert unknown.status_code == 404


def test_the_host_load_route_is_not_in_the_api_description(w):
    assert "/local/host-load" not in w.client.get("/openapi.json").json()["paths"]


@pytest.mark.parametrize("who, status", [("anonymous", 401), ("garbage", 401), ("signed_out", 401),
                                         ("deactivated", 403)])
def test_fresh_probes_need_a_valid_sign_in(w, monkeypatch, who, status):
    import db.database
    import services.fresh_probes as fresh_probes
    monkeypatch.setattr(db.database, "SessionLocal", w.session)
    probed = []

    async def _no_round(*args, **kwargs):
        probed.append(args)
        return {}
    monkeypatch.setattr(fresh_probes, "fresh_round", _no_round)
    fresh_probes.reset()
    headers = _identities(w)
    for kind in ("runners", "compilers"):
        answer = w.client.get(f"/{kind}?fresh=true", headers=headers[who])
        assert answer.status_code == status, (kind, answer.text)
    assert probed == []


def test_the_self_test_plan_starts_nothing(w):
    before = set(job_manager.ACTIVE_JOBS)
    answer = w.client.get("/selftest")
    assert answer.status_code == 200
    assert set(job_manager.ACTIVE_JOBS) == before


@pytest.mark.parametrize("origin", ["https://evil.example", "null", "http://localhost:9999",
                                    "http://127.0.0.1.evil.example"])
@pytest.mark.parametrize("path", ["/compare", "/auth/token", "/history/runs", "/auth/logout"])
def test_cors_preflights_from_other_origins_are_not_allowed(w, origin, path):
    answer = w.client.options(path, headers={"Origin": origin, "Access-Control-Request-Method": "POST",
                                             "Access-Control-Request-Headers": "authorization,content-type"})
    assert answer.status_code == 400
    assert "access-control-allow-origin" not in answer.headers


@pytest.mark.parametrize("origin", ["https://evil.example", "null"])
def test_simple_requests_from_other_origins_get_no_allow_origin(w, origin):
    answer = w.client.get("/config", headers={"Origin": origin})
    assert "access-control-allow-origin" not in answer.headers


def test_the_redoc_script_from_the_cdn_carries_its_integrity_hash(w):
    from routers.security_headers import REDOC_SCRIPT_INTEGRITY, REDOC_SCRIPT_URL
    page = w.client.get("/redoc").text
    assert page.count("<script src=") == 1
    assert (f'<script src="{REDOC_SCRIPT_URL}" integrity="{REDOC_SCRIPT_INTEGRITY}" '
            'crossorigin="anonymous">') in page
