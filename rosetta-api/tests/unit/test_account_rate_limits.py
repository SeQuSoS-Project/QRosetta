"""Rate limits are counted per account for a bearer token this server signed and that has not
expired, else per client address; run, export and render routes add a ceiling per client
address; sign-in, registration and share-link reads stay per address."""
from datetime import timedelta

import jwt
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from routers.errors import register_error_handlers
from routers.rate_limit import RateLimitHeaders
from services.security import (address_ceiling_key, address_key, create_access_token,
                               limit_with_address_ceiling, limiter, rate_limit_key)

ADDRESS = "203.0.113.9"
OTHER_ADDRESS = "203.0.113.10"
LIMIT = 3
CEILING = 5


@limiter.limit(f"{LIMIT}/minute")
async def _plain(request: Request):
    return {"key": rate_limit_key(request)}


@limit_with_address_ceiling(f"{LIMIT}/minute", f"{CEILING}/minute")
async def _expensive(request: Request):
    return {"ok": True}


@limiter.limit(f"{LIMIT}/minute")
async def _per_job(request: Request, job_id: str):
    return {"job": job_id}


@pytest.fixture
def client():
    app = FastAPI()
    app.state.limiter = limiter
    register_error_handlers(app)
    app.add_middleware(RateLimitHeaders)
    app.add_api_route("/plain", _plain, methods=["GET"])
    app.add_api_route("/expensive", _expensive, methods=["GET"])
    app.add_api_route("/jobs/{job_id}/thing", _per_job, methods=["GET"])
    limiter.reset()
    yield TestClient(app)
    limiter.reset()


def _token(uid, email=None, **extra):
    return create_access_token({"sub": email or f"user{uid}@example.org", "uid": uid, **extra})


def _get(client, path, token=None, address=ADDRESS):
    headers = {"X-Forwarded-For": address}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.get(path, headers=headers)


def _codes(client, path, n, token=None, address=ADDRESS):
    return [_get(client, path, token, address).status_code for _ in range(n)]


def test_two_accounts_behind_one_address_have_separate_budgets(client):
    a, b = _token(1), _token(2)
    assert _codes(client, "/plain", LIMIT + 1, a) == [200] * LIMIT + [429]
    assert _codes(client, "/plain", LIMIT + 1, b) == [200] * LIMIT + [429]
    assert _codes(client, "/plain", LIMIT, None) == [200] * LIMIT


def test_two_tokens_of_one_account_share_its_budget(client):
    first, second = _token(7), _token(7, nonce=1)
    assert _codes(client, "/plain", 2, first) == [200, 200]
    assert _codes(client, "/plain", 2, second) == [200, 429]


def test_the_key_names_the_account_and_never_the_email(client):
    body = _get(client, "/plain", _token(42, "someone@example.org")).json()
    assert body["key"] == "account:42"
    assert _get(client, "/plain").json()["key"] == f"address:{ADDRESS}"


_REFUSED_TOKENS = {
    "not_a_jwt": lambda: "not-a-jwt",
    "other_key": lambda: jwt.encode({"sub": "x@example.org", "uid": 1, "iat": 0, "exp": 9999999999},
                                    "another-server-key-" + "x" * 32, algorithm="HS256"),
    "unsigned": lambda: jwt.encode({"sub": "x@example.org", "uid": 1, "iat": 0, "exp": 9999999999},
                                   None, algorithm="none"),
    "expired": lambda: create_access_token({"sub": "x@example.org", "uid": 1}, timedelta(seconds=-5)),
    "no_uid": lambda: create_access_token({"sub": "x@example.org"}),
    "string_uid": lambda: create_access_token({"sub": "x@example.org", "uid": "1"}),
    "bool_uid": lambda: create_access_token({"sub": "x@example.org", "uid": True}),
    "no_sub": lambda: create_access_token({"uid": 1}),
}


@pytest.mark.parametrize("kind", sorted(_REFUSED_TOKENS))
def test_a_token_this_server_would_not_accept_counts_against_the_address(client, kind):
    token = _REFUSED_TOKENS[kind]()
    assert _get(client, "/plain", token).json()["key"] == f"address:{ADDRESS}"
    assert _codes(client, "/plain", LIMIT - 1, None) == [200] * (LIMIT - 1)
    assert _get(client, "/plain", token).status_code == 429


def test_many_forged_tokens_do_not_mint_budgets(client):
    forged = [jwt.encode({"sub": f"u{i}@example.org", "uid": i, "iat": 0, "exp": 9999999999},
                         f"guess-{i}-" + "x" * 32, algorithm="HS256") for i in range(LIMIT + 1)]
    codes = [_get(client, "/plain", t).status_code for t in forged]
    assert codes == [200] * LIMIT + [429]


