"""V5-06: X-Forwarded-For names the client only when the socket peer is a trusted proxy
(QROSETTA_TRUSTED_PROXIES); a container sending straight to the API is keyed by its own address."""

import ipaddress
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from limits import parse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config import Settings, settings
from services import security, trusted_proxies
from services.security import address_key, client_address
from services.trusted_proxies import TrustedProxies, default_spec, peer_address

NGINX = "10.89.0.26"
RUNNER = "10.89.0.30"
API_ROOT = Path(__file__).resolve().parents[2]


def _resolver(table, calls=None):
    def resolve(host):
        if calls is not None:
            calls.append(host)
        return frozenset(ipaddress.ip_address(a) for a in table.get(host, ()))
    return resolve


@pytest.fixture
def nginx_trusted(monkeypatch):
    table = {"nginx": [NGINX]}
    monkeypatch.setattr(security, "TRUSTED_PROXIES", TrustedProxies("nginx", resolve=_resolver(table)))
    return table


def _req(headers, host):
    return SimpleNamespace(headers=headers, client=SimpleNamespace(host=host))


def test_v5_06_a_peer_outside_the_list_cannot_choose_its_key(nginx_trusted):
    for spoofed in ("198.51.100.1", "198.51.100.2", "6.6.6.6, 198.51.100.3"):
        assert client_address(_req({"x-forwarded-for": spoofed}, RUNNER)) == RUNNER
    assert address_key(_req({"x-forwarded-for": "198.51.100.9"}, RUNNER)) == "address:" + RUNNER


def test_v5_06_the_proxy_in_the_list_names_the_client(nginx_trusted):
    assert client_address(_req({"x-forwarded-for": "6.6.6.6, 198.51.100.2"}, NGINX)) == "198.51.100.2"
    assert client_address(_req({}, NGINX)) == NGINX
    assert client_address(_req({"x-forwarded-for": " "}, NGINX)) == NGINX


@pytest.mark.parametrize("peer", [RUNNER, NGINX])
def test_v5_06_the_proxy_token_path_does_not_depend_on_the_peer(nginx_trusted, monkeypatch, peer):
    monkeypatch.setattr(security.settings, "PROXY_TOKEN", "s3cret")
    headers = {"x-forwarded-for": "203.0.113.9, 34.1.2.3", "x-qrosetta-client-ip": "203.0.113.9",
               "x-qrosetta-proxy-token": "s3cret"}
    assert client_address(_req(headers, peer)) == "203.0.113.9"
    headers["x-qrosetta-proxy-token"] = "wrong"
    assert client_address(_req(headers, peer)) == ("34.1.2.3" if peer == NGINX else peer)


def _auth_app():
    from db.database import Base, get_db
    from routers import auth
    from routers.errors import register_error_handlers
    from routers.rate_limit import RateLimitHeaders

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def _get_db():
        db = session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.state.limiter = security.limiter
    register_error_handlers(app)
    app.add_middleware(RateLimitHeaders)
    app.include_router(auth.router)
    app.dependency_overrides[get_db] = _get_db
    return app, engine


@pytest.mark.parametrize("peer,limited", [(RUNNER, True), (NGINX, False)])
def test_v5_06_rotating_x_forwarded_for_on_sign_in(nginx_trusted, peer, limited):
    """V5's reproduction: failed sign-ins with a different X-Forwarded-For each. From a runner's
    address the 11th gets 429; from nginx's address each named client has its own count."""
    app, engine = _auth_app()
    security.limiter.reset()
    try:
        client = TestClient(app, client=(peer, 40000))
        limit = parse(settings.LOGIN_RATE_LIMIT).amount
        codes = [client.post("/auth/token", data={"username": "nobody@example.org", "password": "x" * 10},
                             headers={"X-Forwarded-For": f"198.51.100.{i}"}).status_code
                 for i in range(limit + 2)]
    finally:
        security.limiter.reset()
        engine.dispose()
    assert codes[:limit] == [401] * limit
    assert codes[limit:] == ([429, 429] if limited else [401, 401])


def test_v5_06_defaults_by_execution_mode():
    assert default_spec("local") == "nginx"
    assert default_spec("kubernetes") == "*"
    assert default_spec("something-else") == ""


