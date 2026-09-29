"""A deactivated user (User.is_active=False) cannot log in, and existing tokens are rejected."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import db.models as models
from db.database import Base, get_db
from routers import auth

_engine = create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
_TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
Base.metadata.create_all(bind=_engine)


def _override_get_db():
    db = _TestingSessionLocal()
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


def _register(client, email):
    r = client.post("/auth/register", json={"email": email, "password": "testpass123"})
    assert r.status_code == 201, r.text


def _login(client, email):
    return client.post("/auth/token", data={"username": email, "password": "testpass123"})


def _deactivate(email):
    db = _TestingSessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).one()
        user.is_active = False
        db.commit()
    finally:
        db.close()


def test_new_account_is_active_and_can_log_in(client):
    _register(client, "active@example.com")
    assert _login(client, "active@example.com").status_code == 200


def test_deactivated_account_cannot_log_in(client):
    email = "deactivated@example.com"
    _register(client, email)
    assert _login(client, email).status_code == 200

    _deactivate(email)

    resp = _login(client, email)
    assert resp.status_code == 403
    assert "deactivated" in resp.json()["detail"].lower()


def test_existing_token_stops_working_after_deactivation(client):
    email = "revoked@example.com"
    _register(client, email)
    token = _login(client, email).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/auth/me", headers=headers).status_code == 200

    _deactivate(email)

    assert client.get("/auth/me", headers=headers).status_code == 403
