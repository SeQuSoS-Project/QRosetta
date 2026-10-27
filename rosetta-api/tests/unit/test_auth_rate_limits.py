"""Sign-in and registration are rate-limited per client address: a 429 with Retry-After once
the limit is used up, counted before the password is checked, and declared in OpenAPI."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from limits import parse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import services.accounts as accounts
from config import settings
from db.database import Base, get_db
from routers import auth
from routers.errors import register_error_handlers
from routers.rate_limit import RateLimitHeaders
from services.security import limiter

LOGIN_LIMIT = parse(settings.LOGIN_RATE_LIMIT).amount
REGISTER_LIMIT = parse(settings.REGISTER_RATE_LIMIT).amount


@pytest.fixture
def client():
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
    app.state.limiter = limiter
    register_error_handlers(app)
    app.add_middleware(RateLimitHeaders)
    app.include_router(auth.router)
    app.dependency_overrides[get_db] = _get_db
    limiter.reset()
    yield TestClient(app)
    limiter.reset()
    engine.dispose()


def _login(client, password="wrongpass1", address=None):
    headers = {"X-Forwarded-For": address} if address else {}
    return client.post("/auth/token", data={"username": "user@example.org", "password": password},
                       headers=headers)


def _register(client, i, address=None):
    headers = {"X-Forwarded-For": address} if address else {}
    return client.post("/auth/register", json={"email": f"user{i}@example.org", "password": "testpass123"},
                       headers=headers)


def test_the_limits_are_per_minute():
    assert parse(settings.LOGIN_RATE_LIMIT).GRANULARITY.name == "minute"
    assert parse(settings.REGISTER_RATE_LIMIT).GRANULARITY.name == "minute"
    assert 1 <= REGISTER_LIMIT <= LOGIN_LIMIT


def test_login_attempts_past_the_limit_get_429_with_retry_after(client):
    assert client.post("/auth/register", json={"email": "user@example.org",
                                                "password": "testpass123"}).status_code == 201
    codes = [_login(client).status_code for _ in range(LOGIN_LIMIT)]
    assert codes == [401] * LOGIN_LIMIT
    r = _login(client, password="testpass123")
    assert r.status_code == 429
    assert 1 <= int(r.headers["Retry-After"]) <= 60
    assert r.headers["X-RateLimit-Limit"] == str(LOGIN_LIMIT)
    assert r.headers["X-RateLimit-Remaining"] == "0"
    assert "access_token" not in r.text


def test_login_responses_carry_the_rate_limit_headers(client):
    r = _login(client)
    assert r.status_code == 401
    assert r.headers["X-RateLimit-Limit"] == str(LOGIN_LIMIT)
    assert r.headers["X-RateLimit-Remaining"] == str(LOGIN_LIMIT - 1)


def test_a_refused_login_never_reaches_the_password_check(client, monkeypatch):
    calls = []

    def _authenticate(db, email, password):
        calls.append(email)
        raise accounts.InvalidCredentials()

    monkeypatch.setattr(accounts, "authenticate", _authenticate)
    for _ in range(LOGIN_LIMIT + 3):
        _login(client)
    assert len(calls) == LOGIN_LIMIT


def test_registrations_past_the_limit_get_429(client):
    codes = [_register(client, i).status_code for i in range(REGISTER_LIMIT + 1)]
    assert codes == [201] * REGISTER_LIMIT + [429]
    assert "Retry-After" in _register(client, 99).headers


def test_each_client_address_has_its_own_counters(client):
    for _ in range(LOGIN_LIMIT):
        _login(client, address="203.0.113.1")
    assert _login(client, address="203.0.113.1").status_code == 429
    assert _login(client, address="203.0.113.2").status_code == 401
    for i in range(REGISTER_LIMIT):
        _register(client, i, address="203.0.113.1")
    assert _register(client, 50, address="203.0.113.1").status_code == 429
    assert _register(client, 51, address="203.0.113.2").status_code == 201


def test_login_and_register_declare_429_in_openapi():
    from main import app
    paths = app.openapi()["paths"]
    assert "429" in paths["/auth/token"]["post"]["responses"]
    assert "429" in paths["/auth/register"]["post"]["responses"]
