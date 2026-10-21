"""Whole jobs run under asyncio debug mode: no single event-loop step may take longer than
the budget, so CPU-heavy work (preparation, analysis, report building) stays in threads."""
import asyncio
import logging

import numpy as np
import pytest

pytest.importorskip("pytket")

import services.job_manager as job_manager  # noqa: E402
from qrosetta_commons.helpers import encode_statevector  # noqa: E402
from services import job_store  # noqa: E402

BUDGET_SEC = 0.25
RUNNERS = [f"r{i}" for i in range(14)]


def _circuit(n_qubits=7, n_gates=2000, measured=False):
    rng = np.random.default_rng(7)
    lines = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg q[{n_qubits}];"]
    if measured:
        lines.append(f"creg c[{n_qubits}];")
    for _ in range(n_gates):
        a, b = (int(x) for x in rng.choice(n_qubits, 2, replace=False))
        lines.append(rng.choice([f"h q[{a}];", f"cx q[{a}],q[{b}];", f"rz({rng.uniform(-3, 3):.6f}) q[{a}];"]))
    if measured:
        lines.append("measure q -> c;")
    return "\n".join(lines) + "\n"


@pytest.fixture(autouse=True)
def spill_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(job_store, "SPILL_DIR", str(tmp_path / "spill"))


@pytest.fixture
def fleet(monkeypatch):
    rng = np.random.default_rng(3)

    async def dispatch(runner_urls, runner_payload=None, timeout_seconds=None, runner_statuses=None):
        out = []
        for name in runner_urls:
            if runner_payload and runner_payload.get("n_shots"):
                p = rng.dirichlet(np.full(2 ** 7, 0.5))
                sample = rng.multinomial(runner_payload["n_shots"], p)
                out.append({"simulator": name, "dispatch_status": "ok", "qubit_ordering": "lsb",
                            "counts": {format(i, "07b"): int(v) for i, v in enumerate(sample) if v}})
            else:
                sv = rng.normal(size=2 ** 7) + 1j * rng.normal(size=2 ** 7)
                out.append({"simulator": name, "dispatch_status": "ok", "qubit_ordering": "lsb",
                            "statevector": encode_statevector(sv / np.linalg.norm(sv))})
        return out

    async def available(urls, target_simulators=None):
        return urls, []
    urls = {name: f"http://{name}:8000" for name in RUNNERS}
    monkeypatch.setattr(job_manager, "dispatch_to_runners", dispatch)
    monkeypatch.setattr(job_manager, "filter_available", available)
    monkeypatch.setattr(job_manager, "STATEVECTOR_RUNNER_URLS", urls)
    monkeypatch.setattr(job_manager, "SAMPLED_SV_URLS", urls)
    monkeypatch.setattr(job_manager, "NATIVE_SAMPLING_URLS", {})


def _slow_steps(coro):
    records = []

    class Collect(logging.Handler):
        def emit(self, record):
            if "took" in record.getMessage() and "seconds" in record.getMessage():
                records.append(record.getMessage())

    handler = Collect()
    logger = logging.getLogger("asyncio")
    logger.addHandler(handler)
    previous_level = logger.level
    logger.setLevel(logging.WARNING)

    async def main():
        asyncio.get_running_loop().slow_callback_duration = BUDGET_SEC
        return await coro

    try:
        report = asyncio.run(main(), debug=True)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
    return report, records


def test_statevector_job_keeps_every_loop_step_within_budget(fleet):
    report, slow = _slow_steps(job_manager.run_single_circuit_comparison(
        _circuit(), target_simulators=RUNNERS))
    assert len(report["raw_results"]) == len(RUNNERS), report.get("error")
    assert report["divergence_report"]["pairwise_agreement"]
    assert not slow, slow


def test_measured_job_keeps_every_loop_step_within_budget(fleet):
    report, slow = _slow_steps(job_manager.run_single_circuit_measurement(
        _circuit(measured=True), 8200, target_simulators=RUNNERS, seed=1))
    assert len(report["raw_results"]) == len(RUNNERS), report.get("error")
    assert report["divergence_report"]["pairwise_agreement"]
    assert not slow, slow
