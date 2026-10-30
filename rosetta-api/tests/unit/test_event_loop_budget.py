"""Whole jobs run under asyncio debug mode: no single event-loop step may take longer than
the budget, so CPU-heavy work (preparation, analysis, report building) stays off the loop.
A ticker beside a large preparation also catches a thread that holds the GIL."""
import asyncio
import logging
import time

import numpy as np
import pytest

pytest.importorskip("pytket")

import services.job_manager as job_manager  # noqa: E402
from services import prep_worker  # noqa: E402
from qrosetta_commons.helpers import encode_statevector  # noqa: E402
from services import job_store  # noqa: E402
from tests.unit._time_scale import seconds  # noqa: E402

BUDGET_SEC = seconds(0.25)
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


@pytest.mark.parametrize("mode", ["statevector", "measured"])
def test_playlist_job_keeps_every_loop_step_within_budget(fleet, mode):
    from schemas import BatchPayload, BenchmarkTask
    payload = BatchPayload(mode=mode, n_shots=8200, target_simulators=RUNNERS,
                           tasks=[BenchmarkTask(name=f"t{i}", qasm_string=_circuit(measured=mode == "measured"))
                                  for i in range(3)])
    job_manager.ACTIVE_JOBS["budget-batch"] = job_manager.new_job()
    try:
        _, slow = _slow_steps(job_manager.worker_batch_suite("budget-batch", payload))
        job = job_manager.ACTIVE_JOBS["budget-batch"]
        assert job["status"] == "completed", job.get("error")
        assert len(job_store.full_report(job)["benchmark_summary"]) == 3
        assert not slow, slow
    finally:
        job_manager.ACTIVE_JOBS.pop("budget-batch", None)


def _nine_thousand_nine_hundred_gate_calls():
    body = " ".join(["h a;", "cx a,b;", "rz(0.1) b;", "t a;", "cx b,a;"] * 4)
    calls = "\n".join(f"g q[{k % 10}],q[{(k + 1) % 10}];" for k in range(9900))
    return f'OPENQASM 2.0;\ninclude "qelib1.inc";\ngate g a,b {{ {body} }}\nqreg q[10];\n{calls}\n'


async def _longest_gap(coro):
    """(result of ``coro``, the longest gap between ticks of a 5 ms ticker beside it)."""
    gaps, done = [0.0], asyncio.Event()

    async def tick():
        last = time.perf_counter()
        while not done.is_set():
            await asyncio.sleep(0.005)
            now = time.perf_counter()
            gaps.append(now - last)
            last = now

    ticker = asyncio.create_task(tick())
    try:
        return await coro, max(gaps)
    finally:
        done.set()
        await ticker


def test_a_large_preparation_keeps_every_loop_step_within_budget(fleet):
    qasm = _nine_thousand_nine_hundred_gate_calls()
    try:
        (report, gap), slow = _slow_steps(_longest_gap(job_manager.run_single_circuit_comparison(
            qasm, target_simulators=RUNNERS)))
    finally:
        prep_worker.stop()
    assert len(report["raw_results"]) == len(RUNNERS), report.get("error")
    assert not slow, slow
    assert gap < BUDGET_SEC, f"event loop blocked for {gap:.2f} s"


def test_tket_parameter_note_runs_off_the_loop(fleet, monkeypatch):
    """The note scans the whole dispatched text (0.4 s on a 3 MB circuit at one CPU)."""
    import time as _time
    real = job_manager.tket_parameter_note

    def slow(*args, **kwargs):
        _time.sleep(0.5)
        return real(*args, **kwargs)
    monkeypatch.setattr(job_manager, "tket_parameter_note", slow)
    monkeypatch.setattr(job_manager, "_TKET_RUNNERS", frozenset(RUNNERS))
    report, slow_steps = _slow_steps(job_manager.run_single_circuit_comparison(
        _circuit(n_gates=50), target_simulators=RUNNERS))
    assert len(report["raw_results"]) == len(RUNNERS)
    assert not slow_steps, slow_steps
