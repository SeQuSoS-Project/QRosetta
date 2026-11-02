"""Security events (services/security_events.py): sign-in, failed sign-in, sign-out and refused
requests each write one JSON line with a UTC timestamp; no password or token appears."""
import json
import logging
from datetime import datetime

import pytest

import services.security_events as events
from tests.unit.authz_world import PASSWORD, world


class _Lines(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


@pytest.fixture
def lines():
    handler = _Lines()
    events.LOGGER.addHandler(handler)
    yield handler.lines
    events.LOGGER.removeHandler(handler)


@pytest.fixture
def w(tmp_path, monkeypatch):
    with world(tmp_path, monkeypatch) as built:
        yield built


def _events(lines):
    return [json.loads(line) for line in lines]


def test_sign_in_failure_sign_in_and_sign_out_are_logged_without_secrets(w, lines):
    email = "events-owner@example.org"
    user_id = w.user(email)
    assert w.client.post("/auth/token", data={"username": email, "password": "wrong-password-1"}).status_code == 401
    token = w.client.post("/auth/token", data={"username": email, "password": PASSWORD}).json()["access_token"]
    assert w.client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"}).status_code == 204
    got = _events(lines)
    assert [e["event"] for e in got] == ["auth.login_failed", "auth.login", "auth.logout"]
    assert got[0]["reason"] == "credentials" and got[0]["email_sha256"] == events.email_digest(email)
    assert got[1]["user_id"] == user_id and got[1]["path"] == "/auth/token"
    for e in got:
        assert datetime.fromisoformat(e["ts"]).utcoffset().total_seconds() == 0
    text = "\n".join(lines)
    assert PASSWORD not in text and "wrong-password-1" not in text and token not in text and email not in text


def test_a_refused_request_is_logged(w, lines):
    assert w.client.get("/history/runs", headers={"Authorization": "Bearer not-a-token"}).status_code == 401
    assert _events(lines)[-1]["event"] == "access.denied" and _events(lines)[-1]["status"] == 401


def test_control_characters_stay_escaped(lines):
    events.security_event("test.event", note="a\nb\x1b[31m")
    assert len(lines) == 1 and "\n" not in lines[0] and "\x1b" not in lines[0]