def test_the_lifecycle_token_has_its_own_budget(client, monkeypatch, tmp_path):
    token_file = tmp_path / "lifecycle.token"
    token_file.write_text("lifecycle-secret\n")
    monkeypatch.setenv("QROSETTA_LIFECYCLE_TOKEN_FILE", str(token_file))
    assert _get(client, "/plain", "lifecycle-secret").json()["key"] == "lifecycle"
    assert _codes(client, "/plain", LIMIT, "lifecycle-secret", OTHER_ADDRESS) == [200] * (LIMIT - 1) + [429]
    assert _codes(client, "/plain", LIMIT, None) == [200] * LIMIT
    assert _codes(client, "/plain", 1, "lifecycle-secret") == [429]


def test_the_address_ceiling_holds_across_accounts(client):
    assert _codes(client, "/expensive", LIMIT, _token(1)) == [200] * LIMIT
    assert _codes(client, "/expensive", CEILING - LIMIT + 1, _token(2)) == [200, 200, 429]
    assert _codes(client, "/expensive", 1, _token(3)) == [429]
    assert _codes(client, "/expensive", 1, _token(3), OTHER_ADDRESS) == [200]


def test_an_account_over_its_own_limit_leaves_the_ceiling_alone(client):
    a = _token(1)
    assert _codes(client, "/expensive", LIMIT + 4, a) == [200] * LIMIT + [429] * 4
    assert _codes(client, "/expensive", CEILING - LIMIT, _token(2)) == [200] * (CEILING - LIMIT)


def test_path_parameters_do_not_split_a_budget(client):
    codes = [_get(client, f"/jobs/job-{i}/thing", _token(1)).status_code for i in range(LIMIT + 1)]
    assert codes == [200] * LIMIT + [429]


def test_anonymous_requests_meet_the_key_limit_before_the_ceiling(client):
    assert _codes(client, "/expensive", LIMIT + 1) == [200] * LIMIT + [429]


def test_headers_report_the_limit_with_fewest_requests_left(client):
    r = _get(client, "/expensive", _token(1))
    assert r.headers["X-RateLimit-Limit"] == str(LIMIT)
    assert r.headers["X-RateLimit-Remaining"] == str(LIMIT - 1)
    _codes(client, "/expensive", LIMIT - 1, _token(1))
    r = _get(client, "/expensive", _token(2))
    assert r.headers["X-RateLimit-Limit"] == str(CEILING)
    assert r.headers["X-RateLimit-Remaining"] == str(CEILING - LIMIT - 1)
    _get(client, "/expensive", _token(2))
    r = _get(client, "/expensive", _token(2))
    assert r.status_code == 429
    assert r.headers["X-RateLimit-Limit"] == str(CEILING)
    assert r.headers["X-RateLimit-Remaining"] == "0"
    assert 1 <= int(r.headers["Retry-After"]) <= 60


def _key_funcs(endpoint):
    name = f"{endpoint.__module__}.{endpoint.__name__}"
    return {(lim.key_func, str(lim.limit)) for lim in limiter._route_limits[name]}


def test_run_export_and_render_routes_carry_the_address_ceiling():
    from limits import parse

    from config import settings
    from routers import benchmark, experiment, export, generation, publication
    run = {(rate_limit_key, str(parse(settings.RUN_RATE_LIMIT))),
           (address_ceiling_key, str(parse(settings.RUN_RATE_LIMIT_PER_ADDRESS)))}
    render = {(rate_limit_key, str(parse(settings.RENDER_RATE_LIMIT))),
              (address_ceiling_key, str(parse(settings.RENDER_RATE_LIMIT_PER_ADDRESS)))}
    for endpoint in (benchmark.compare_circuits_endpoint, benchmark.compare_measured_circuits_endpoint,
                     benchmark.run_batch_suite_endpoint, experiment.start_experiment,
                     export.export_ro_crate, export.export_job_ro_crate,
                     generation.generate_circuit_endpoint, generation.visualize_quirk,
                     generation.get_mqt_bench, generation.get_qasmbench):
        assert _key_funcs(endpoint) == run, endpoint.__name__
    for endpoint in (publication.publication_render, publication.job_publication_render):
        assert _key_funcs(endpoint) == render, endpoint.__name__


def test_sign_in_registration_and_share_reads_stay_per_address():
    from config import settings
    from routers import auth, share
    assert {f for f, _ in _key_funcs(auth.login_for_access_token)} == {address_key}
    assert {f for f, _ in _key_funcs(auth.register)} == {address_key}
    assert {f for f, _ in _key_funcs(share.read_shared_circuits)} == {address_key}
    assert settings.LOGIN_RATE_LIMIT and settings.REGISTER_RATE_LIMIT


def test_every_other_limited_route_keys_on_the_account():
    from main import app  # noqa: F401  (imports every router)
    per_address = {"routers.auth.login_for_access_token", "routers.auth.register",
                   "routers.share.read_shared_circuits"}
    for name, limits in limiter._route_limits.items():
        if not name.startswith("routers."):
            continue
        funcs = {lim.key_func for lim in limits}
        if name in per_address:
            assert funcs == {address_key}, name
        else:
            assert rate_limit_key in funcs and funcs <= {rate_limit_key, address_ceiling_key}, name


def test_address_keys_cannot_collide_with_account_keys(client):
    r = _get(client, "/plain", None, "account:1")
    assert r.json()["key"] == "address:account:1"
