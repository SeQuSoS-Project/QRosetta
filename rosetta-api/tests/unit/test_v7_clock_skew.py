"""V7(f) Failure injection, clock skew with a patched wall clock: access tokens (PyJWT's clock
moved after the token was issued; ``iat`` is in whole seconds, so a clock less than a second
behind the issuer cannot be told apart), share-link expiry, job retention, and host-load notices,
whose expiry is decided on the monotonic clock so that a wall-clock step does not end them."""

import asyncio
import time
import uuid
from datetime import datetime, timedelta

import jwt.api_jwt
import pytest

import db.models as models
import services.host_load as host_load
import services.job_manager as job_manager
import services.share_links as share_links
import services.storage as storage
from config import settings
from services.run_registry import GATE
from tests.unit.authz_world import PASSWORD, world


@pytest.fixture
def w(tmp_path, monkeypatch):
    with world(tmp_path, monkeypatch) as built:
        yield built


@pytest.fixture
def verifier_clock(monkeypatch):
    """``shift(seconds)``: from now on PyJWT checks tokens against a clock moved by ``seconds``
    (call it after the token is issued: the encoder reads the same name)."""

    def shift(seconds):
        class Shifted(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.now(tz) + timedelta(seconds=seconds)
        monkeypatch.setattr(jwt.api_jwt, "datetime", Shifted)
    return shift


def _login(w, uid):
    email = w.get_user(uid).email
    r = w.client.post("/auth/token", data={"username": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _me(w, token):
    return w.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code


@pytest.mark.parametrize("shift_sec, status", [
    (0, 200),
    (settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 - 60, 200),
    (settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 + 1, 401),
    (24 * 3600, 401),
    (-2, 401),
    (-10, 401),
])
def test_a_token_follows_the_servers_clock_with_no_leeway(w, verifier_clock, shift_sec, status):
    token = _login(w, w.user())
    verifier_clock(shift_sec)
    assert _me(w, token) == status


def test_a_refused_token_is_a_plain_401(w, verifier_clock):
    token = _login(w, w.user())
    verifier_clock(-10)
    r = w.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401 and r.headers.get("www-authenticate") == "Bearer"
    assert "iat" not in r.text and "Immature" not in r.text


def _shared_link(w, monkeypatch, days):
    uid = w.user()
    run_id = str(uuid.uuid4())
    key = storage.save_run_report(uid, run_id, {"input_qasm": "OPENQASM 2.0;\nqreg q[1];\n", "raw_results": []})
    with w.session() as db:
        db.add(models.RunHistory(id=run_id, user_id=uid, s3_object_key=key, run_name="skew"))
        db.commit()
        _link, token = share_links.create_link(db, uid, run_id, days)
    return token


@pytest.mark.parametrize("shift, status", [
    (timedelta(0), 200),
    (timedelta(days=7) - timedelta(minutes=1), 200),
    (timedelta(days=7) + timedelta(seconds=1), 404),
    (-timedelta(days=30), 200),
])
def test_share_link_expiry_follows_the_servers_clock(w, monkeypatch, shift, status):
    token = _shared_link(w, monkeypatch, 7)
    real_now = share_links._now
    monkeypatch.setattr(share_links, "_now", lambda: real_now() + shift)
    r = w.client.post("/shared/circuits", json={"token": token})
    assert r.status_code == status, r.text
    if status == 404:
        assert r.json() == {"detail": "This link does not exist, has expired or was revoked."}


class _Worker:
    def __init__(self, done):
        self._done = done

    def done(self):
        return self._done


def test_job_retention_follows_the_wall_clock_and_never_drops_a_running_job():
    now = time.time()
    ttl = settings.JOB_TTL_SEC
    jobs = {
        "skew-finished": {"status": "completed", "finished_at": now},
        "skew-running": {"status": "processing", "submitted_at": now, "worker": _Worker(False)},
        "skew-orphan": {"status": "processing", "submitted_at": now, "worker": _Worker(True)},
    }
    for job_id, job in jobs.items():
        dict.__setitem__(job_manager.ACTIVE_JOBS, job_id, job)
    try:
        def expired(at):
            return sorted(j for j in job_manager.expired_job_ids(now=at) if j.startswith("skew-"))
        assert expired(now) == []
        assert expired(now - 3600) == [], "a backward step evicted a job"
        assert expired(now + ttl - 1) == []
        assert expired(now + ttl + 1) == ["skew-finished", "skew-orphan"]
        assert expired(now + 365 * 86400) == ["skew-finished", "skew-orphan"]
    finally:
        for job_id in jobs:
            dict.pop(job_manager.ACTIVE_JOBS, job_id, None)


@pytest.fixture
def host_clocks(monkeypatch):
    clocks = {"wall": 1_000_000.0, "ticks": 500.0}
    monkeypatch.setattr(host_load, "_clock", lambda: clocks["wall"])
    monkeypatch.setattr(host_load, "_ticks", lambda: clocks["ticks"])
    yield clocks
    asyncio.run(host_load.reset())


@pytest.mark.parametrize("step", [3600.0, -3600.0])
def test_v7_07_a_wall_clock_step_does_not_end_a_host_load_notice(host_clocks, step):
    async def scenario():
        notice = await host_load.begin("build")
        host_clocks["wall"] += step
        host_clocks["ticks"] += 5
        assert await host_load.expire_due() == []
        await host_load.heartbeat(notice["notice_id"])
        host_clocks["ticks"] += host_load.NOTICE_TTL_SEC - 1
        assert await host_load.expire_due() == []
        assert GATE.status()["host_load_running"] == 1
        host_clocks["ticks"] += 2
        assert await host_load.expire_due() == [notice["notice_id"]]

    asyncio.run(scenario())
    assert GATE.status()["host_load_running"] == 0
