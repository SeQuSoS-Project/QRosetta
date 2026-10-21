"""Registration and login input validation: email format/length/case, password length."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base, get_db
from routers import auth
from routers.errors import register_error_handlers

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
    register_error_handlers(app)
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


def test_validation_error_does_not_echo_the_password(client):
    password = "secret-" + "p" * 70
    r = client.post("/auth/register", json={"email": "echo@example.org", "password": password})
    assert r.status_code == 422
    assert password not in r.text
    assert r.json()["detail"][0]["msg"] == "password must be at most 72 bytes (UTF-8)"


def test_register_rejects_unknown_fields(client):
    r = client.post("/auth/register", json={"email": "extra@example.org", "password": "testpass123",
                                            "is_admin": True})
    assert r.status_code == 422


def test_registration_that_loses_the_race_for_its_email_is_400(client, monkeypatch):
    import services.accounts as accounts
    assert client.post("/auth/register", json={"email": "twice@example.org",
                                               "password": "testpass123"}).status_code == 201
    monkeypatch.setattr(accounts, "_find_by_email", lambda db, email: None)
    r = client.post("/auth/register", json={"email": "Twice@example.org", "password": "otherpass123"})
    assert r.status_code == 400 and r.json()["detail"] == "Email already registered"
    monkeypatch.undo()
    r = client.post("/auth/token", data={"username": "twice@example.org", "password": "testpass123"})
    assert r.status_code == 200


def test_simultaneous_registrations_of_one_email_create_one_account(tmp_path, monkeypatch):
    import threading
    from sqlalchemy import func
    import db.models as models
    import services.accounts as accounts

    engine = create_engine(f"sqlite:///{tmp_path / 'accounts.db'}",
                           connect_args={"check_same_thread": False, "timeout": 10})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    checked = threading.Barrier(4, timeout=5)
    find = accounts._find_by_email
    outcomes = []

    def find_then_wait(db, email):
        found = find(db, email)
        checked.wait()
        return found

    def register():
        db = session()
        try:
            accounts.register(db, "same@example.org", "testpass123")
            outcomes.append("created")
        except accounts.EmailAlreadyRegistered:
            outcomes.append("taken")
        finally:
            db.close()

    monkeypatch.setattr(accounts, "_find_by_email", find_then_wait)
    threads = [threading.Thread(target=register) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(15)
    assert sorted(outcomes) == ["created", "taken", "taken", "taken"]
    db = session()
    try:
        assert db.query(func.count(models.User.id)).scalar() == 1
    finally:
        db.close()
        engine.dispose()
