"""End-to-end smoke test through nginx, as the page and a share-link reader use the stack:
routing, an account, QFT-4 in both modes on a few runners with known answers, the Summary,
a saved run, a share link from creation to revocation, sign-out, and account deletion.

The account is overnight-e2e-<random>@example.invalid, created and deleted here. Run against
the live stack:
    python -m pytest tests/integration/test_e2e_nginx.py

Servers before the 2026-10-28 hardening (no `readiness` feature in GET /config) do not check
Origin or Content-Type, send no security headers and delete an account without its password;
those checks are skipped there, and so is sign-out on a server without the `logout` feature.
QROSETTA_E2E_REQUIRE_CURRENT=1 requires all of them whatever the server says (CI, where the
images are built from the commit under test).
"""

import math
import os
import secrets

import httpx
import pytest
from qrosetta_commons.contract_probes import decode_complex128_base64

from live_stack import BASE_URL, ORIGIN, poll_job, selected_runners, send

RUNNERS = selected_runners(["qiskit", "qulacs", "cirq"])
QFT_QUBITS = 4
SEED = 20261028
CURRENT_FEATURE = "readiness"
LOGOUT_FEATURE = "logout"
CROSS_SITE_DETAIL = "Requests from other sites are refused."
SHARE_GONE_DETAIL = "This link does not exist, has expired or was revoked."
NOT_SHARED = {
    "statevector",
    "counts",
    "error",
    "simulation_time_sec",
    "compilation_time_sec",
    "memory_usage_mb",
    "user_id",
    "email",
    "owner_user_id",
    "job_id",
}
DIFFERENCE = "difference"
AGREEMENT = "agreement"


def _require_current() -> bool:
    return os.environ.get("QROSETTA_E2E_REQUIRE_CURRENT", "") not in ("", "0")


def required(feature: str, features) -> bool:
    """Whether the checks of ``feature`` run: the server lists it, or the current checks are required."""
    return _require_current() or feature in (features or {})


def server_state(config: dict) -> dict:
    """GET /config's answer, its features, and which of the newer checks run against it."""
    features = (config.get("server") or {}).get("features") or {}
    return {
        "config": config,
        "features": features,
        "current": required(CURRENT_FEATURE, features),
        "logout": required(LOGOUT_FEATURE, features),
    }


@pytest.fixture(scope="module")
def server():
    """GET /config, and whether the server has the current request and header checks and sign-out."""
    resp = httpx.get(f"{BASE_URL}/config", timeout=10)
    assert resp.status_code == 200, resp.text
    state = server_state(resp.json())
    sha = state["config"]["server"].get("git_sha")
    print(f"  server {sha} at {BASE_URL}; current checks: {state['current']}; sign-out: {state['logout']}")
    return state


@pytest.fixture(scope="module")
def browser():
    """A client that sends what the page sends: its own Origin."""
    with httpx.Client(timeout=30, headers={"Origin": ORIGIN}) as client:
        yield client


