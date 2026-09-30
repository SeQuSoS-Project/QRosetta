"""Access tokens are bound to the account id and issue time: a token of a deleted account
does not authenticate a new account registered with the same email."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import db.models as models
from db.database import Base, get_db
from routers import auth
from services import security

_engine = create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
Base.metadata.create_all(bind=_engine)


def _override_get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(auth.router)
    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


def _register_and_login(client, email):
    assert client.post("/auth/register", json={"email": email, "password": "testpass123"}).status_code == 201
    r = client.post("/auth/token", data={"username": email, "password": "testpass123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _me(client, token):
    return client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})


def test_token_carries_uid_and_iat(client):
    token = _register_and_login(client, "claims@example.com")
    claims = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
    assert claims["sub"] == "claims@example.com"
    assert isinstance(claims["uid"], int)
    assert isinstance(claims["iat"], int)
    assert _me(client, token).status_code == 200


def test_deleted_account_token_rejected_for_reregistered_email(client):
    old = _register_and_login(client, "reuse@example.com")
    assert client.delete("/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code == 204
    assert _me(client, old).status_code == 401

    db = _Session()
    try:
        db.add(models.User(email="reuse@example.com", hashed_password=security.get_password_hash("testpass123"),
                           created_at=datetime.now(timezone.utc) + timedelta(seconds=10)))
        db.commit()
    finally:
        db.close()
    assert _me(client, old).status_code == 401


def test_token_without_uid_rejected(client):
    _register_and_login(client, "legacy@example.com")
    legacy = security.create_access_token({"sub": "legacy@example.com"})
    assert _me(client, legacy).status_code == 401


def test_token_with_other_uid_rejected(client):
    _register_and_login(client, "other-uid@example.com")
    forged = security.create_access_token({"sub": "other-uid@example.com", "uid": 999999})
    assert _me(client, forged).status_code == 401


def test_token_matches_account_rules():
    now = datetime.now(timezone.utc)
    user = SimpleNamespace(id=7, created_at=now.replace(tzinfo=None))
    iat = int(now.timestamp())
    assert security.token_matches_account({"uid": 7, "iat": iat}, user)
    assert not security.token_matches_account({"uid": 8, "iat": iat}, user)
    assert not security.token_matches_account({"uid": True, "iat": iat}, user)
    assert not security.token_matches_account({"uid": 7}, user)
    assert not security.token_matches_account({"uid": 7, "iat": iat - 60}, user)
