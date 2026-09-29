"""Registration and login input validation: email format/length/case, password length."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base, get_db
from routers import auth

_engine = create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
_Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
Base.metadata.create_all(bind=_engine)


def _get_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(auth.router)
    app.dependency_overrides[get_db] = _get_db
    return TestClient(app)


@pytest.mark.parametrize("email,password", [
    ("", "longenough"),
    ("valid@example.org", ""),
    ("<script>alert(1)</script>", "longenough"),
    ("a" * 5000 + "@example.org", "longenough"),
    ("no-at-sign.example.org", "longenough"),
    ("short@example.org", "1234567"),
    ("long@example.org", "x" * 73),
    ("multibyte@example.org", "é" * 37),
])
def test_register_rejects_invalid_input(client, email, password):
    r = client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code == 422, r.text


def test_email_is_case_insensitive(client):
    r = client.post("/auth/register", json={"email": "Mixed.Case@Example.org", "password": "testpass123"})
    assert r.status_code == 201 and r.json()["email"] == "mixed.case@example.org"
    r = client.post("/auth/register", json={"email": "MIXED.case@example.ORG", "password": "testpass123"})
    assert r.status_code == 400
    r = client.post("/auth/token", data={"username": "MIXED.CASE@example.org", "password": "testpass123"})
    assert r.status_code == 200


def test_login_with_overlong_password_is_400(client):
    r = client.post("/auth/token", data={"username": "x@example.org", "password": "p" * 100})
    assert r.status_code == 400 and "72 bytes" in r.json()["detail"]


def test_72_byte_password_is_accepted(client):
    r = client.post("/auth/register", json={"email": "max@example.org", "password": "p" * 72})
    assert r.status_code == 201
