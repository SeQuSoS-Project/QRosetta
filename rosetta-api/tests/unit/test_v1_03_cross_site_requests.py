"""V1-03: a page on another site cannot start jobs or sign in through the API. A body sent
without a JSON Content-Type is a 415, and a state-changing request whose Origin is neither the
server's own nor an allowed CORS origin is a 403; requests without Origin (the CLI) and from
the page's own origin work."""
import json
from pathlib import Path

import pytest

pytest.importorskip("pytket")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import routers.benchmark as benchmark  # noqa: E402
from config import settings  # noqa: E402
from db.database import Base, get_db  # noqa: E402
from main import app  # noqa: E402
from routers.same_origin import request_is_cross_site  # noqa: E402
from services import job_manager, job_store  # noqa: E402
from services.security import limiter  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
BELL = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'
COMPARE = json.dumps({"qasm_string": BELL, "target_simulators": ["qiskit"]}).encode()
JSON = {"Content-Type": "application/json"}
EVIL = "https://evil.example"


@pytest.fixture
def started(monkeypatch, tmp_path):
    """The real app with rate limits off; returns the list of compare jobs the API started."""
    calls = []

    async def require(target_simulators):
        return None

    async def worker(job_id, *args, **kwargs):
        calls.append(job_id)

    monkeypatch.setattr(limiter, "enabled", False)
    monkeypatch.setattr(job_store, "SPILL_DIR", str(tmp_path / "spill"))
    monkeypatch.setattr(benchmark, "require_available", require)
    monkeypatch.setattr(benchmark, "worker_compare", worker)
    before = set(job_manager.ACTIVE_JOBS)
    yield calls
    for job_id in [j for j in job_manager.ACTIVE_JOBS if j not in before]:
        job_manager.ACTIVE_JOBS.pop(job_id, None)


def _jobs():
    return len(job_manager.ACTIVE_JOBS)


def test_v1_03_a_cross_site_body_without_content_type_starts_no_job(started):
    before = _jobs()
    response = TestClient(app).post("/compare", content=COMPARE)
    assert response.status_code == 415
    assert response.json() == {"detail": "Send the request body as JSON, with Content-Type: application/json."}
    assert started == [] and _jobs() == before


@pytest.mark.parametrize("content_type", ["text/plain", "text/plain;charset=UTF-8",
                                          "application/x-www-form-urlencoded",
                                          "multipart/form-data; boundary=x"])
@pytest.mark.parametrize("path", ["/compare", "/compare_measured", "/run_batch_suite", "/experiments", "/plan"])
def test_v1_03_a_simple_request_content_type_is_415_on_json_routes(started, path, content_type):
    before = _jobs()
    response = TestClient(app).post(path, content=COMPARE, headers={"Content-Type": content_type})
    assert response.status_code == 415
    assert started == [] and _jobs() == before


@pytest.mark.parametrize("path", ["/compare", "/compare_measured", "/run_batch_suite", "/experiments",
                                  "/plan", "/export", "/summary", "/generate_circuit", "/auth/token",
                                  "/auth/register", "/shared/circuits", "/timing-caveats"])
@pytest.mark.parametrize("origin", [EVIL, "null", "http://testserver:3000", "https://testserver.evil.example",
                                    "not an origin", "http://testserver/path"])
def test_v1_03_a_foreign_origin_is_403(started, path, origin):
    before = _jobs()
    response = TestClient(app).post(path, content=COMPARE, headers={**JSON, "Origin": origin})
    assert response.status_code == 403
    assert response.json() == {"detail": "Requests from other sites are refused."}
    assert started == [] and _jobs() == before


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_v1_03_every_state_changing_method_is_checked(started, method):
    response = TestClient(app).request(method, "/history/runs", content=b"{}", headers={**JSON, "Origin": EVIL})
    assert response.status_code == 403


def test_v1_03_a_cross_site_fetch_without_origin_is_403(started):
    response = TestClient(app).post("/compare", content=COMPARE, headers={**JSON, "Sec-Fetch-Site": "cross-site"})
    assert response.status_code == 403
    assert started == []


