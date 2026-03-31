"""
Local smoke test for the myqlm runner.

Run against the live stack:
    python3 tests/test_myqlm_runner.py
"""
import httpx
import time

BASE_URL = "http://localhost"


def _poll_job(job_id: str, timeout: int = 120) -> dict:
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
        "target_simulators": ["myqlm"]
    }
    resp = httpx.post(f"{BASE_URL}/run_batch_suite", json=payload, timeout=30)
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    job_id = resp.json()["job_id"]
    results = _poll_job(job_id)
    summary = results.get("benchmark_summary", [])
    assert len(summary) == 1, f"Expected 1 task result, got {len(summary)}"
    task = summary[0]
    myqlm_result = next(
        (r for r in task.get("raw_results", []) if r.get("simulator") == "myqlm"),
        None
    )
    assert myqlm_result is not None, "No result for myqlm in raw_results"
    assert myqlm_result.get("error") is None, f"myqlm runner error: {myqlm_result.get('error')}"
    print(f"  execution_time_sec  : {myqlm_result.get('execution_time_sec'):.4f}s")
    print(f"  compilation_time_sec: {myqlm_result.get('compilation_time_sec'):.4f}s")
    print(f"  simulation_time_sec : {myqlm_result.get('simulation_time_sec'):.4f}s")
    print(f"  memory_usage_mb     : {myqlm_result.get('memory_usage_mb'):.2f} MB")
    print("  PASSED")


def test_measured():
    print("--- Test 2: /run_measured (counts) ---")
    payload = {
        "tasks": [{"algorithm": "bell", "qubits": 2}],
        "mode": "measured",
        "n_shots": 1024,
        "target_simulators": ["myqlm"]
    }
    resp = httpx.post(f"{BASE_URL}/run_batch_suite", json=payload, timeout=30)
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    job_id = resp.json()["job_id"]
    results = _poll_job(job_id)
    summary = results.get("benchmark_summary", [])
    assert len(summary) == 1, f"Expected 1 task result, got {len(summary)}"
    task = summary[0]
    myqlm_result = next(
        (r for r in task.get("raw_results", []) if r.get("simulator") == "myqlm"),
        None
    )
    assert myqlm_result is not None, "No result for myqlm in raw_results"
    assert myqlm_result.get("error") is None, f"myqlm runner error: {myqlm_result.get('error')}"
    counts = myqlm_result.get("counts", {})
    total_shots = sum(counts.values())
    assert total_shots == 1024, f"Expected 1024 total shots, got {total_shots}"
    unexpected = [k for k in counts if k not in ("00", "11")]
    assert not unexpected, f"Unexpected bitstrings in Bell counts: {unexpected}"
    print(f"  counts             : {counts}")
    print(f"  execution_time_sec : {myqlm_result.get('execution_time_sec'):.4f}s")
    print("  PASSED")


if __name__ == "__main__":
    try:
        test_statevector()
        test_measured()
        print("\nAll myqlm smoke tests PASSED.")
    except Exception as exc:
        print(f"\nSMOKE TEST FAILED: {exc}")
        raise
