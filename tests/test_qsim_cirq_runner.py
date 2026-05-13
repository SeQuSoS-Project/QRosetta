# Unit and integration tests.

"""
Local smoke test for the qsim-cirq runner.

Run against the live stack:
    pip install httpx && python3 tests/test_qsim_cirq_runner.py
"""
import httpx
import json

BASE_URL = "http://localhost"

BELL_QASM_SV = """\
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q[0];
cx q[0],q[1];
"""

BELL_QASM_MEAS = """\
OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
creg c[2];
h q[0];
cx q[0],q[1];
measure q -> c;
"""

def _poll_job(job_id: str, timeout: int = 120) -> dict:
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = httpx.get(f"{BASE_URL}/jobs/{job_id}", timeout=10)
        assert resp.status_code == 200, f"Job poll HTTP {resp.status_code}: {resp.text}"
        data = resp.json()
        if data.get("status") == "completed":
            return data.get("results", {})
        time.sleep(1)
    raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")

def test_statevector():
    print("--- Test 1: /run (statevector) ---")
    payload = {
        "tasks": [{"algorithm": "bell", "qubits": 2}],
        "mode": "statevector",
        "target_simulators": ["qsim-cirq"]
    }
    resp = httpx.post(f"{BASE_URL}/run_batch_suite", json=payload, timeout=30)
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    job_id = resp.json()["job_id"]
    results = _poll_job(job_id)
    summary = results.get("benchmark_summary", [])
    assert len(summary) == 1, f"Expected 1 task result, got {len(summary)}"
    task = summary[0]
    assert "error" not in task, f"Task error: {task.get('error')}"
    perf = task.get("performance_report", {})
    qsim_result = next(
        (r for r in task.get("raw_results", []) if r.get("simulator") == "qsim-cirq"),
        None
    )
    assert qsim_result is not None, "No result for qsim-cirq in raw_results"
    assert "error" not in qsim_result or qsim_result.get("error") is None,        f"qsim-cirq runner error: {qsim_result.get('error')}"
    print(f"  execution_time_sec : {qsim_result.get('execution_time_sec'):.4f}s")
    print(f"  compilation_time_sec: {qsim_result.get('compilation_time_sec'):.4f}s")
    print(f"  simulation_time_sec : {qsim_result.get('simulation_time_sec'):.4f}s")
    print(f"  memory_usage_mb     : {qsim_result.get('memory_usage_mb'):.2f} MB")
    print("  PASSED")

def test_measured():
    print("--- Test 2: /run_measured (counts) ---")
    payload = {
        "tasks": [{"algorithm": "bell", "qubits": 2}],
        "mode": "measured",
        "n_shots": 1024,
        "target_simulators": ["qsim-cirq"]
    }
    resp = httpx.post(f"{BASE_URL}/run_batch_suite", json=payload, timeout=30)
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    job_id = resp.json()["job_id"]
    results = _poll_job(job_id)
    summary = results.get("benchmark_summary", [])
    assert len(summary) == 1, f"Expected 1 task result, got {len(summary)}"
    task = summary[0]
    assert "error" not in task, f"Task error: {task.get('error')}"
    qsim_result = next(
        (r for r in task.get("raw_results", []) if r.get("simulator") == "qsim-cirq"),
        None
    )
    assert qsim_result is not None, "No result for qsim-cirq in raw_results"
    assert "error" not in qsim_result or qsim_result.get("error") is None,        f"qsim-cirq runner error: {qsim_result.get('error')}"
    counts = qsim_result.get("counts", {})
    total_shots = sum(counts.values())
    assert total_shots == 1024, f"Expected 1024 total shots, got {total_shots}"

    unexpected = [k for k in counts if k not in ("00", "11")]
    assert not unexpected, f"Unexpected bitstrings in Bell counts: {unexpected}"
    print(f"  counts: {counts}")
    print(f"  execution_time_sec : {qsim_result.get('execution_time_sec'):.4f}s")
    print("  PASSED")

if __name__ == "__main__":
    try:
        test_statevector()
        test_measured()
        print("\nAll qsim-cirq smoke tests PASSED.")
    except Exception as exc:
        print(f"\nSMOKE TEST FAILED: {exc}")
        raise
