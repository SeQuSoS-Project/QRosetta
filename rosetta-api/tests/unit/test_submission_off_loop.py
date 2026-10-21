"""Circuit validation of a submission runs in a worker thread, so a large circuit does not
stall other requests on the event loop."""
import asyncio
import time

import httpx
import pytest
from fastapi import FastAPI, HTTPException

import routers.benchmark as benchmark
import routers.experiment as experiment
from routers.errors import register_error_handlers
from services.security import limiter

H = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
BELL = H + "qreg q[2];\nh q[0];\ncx q[0],q[1];\n"


def _slow_refusal(*args, **kwargs):
    time.sleep(1.0)
    raise HTTPException(status_code=400, detail="refused")


async def _post_with_max_gap(app, path, body):
    gaps, done = [], asyncio.Event()

    async def tick():
        last = time.perf_counter()
        while not done.is_set():
            await asyncio.sleep(0.01)
            now = time.perf_counter()
            gaps.append(now - last)
            last = now

    ticker = asyncio.create_task(tick())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            response = await client.post(path, json=body)
        finally:
            done.set()
            await ticker
    return response, max(gaps)


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr(limiter, "enabled", False)
    monkeypatch.setattr(benchmark, "validate_submission", _slow_refusal)
    monkeypatch.setattr(experiment, "validate_submission", _slow_refusal)
    application = FastAPI()
    application.state.limiter = limiter
    register_error_handlers(application)
    application.include_router(benchmark.router)
    application.include_router(experiment.router)
    return application


@pytest.mark.parametrize("path, body", [
    ("/compare", {"qasm_string": BELL}),
    ("/compare_measured", {"qasm_string": BELL + "creg c[2];\nmeasure q -> c;\n"}),
    ("/run_batch_suite", {"tasks": [{"qasm_string": BELL}], "mode": "statevector"}),
    ("/experiments", {"circuits": [{"qasm_string": BELL}], "mode": "statevector"}),
])
def test_validation_does_not_block_the_event_loop(app, path, body):
    response, gap = asyncio.run(_post_with_max_gap(app, path, body))
    assert response.status_code == 400, response.text
    assert "refused" in response.text
    assert gap < 0.5, f"event loop blocked for {gap:.2f} s"