@pytest.fixture(scope="module")
def account(browser):
    """A fresh account and its bearer token; deleted at the end if a test has not done so, signing
    in again when a sign-out ended the token."""
    email = f"overnight-e2e-{secrets.token_hex(6)}@example.invalid"
    password = secrets.token_urlsafe(18)
    resp = send(browser, "POST", "/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    assert resp.json()["email"] == email
    resp = send(browser, "POST", "/auth/token", data={"username": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    state = {
        "email": email,
        "password": password,
        "token": token,
        "auth": {"Authorization": f"Bearer {token}"},
        "deleted": False,
    }
    yield state
    if not state["deleted"]:
        gone = browser.request("DELETE", f"{BASE_URL}/auth/me", headers=state["auth"], json={"password": password})
        if gone.status_code == 401:
            again = send(browser, "POST", "/auth/token", data={"username": email, "password": password})
            if again.status_code == 200:
                auth = {"Authorization": f"Bearer {again.json()['access_token']}"}
                browser.request("DELETE", f"{BASE_URL}/auth/me", headers=auth, json={"password": password})


def _keys(value) -> set:
    if isinstance(value, dict):
        return set(value).union(*(_keys(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(_keys(v) for v in value))
    return set()


def _content_type(resp: httpx.Response) -> str:
    return resp.headers.get("content-type", "").split(";")[0].strip()


def test_routing_through_nginx():
    with httpx.Client(timeout=30) as client:
        page = client.get(f"{BASE_URL}/")
        assert page.status_code == 200 and _content_type(page) == "text/html"
        assert 'type="module" src="js/main.js' in page.text

        swagger = client.get(f"{BASE_URL}/docs")
        assert swagger.status_code == 200 and _content_type(swagger) == "text/html"
        assert "swagger-ui" in swagger.text.lower()

        manual = client.get(f"{BASE_URL}/docs.html")
        assert manual.status_code == 200 and _content_type(manual) == "text/html"
        assert "<title>QRosetta Documentation</title>" in manual.text
        assert "swagger-ui" not in manual.text.lower()

        spec = client.get(f"{BASE_URL}/openapi.json")
        assert spec.status_code == 200 and "/compare" in spec.json()["paths"]

        missing = client.get(f"{BASE_URL}/no-such-route-{secrets.token_hex(4)}")
        assert missing.status_code == 404
        assert _content_type(missing) == "application/json"
        assert "detail" in missing.json()


def test_health_and_readiness(server):
    if not (server["current"] or "readiness" in server["features"]):
        pytest.skip("this server has no /health or /ready")
    with httpx.Client(timeout=10) as client:
        health = client.get(f"{BASE_URL}/health")
        assert health.status_code == 200 and health.json() == {"status": "ok"}
        ready = client.get(f"{BASE_URL}/ready")
        assert ready.status_code == 200, ready.text
        assert ready.json()["status"] == "ready"


def test_browser_security_checks(server, browser):
    if not server["current"]:
        pytest.skip("this server predates the Origin, Content-Type and header checks")
    page = browser.get(f"{BASE_URL}/")
    assert "default-src 'self'" in page.headers.get("content-security-policy", "")
    assert page.headers.get("x-content-type-options") == "nosniff"
    config = browser.get(f"{BASE_URL}/config")
    assert "default-src 'none'" in config.headers.get("content-security-policy", "")

    foreign = httpx.post(f"{BASE_URL}/plan", json={}, headers={"Origin": "https://evil.example"}, timeout=10)
    assert foreign.status_code == 403 and foreign.json()["detail"] == CROSS_SITE_DETAIL

    not_json = browser.post(f"{BASE_URL}/plan", content=b"{}", headers={"Content-Type": "text/plain"})
    assert not_json.status_code == 415, not_json.text


def _qft_text(browser, account) -> str:
    resp = send(
        browser, "POST", "/generate_circuit", headers=account["auth"], json={"algorithm": "qft", "qubits": QFT_QUBITS}
    )
    assert resp.status_code == 200, resp.text
    qasm = resp.json()["qasm"]
    assert f"qreg q[{QFT_QUBITS}];" in qasm
    return qasm


def _run(browser, account, endpoint: str, payload: dict) -> dict:
    body = {"target_simulators": RUNNERS, "timeout_seconds": 120, **payload}
    resp = send(browser, "POST", endpoint, headers=account["auth"], json=body)
    assert resp.status_code == 200, resp.text
    job = poll_job(browser, resp.json()["job_id"])
    assert job["status"] == "completed", job.get("error")
    return job


def _check_summary(browser, job_id: str, n_backends: int) -> dict:
    resp = browser.get(f"{BASE_URL}/jobs/{job_id}/summary")
    assert resp.status_code == 200, resp.text
    summary = resp.json()
    roles = summary["outcome_roles"]
    by_role = {}
    for name, count in summary["outcomes"].items():
        by_role[roles.get(name)] = by_role.get(roles.get(name), 0) + count
    pairs = n_backends * (n_backends - 1) // 2
    assert summary["runs"] == {
        "total": n_backends,
        "returned": n_backends,
        "without_output": 0,
        "circuit_failed": False,
    }, summary["runs"]
    assert by_role.get(DIFFERENCE, 0) == 0, summary["pair_verdicts"]
    assert by_role.get(AGREEMENT, 0) == pairs, summary["pair_verdicts"]
    return summary


def test_qft_save_share_revoke(browser, account):
    qasm = _qft_text(browser, account)
    uniform = 1 / math.sqrt(2**QFT_QUBITS)

    statevector = _run(browser, account, "/compare", {"qasm_string": qasm})
    raw = {r["simulator"]: r for r in statevector["results"]["raw_results"]}
    assert sorted(raw) == sorted(RUNNERS)
    for name, result in raw.items():
        assert result.get("dispatch_status", "ok") == "ok", (name, result.get("error"))
        amplitudes = decode_complex128_base64(result["statevector"])
        assert len(amplitudes) == 2**QFT_QUBITS, name
        assert all(abs(abs(a) - uniform) < 1e-6 for a in amplitudes), name
    _check_summary(browser, statevector["job_id"], len(RUNNERS))

    measured = _run(browser, account, "/compare_measured", {"qasm_string": qasm, "seed": SEED})
    assert measured["results"]["seed"] == SEED
    n_shots = measured["results"]["n_shots"]
    for result in measured["results"]["raw_results"]:
        counts = result["counts"]
        assert sum(counts.values()) == n_shots, result["simulator"]
        assert all(len(key) == QFT_QUBITS for key in counts), result["simulator"]
    _check_summary(browser, measured["job_id"], len(RUNNERS))

    run_name = f"e2e QFT-{QFT_QUBITS}"
    saved = send(
        browser,
        "POST",
        f"/history/runs/from_job/{statevector['job_id']}",
        headers=account["auth"],
        json={"run_name": run_name},
    )
    assert saved.status_code == 201, saved.text
    run_id = saved.json()["id"]
    runs = browser.get(f"{BASE_URL}/history/runs", headers=account["auth"])
    assert [r["id"] for r in runs.json()] == [run_id]
    run_summary = browser.get(f"{BASE_URL}/history/runs/{run_id}/summary", headers=account["auth"])
    assert run_summary.status_code == 200 and run_summary.json()["report_source"] == "saved_run"

    created = send(
        browser,
        "POST",
        f"/history/runs/{run_id}/share-links",
        headers=account["auth"],
        json={"expires_in_days": 1, "label": "e2e"},
    )
    assert created.status_code == 201, created.text
    assert created.headers.get("cache-control") == "no-store"
    link = created.json()
    assert link["active"] is True and link["token"]

    share_page = browser.get(f"{BASE_URL}/share.html")
    assert share_page.status_code == 200 and _content_type(share_page) == "text/html"
    assert "js/share_main.js" in share_page.text
    script = browser.get(f"{BASE_URL}/js/share_main.js")
    assert script.status_code == 200 and "/shared/circuits" in script.text

    reader = httpx.Client(timeout=30, headers={"Origin": ORIGIN})
    try:
        opened = send(reader, "POST", "/shared/circuits", json={"token": link["token"]})
        assert opened.status_code == 200, opened.text
        assert opened.headers.get("cache-control") == "no-store"
        shared = opened.json()
        assert shared.get("run_name") == run_name
        assert f"qreg q[{QFT_QUBITS}];" in str(shared)
        assert not _keys(shared) & NOT_SHARED, _keys(shared) & NOT_SHARED

        listed = browser.get(f"{BASE_URL}/history/runs/{run_id}/share-links", headers=account["auth"])
        assert [(entry["id"], entry["active"]) for entry in listed.json()] == [(link["id"], True)]
        assert "token" not in listed.json()[0]

        revoked = browser.request("DELETE", f"{BASE_URL}/history/share-links/{link['id']}", headers=account["auth"])
        assert revoked.status_code == 200 and revoked.json()["active"] is False

        gone = send(reader, "POST", "/shared/circuits", json={"token": link["token"]})
        assert gone.status_code == 404 and gone.json()["detail"] == SHARE_GONE_DETAIL
    finally:
        reader.close()

    second = send(browser, "POST", f"/history/runs/{run_id}/share-links", headers=account["auth"], json={})
    assert second.status_code == 201, second.text
    account["open_link"] = second.json()["token"]


def test_sign_out_ends_the_token(server, browser, account):
    if not server["logout"]:
        pytest.skip("this server has no POST /auth/logout")
    old_auth = account["auth"]
    out = send(browser, "POST", "/auth/logout", headers=old_auth)
    assert out.status_code == 204, out.text
    assert browser.get(f"{BASE_URL}/auth/me", headers=old_auth).status_code == 401
    assert browser.get(f"{BASE_URL}/history/runs", headers=old_auth).status_code == 401

    login = send(browser, "POST", "/auth/token", data={"username": account["email"], "password": account["password"]})
    assert login.status_code == 200, login.text
    account["token"] = login.json()["access_token"]
    account["auth"] = {"Authorization": f"Bearer {account['token']}"}
    me = browser.get(f"{BASE_URL}/auth/me", headers=account["auth"])
    assert me.status_code == 200 and me.json()["email"] == account["email"], me.text


def test_account_deletion_ends_the_token_and_links(server, browser, account):
    if server["current"]:
        missing = browser.request("DELETE", f"{BASE_URL}/auth/me", headers=account["auth"])
        assert missing.status_code == 422, missing.text
        wrong = browser.request(
            "DELETE", f"{BASE_URL}/auth/me", headers=account["auth"], json={"password": account["password"] + "x"}
        )
        assert wrong.status_code == 403, wrong.text
        assert browser.get(f"{BASE_URL}/auth/me", headers=account["auth"]).status_code == 200

    deleted = browser.request(
        "DELETE", f"{BASE_URL}/auth/me", headers=account["auth"], json={"password": account["password"]}
    )
    assert deleted.status_code == 204, deleted.text
    account["deleted"] = True

    assert browser.get(f"{BASE_URL}/auth/me", headers=account["auth"]).status_code == 401
    assert browser.get(f"{BASE_URL}/history/runs", headers=account["auth"]).status_code == 401
    login = send(browser, "POST", "/auth/token", data={"username": account["email"], "password": account["password"]})
    assert login.status_code == 401

    if account.get("open_link"):
        gone = send(browser, "POST", "/shared/circuits", json={"token": account["open_link"]})
        assert gone.status_code == 404