def test_v5_06_the_setting_distinguishes_unset_from_empty(monkeypatch):
    monkeypatch.delenv("QROSETTA_TRUSTED_PROXIES", raising=False)
    assert Settings().TRUSTED_PROXIES is None
    monkeypatch.setenv("QROSETTA_TRUSTED_PROXIES", "")
    assert Settings().TRUSTED_PROXIES == ""
    monkeypatch.setenv("QROSETTA_TRUSTED_PROXIES", "10.0.0.0/8, nginx")
    assert Settings().TRUSTED_PROXIES == "10.0.0.0/8, nginx"


def test_v5_06_entries_any_address_network_and_empty():
    assert TrustedProxies("*").trusts("testclient")
    empty = TrustedProxies("")
    assert not empty.trusts("127.0.0.1") and not empty.trusts(NGINX)
    listed = TrustedProxies("10.89.0.0/24, 2001:db8::1", resolve=_resolver({}))
    assert listed.trusts(NGINX)
    assert listed.trusts("::ffff:10.89.0.7")
    assert listed.trusts("2001:db8::1")
    assert not listed.trusts("10.89.1.3")
    assert not listed.trusts("testclient")
    assert not listed.trusts(None)


def test_v5_06_peer_address_normalises():
    assert peer_address("::ffff:192.0.2.1") == ipaddress.ip_address("192.0.2.1")
    assert peer_address("fe80::1%eth0") == ipaddress.ip_address("fe80::1")
    assert peer_address("testclient") is None and peer_address("") is None


def test_v5_06_host_names_resolve_at_most_once_per_interval(monkeypatch):
    calls = []
    table = {"nginx": [NGINX]}
    proxies = TrustedProxies("nginx", resolve=_resolver(table, calls))
    clock = [1000.0]
    monkeypatch.setattr(trusted_proxies.time, "monotonic", lambda: clock[0])
    assert proxies.trusts(NGINX) and calls == ["nginx"]
    for _ in range(20):
        assert not proxies.trusts(RUNNER)
    assert proxies.trusts(NGINX) and calls == ["nginx"]
    table["nginx"] = ["10.89.0.40"]
    assert not proxies.trusts("10.89.0.40")
    clock[0] += trusted_proxies.RESOLVE_EVERY_SEC
    assert proxies.trusts("10.89.0.40") and not proxies.trusts(NGINX)
    assert len(calls) == 2


def test_v5_06_a_name_that_does_not_resolve_trusts_nobody():
    proxies = TrustedProxies("nginx", resolve=_resolver({}))
    assert not proxies.trusts(NGINX)


def test_v5_06_a_slow_resolver_holds_a_request_for_at_most_the_wait(monkeypatch):
    monkeypatch.setattr(trusted_proxies, "RESOLVE_WAIT_SEC", 0.05)
    release = threading.Event()

    def slow(host):
        release.wait(5)
        return frozenset({ipaddress.ip_address(NGINX)})

    proxies = TrustedProxies("nginx", resolve=slow)
    start = time.monotonic()
    assert not proxies.trusts(NGINX)
    assert time.monotonic() - start < 1.0
    release.set()
    deadline = time.monotonic() + 5
    while not proxies.trusts(NGINX) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert proxies.trusts(NGINX)


def test_v5_06_resolve_host_reads_the_system_resolver():
    assert ipaddress.ip_address("127.0.0.1") in trusted_proxies.resolve_host("localhost")


def test_v5_06_only_security_reads_the_peer_or_x_forwarded_for():
    """Every rate-limit key and the exclusive slot go through security.client_address."""
    readers = []
    for path in API_ROOT.rglob("*.py"):
        rel = path.relative_to(API_ROOT)
        if rel.parts[0] in ("tests", ".venv") or "site-packages" in rel.parts:
            continue
        text = path.read_text(encoding="utf-8").lower()
        if "x-forwarded-for" in text or "get_remote_address" in text or "request.client" in text:
            readers.append(str(rel))
    assert sorted(readers) == ["services/security.py", "services/trusted_proxies.py"]
    for router in ("benchmark.py", "experiment.py"):
        text = (API_ROOT / "routers" / router).read_text(encoding="utf-8")
        assert text.count("require_exclusive_slot(") == text.count("require_exclusive_slot(payload, client_address(request)")


def test_v5_06_config_publishes_nothing_about_the_proxies():
    from main import app
    body = TestClient(app).get("/config").text.lower()
    assert "trusted" not in body and "proxies" not in body and "proxy_token" not in body
