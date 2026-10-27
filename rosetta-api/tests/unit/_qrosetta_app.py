"""The real FastAPI app behind qrosetta's Transport interface (spec Q15, job `cli-contract`):
TestClient requests in process, rate limits off, availability answered as up, and a fake runner
fleet behind the dispatcher returning statevectors and counts the test chooses."""

import math

import numpy as np
import pytest
from fastapi.testclient import TestClient

from tests.unit._qrosetta_fake import REPO  # noqa: F401

from qrosetta_cli.client.transport import Response, Transport  # noqa: E402
from qrosetta_commons.helpers import encode_statevector  # noqa: E402

BELL = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\nh q[0];\ncx q[0],q[1];\n'
RUNNERS = ("qiskit", "cirq", "qulacs")


class AppTransport(Transport):
    """A Transport (and its factory) that sends every request to the app through TestClient."""

    def __init__(self, client, url="http://localhost:8080"):
        self.client = client
        self.url = url
        self.requests = []
        self.tokens = []

    def __call__(self, server, token=None, timeout=None):
        self.url = server.url
        self.tokens.append(token)
        return self

    def request(self, method, path, query=None, body=None, headers=None, timeout=None):
        self.requests.append((method, path, query, body))
        r = self.client.request(method, path, params=query, content=body, headers=headers or {})
        return Response(r.status_code, {k.lower(): v for k, v in r.headers.items()}, r.content)


class Fleet:
    """What each fake runner returns: `vectors` maps a runner to its statevector, `counts` to its
    counts; the rest return the Bell state."""

    def __init__(self):
        bell = np.array([1, 0, 0, 1], dtype=complex) / math.sqrt(2)
        self.vectors = {name: bell for name in RUNNERS}
        self.counts = {}
        self.errors = {}
        self.calls = []

    async def dispatch(self, runner_urls, runner_payload=None, timeout_seconds=None, runner_statuses=None):
        self.calls.append((sorted(runner_urls), dict(runner_payload or {})))
        out = []
        for name in runner_urls:
            if name in self.errors:
                out.append({"simulator": name, "dispatch_status": "error", "error": self.errors[name]})
            elif runner_payload and runner_payload.get("n_shots"):
                n = runner_payload["n_shots"]
                counts = self.counts.get(name) or {"00": n // 2, "11": n - n // 2}
                out.append({"simulator": name, "dispatch_status": "ok", "qubit_ordering": "lsb", "counts": counts})
            else:
                out.append({"simulator": name, "dispatch_status": "ok", "qubit_ordering": "lsb",
                            "statevector": encode_statevector(self.vectors[name])})
            if runner_statuses is not None:
                runner_statuses[name] = "done" if out[-1]["dispatch_status"] == "ok" else "error"
        return out


@pytest.fixture
def app_server(tmp_path, monkeypatch):
    """(transport factory, fleet) for the real app with a fake fleet of three runners."""
    pytest.importorskip("pytket")
    import routers.benchmark as benchmark
    import services.availability as availability
    import services.compilation as compilation
    import services.job_manager as job_manager
    import services.service_listing as service_listing
    from config import settings
    from main import app
    from services import job_store, prep_worker
    from services.security import limiter

    fleet = Fleet()
    urls = {name: f"http://{name}:8000" for name in RUNNERS}

    async def available(urls_, target_simulators=None):
        return urls_, []

    async def require(target_simulators):
        return None

    async def runner_availability(names=None, services=None):
        registry = services if services is not None else settings.get_runner_services()
        return {n: {"available": n in RUNNERS or services is not None, "reason": None, "device": None}
                for n in (names if names is not None else registry)}

    monkeypatch.setattr(job_store, "SPILL_DIR", str(tmp_path / "spill"))
    monkeypatch.setattr(limiter, "enabled", False)
    monkeypatch.setattr(prep_worker, "IN_PROCESS", True)
    monkeypatch.setattr(job_manager, "dispatch_to_runners", fleet.dispatch)
    monkeypatch.setattr(compilation, "dispatch_to_runners", fleet.dispatch)
    monkeypatch.setattr(job_manager, "filter_available", available)
    monkeypatch.setattr(benchmark, "require_available", require)
    monkeypatch.setattr(availability, "runner_availability", runner_availability)
    monkeypatch.setattr(service_listing, "runner_availability", runner_availability)
    monkeypatch.setattr(job_manager, "STATEVECTOR_RUNNER_URLS", urls)
    monkeypatch.setattr(job_manager, "SAMPLED_SV_URLS", urls)
    monkeypatch.setattr(job_manager, "NATIVE_SAMPLING_URLS", {})
    before = set(job_manager.ACTIVE_JOBS)
    yield AppTransport(TestClient(app)), fleet
    for job_id in [j for j in job_manager.ACTIVE_JOBS if j not in before]:
        job_manager.ACTIVE_JOBS.pop(job_id, None)