def test_v1_03_a_request_without_origin_starts_a_job(started):
    response = TestClient(app).post("/compare", content=COMPARE, headers=JSON)
    assert response.status_code == 200, response.text
    assert started == [response.json()["job_id"]]


@pytest.mark.parametrize("host, origin", [("testserver", "http://testserver"),
                                          ("127.0.0.1:8080", "http://127.0.0.1:8080"),
                                          ("localhost:8080", "http://LOCALHOST:8080"),
                                          ("rosetta.example", "https://rosetta.example"),
                                          ("rosetta.example:443", "https://rosetta.example"),
                                          ("[::1]:8080", "http://[::1]:8080")])
def test_v1_03_the_pages_own_origin_starts_a_job(started, host, origin):
    headers = {**JSON, "Origin": origin, "Host": host, "Sec-Fetch-Site": "same-origin"}
    response = TestClient(app).post("/compare", content=COMPARE, headers=headers)
    assert response.status_code == 200, response.text
    assert len(started) == 1


def test_v1_03_a_host_without_its_port_does_not_match_a_page_on_another_port(started):
    response = TestClient(app).post("/compare", content=COMPARE,
                                    headers={**JSON, "Origin": "http://127.0.0.1:8080", "Host": "127.0.0.1"})
    assert response.status_code == 403


def test_v1_03_a_cors_origin_is_allowed(started, monkeypatch):
    monkeypatch.setattr(settings, "CORS_ALLOW_ORIGINS", "https://frontend.example")
    for origin in ("https://frontend.example", "http://localhost", "http://127.0.0.1"):
        response = TestClient(app).post("/compare", content=COMPARE, headers={**JSON, "Origin": origin})
        assert response.status_code == 200, (origin, response.text)
    assert len(started) == 3


def test_v1_03_forwarded_host_counts_only_with_the_proxy_token(monkeypatch):
    monkeypatch.setattr(settings, "PROXY_TOKEN", "proxy-secret")
    monkeypatch.setattr(settings, "CORS_ALLOW_ORIGINS", "")
    base = {b"origin": b"https://frontend.example", b"host": b"api.example",
            b"x-forwarded-host": b"frontend.example"}
    assert not request_is_cross_site({**base, b"x-qrosetta-proxy-token": b"proxy-secret"})
    assert request_is_cross_site({**base, b"x-qrosetta-proxy-token": b"wrong"})
    assert request_is_cross_site(base)
    monkeypatch.setattr(settings, "PROXY_TOKEN", "")
    assert request_is_cross_site({**base, b"x-qrosetta-proxy-token": b""})


def test_v1_03_reads_and_preflights_are_not_checked(started):
    client = TestClient(app)
    assert client.get("/config", headers={"Origin": EVIL}).status_code == 200
    preflight = client.options("/compare", headers={"Origin": "http://localhost",
                                                    "Access-Control-Request-Method": "POST"})
    assert preflight.status_code == 200


@pytest.fixture
def accounts_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def _get_db():
        db = session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    limiter.reset()
    yield
    app.dependency_overrides.pop(get_db, None)
    limiter.reset()
    engine.dispose()


def test_v1_03_login_from_the_pages_own_origin_works_and_from_another_site_is_403(accounts_db):
    client = TestClient(app)
    page = {"Origin": "http://127.0.0.1:8080", "Host": "127.0.0.1:8080"}
    registered = client.post("/auth/register", json={"email": "v103@example.org", "password": "correct-horse-1"},
                             headers=page)
    assert registered.status_code == 201, registered.text
    form = {"username": "v103@example.org", "password": "correct-horse-1"}
    signed_in = client.post("/auth/token", data=form, headers=page)
    assert signed_in.status_code == 200, signed_in.text
    assert signed_in.json()["access_token"]
    assert client.post("/auth/token", data=form, headers={"Origin": EVIL}).status_code == 403


def test_v1_03_nginx_passes_the_host_with_its_port_and_the_frontend_its_forwarded_host():
    local = (REPO / "nginx" / "nginx.conf").read_text()
    assert "proxy_set_header Host $http_host;" in local
    assert "proxy_set_header Host $host;" not in local
    frontend = (REPO / "infra" / "nginx-frontend.conf").read_text()
    assert "proxy_set_header X-Forwarded-Host $http_host;" in frontend
