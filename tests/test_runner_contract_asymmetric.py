# Unit and integration tests.

"""
Live-stack asymmetric contract test for active runners.

Run against the live stack:
    python3 tests/test_runner_contract_asymmetric.py

The probe is intentionally asymmetric. Symmetric Bell/GHZ smoke tests can pass
when a runner silently returns |0...0> or when its bit-order label is wrong.
"""

import base64
import math
import struct
import time

import httpx


BASE_URL = "http://localhost"
N_SHOTS = 64

ACTIVE_STATEVECTOR_RUNNERS = [
    "qiskit",
    "cirq",
    "qulacs",
    "quest",
    "pennylane-lightning",
    "pennylane-default",
    "qsim-cirq",
    "qibo",
    "qrisp",
    "myqlm",
    "pyquil",
    "torchquantum",
    "quimb",
    "cuquantum",
]

ONE_HOT_QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
x q[0];
"""

EXPECTED_STATEVECTOR_INDEX = {
    "lsb": 1,  # |001>
    "msb": 4,  # |100>
}

EXPECTED_COUNT_KEY = {
    "lsb": "001",
    "msb": "100",
}


def _poll_job(job_id: str, timeout: int = 180) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = httpx.get(f"{BASE_URL}/jobs/{job_id}", timeout=10)
        assert resp.status_code == 200, f"Job poll HTTP {resp.status_code}: {resp.text}"
        data = resp.json()
        if data.get("status") == "completed":
            return data.get("results", {})
        if data.get("status") == "failed":
            raise AssertionError(f"Job failed: {data.get('error')}")
        time.sleep(1)
    raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")


def _decode_complex128_base64(encoded: str) -> list[complex]:
    raw = base64.b64decode(encoded)
    assert len(raw) % 16 == 0, f"Statevector byte length {len(raw)} is not complex128"
    values = []
    for offset in range(0, len(raw), 16):
        real, imag = struct.unpack("dd", raw[offset : offset + 16])
        values.append(complex(real, imag))
    return values


def _raw_result_by_runner(results: dict) -> dict:
    raw_results = results.get("raw_results", [])
    return {item.get("simulator"): item for item in raw_results}


def test_active_runner_statevector_ordering_contract():
    print("--- Asymmetric statevector contract probe ---")
    payload = {
        "qasm_string": ONE_HOT_QASM,
        "mode": "statevector",
        "target_simulators": ACTIVE_STATEVECTOR_RUNNERS,
        "timeout_seconds": 300,
        "execution_target": "local",
    }
    resp = httpx.post(f"{BASE_URL}/compare", json=payload, timeout=30)
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    results = _poll_job(resp.json()["job_id"])
    by_runner = _raw_result_by_runner(results)

    missing = [runner for runner in ACTIVE_STATEVECTOR_RUNNERS if runner not in by_runner]
    assert not missing, f"Missing statevector results: {missing}"

    for runner in ACTIVE_STATEVECTOR_RUNNERS:
        result = by_runner[runner]
        assert result.get("error") is None, f"{runner} statevector error: {result.get('error')}"
        ordering = result.get("qubit_ordering")
        assert ordering in EXPECTED_STATEVECTOR_INDEX, f"{runner} invalid ordering: {ordering}"

        statevector = _decode_complex128_base64(result["statevector"])
        probabilities = [abs(value) ** 2 for value in statevector]
        norm = sum(probabilities)
        max_index = max(range(len(probabilities)), key=probabilities.__getitem__)
        max_probability = probabilities[max_index]
        expected_index = EXPECTED_STATEVECTOR_INDEX[ordering]

        assert math.isclose(norm, 1.0, rel_tol=0.0, abs_tol=1e-9), (
            f"{runner} statevector norm {norm}, expected 1"
        )
        assert max_index == expected_index, (
            f"{runner} declared {ordering}, but populated index {max_index}; "
            f"expected {expected_index}"
        )
        assert math.isclose(max_probability, 1.0, rel_tol=0.0, abs_tol=1e-9), (
            f"{runner} max probability {max_probability}, expected 1"
        )
        assert max_index != 0, f"{runner} returned fabricated |000> state"

    print("  PASSED")


def test_active_runner_measured_ordering_contract():
    print("--- Asymmetric measured contract probe ---")
    payload = {
        "qasm_string": ONE_HOT_QASM,
        "n_shots": N_SHOTS,
        "target_simulators": ACTIVE_STATEVECTOR_RUNNERS,
        "timeout_seconds": 300,
        "execution_target": "local",
        "seed": 12345,
    }
    resp = httpx.post(f"{BASE_URL}/compare_measured", json=payload, timeout=30)
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    results = _poll_job(resp.json()["job_id"])
    by_runner = _raw_result_by_runner(results)

    missing = [runner for runner in ACTIVE_STATEVECTOR_RUNNERS if runner not in by_runner]
    assert not missing, f"Missing measured results: {missing}"

    for runner in ACTIVE_STATEVECTOR_RUNNERS:
        result = by_runner[runner]
        assert result.get("error") is None, f"{runner} measured error: {result.get('error')}"
        ordering = result.get("qubit_ordering")
        assert ordering in EXPECTED_COUNT_KEY, f"{runner} invalid ordering: {ordering}"

        counts = result.get("counts", {})
        expected_key = EXPECTED_COUNT_KEY[ordering]
        total_shots = sum(counts.values())

        assert total_shots == N_SHOTS, f"{runner} returned {total_shots} shots"
        assert counts == {expected_key: N_SHOTS}, (
            f"{runner} declared {ordering}, expected only {expected_key}, got {counts}"
        )
        assert "000" not in counts, f"{runner} returned fabricated all-zero counts"

    print("  PASSED")


if __name__ == "__main__":
    try:
        test_active_runner_statevector_ordering_contract()
        test_active_runner_measured_ordering_contract()
        print("\nAsymmetric runner contract tests PASSED.")
    except Exception as exc:
        print(f"\nASYMMETRIC CONTRACT TEST FAILED: {exc}")
        raise
