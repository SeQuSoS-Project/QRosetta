"""Live-stack asymmetric contract test for active runners.

Run against the live stack:
    python3 tests/integration/test_runner_contract_asymmetric.py

The probe circuits and their checks live in ``qrosetta_commons.contract_probes``, shared with
each runner's in-process ``--self-test``; see that module for what each probe catches. Here
they are sent through the API, so every runner receives the circuit text the API dispatches.
"""

import os
import time

import httpx

from qrosetta_commons.contract_probes import (
    CLASSICAL_BIT_PROBES, CLASSICAL_N_SHOTS, MID_CIRCUIT_QASM, MULTI_QREG_REFUSAL, N_SHOTS,
    ONE_HOT_QASM, QASM_HEADER, STATEVECTOR_SHAPE_PROBES, SUBSET_QASM, check_classical_bits,
    check_measured_subset, check_mid_circuit, check_one_hot_counts, check_one_hot_statevector,
    check_statevector_shape, decode_complex128_base64,
)


BASE_URL = os.environ.get("QROSETTA_BASE_URL", "http://localhost")

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

# One indexed operand with one register operand: cx q[0],r[0] and cx q[0],r[1], so every
# qubit ends in |1> and the populated index is 7 in either ordering.
REGISTER_BROADCAST_QASM = "qreg q[1]; qreg r[2]; x q[0]; cx q[0],r;"
REGISTER_BROADCAST_INDEX = 7


def _poll_job(job_id: str, timeout: int = 180) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = httpx.get(f"{BASE_URL}/jobs/{job_id}", timeout=10)
        assert resp.status_code == 200, f"Job poll HTTP {resp.status_code}: {resp.text}"
        data = resp.json()
        if data.get("status") in ("completed", "failed") and data.get("results"):
            return data["results"]
        if data.get("status") == "failed":
            raise AssertionError(f"Job failed: {data.get('error')}")
        time.sleep(1)
    raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")


def _raw_result_by_runner(results: dict) -> dict:
    return {item.get("simulator"): item for item in results.get("raw_results", [])}


def _submit(endpoint: str, payload: dict) -> dict:
    payload = {"target_simulators": ACTIVE_STATEVECTOR_RUNNERS, "timeout_seconds": 300,
               "execution_target": "local", **payload}
    resp = httpx.post(f"{BASE_URL}/{endpoint}", json=payload, timeout=30)
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    by_runner = _raw_result_by_runner(_poll_job(resp.json()["job_id"]))
    missing = [runner for runner in ACTIVE_STATEVECTOR_RUNNERS if runner not in by_runner]
    assert not missing, f"Missing {endpoint} results: {missing}"
    return by_runner


def _run_statevector(qasm: str, apply_preprocessing: bool = True) -> dict:
    return _submit("compare", {"qasm_string": qasm, "apply_preprocessing": apply_preprocessing})


def _run_measured(qasm: str, n_shots: int = CLASSICAL_N_SHOTS) -> dict:
    return _submit("compare_measured", {"qasm_string": qasm, "n_shots": n_shots, "seed": 12345})


def _assert_no_failures(failures: list) -> None:
    assert not failures, "\n".join(failures)
    print("  PASSED")


def test_active_runner_statevector_ordering_contract():
    print("--- Asymmetric statevector contract probe ---")
    by_runner = _run_statevector(ONE_HOT_QASM)
    _assert_no_failures([f"{runner}: {msg}" for runner in ACTIVE_STATEVECTOR_RUNNERS
                         for msg in check_one_hot_statevector(by_runner[runner])])


def test_active_runner_measured_ordering_contract():
    print("--- Asymmetric measured contract probe ---")
    by_runner = _run_measured(ONE_HOT_QASM, N_SHOTS)
    _assert_no_failures([f"{runner}: {msg}" for runner in ACTIVE_STATEVECTOR_RUNNERS
                         for msg in check_one_hot_counts(by_runner[runner], N_SHOTS)])


def test_statevector_shape_probes():
    print("--- Statevector shape probes ---")
    failures = []
    for name, (body, preprocessing, _n, _expected) in STATEVECTOR_SHAPE_PROBES.items():
        by_runner = _run_statevector(QASM_HEADER + body, preprocessing)
        failures += [f"{name}/{runner}: {msg}" for runner in ACTIVE_STATEVECTOR_RUNNERS
                     for msg in check_statevector_shape(name, by_runner[runner])]
    _assert_no_failures(failures)


def check_register_broadcast(result: dict) -> list:
    """All weight on index 7, or the multi-register refusal."""
    error = result.get("error")
    if error:
        return [] if MULTI_QREG_REFUSAL in str(error).lower() else [f"error: {error}"]
    statevector = decode_complex128_base64(result["statevector"])
    if len(statevector) != 8:
        return [f"{len(statevector)} amplitudes, expected 8"]
    if abs(abs(statevector[REGISTER_BROADCAST_INDEX]) ** 2 - 1.0) > 1e-6:
        populated = max(range(len(statevector)), key=lambda i: abs(statevector[i]))
        return [f"expected index {REGISTER_BROADCAST_INDEX}, got {populated}"]
    return []


def test_register_broadcast_without_preprocessing():
    print("--- Register-broadcast probe (apply_preprocessing=False) ---")
    by_runner = _run_statevector(QASM_HEADER + REGISTER_BROADCAST_QASM, False)
    _assert_no_failures([f"{runner}: {msg}" for runner in ACTIVE_STATEVECTOR_RUNNERS
                         for msg in check_register_broadcast(by_runner[runner])])


def test_counts_keys_are_classical_bits():
    print("--- Classical-bit counts contract probes ---")
    failures = []
    for name, (body, _expected) in CLASSICAL_BIT_PROBES.items():
        by_runner = _run_measured(QASM_HEADER + body)
        failures += [f"{name}/{runner}: {msg}" for runner in ACTIVE_STATEVECTOR_RUNNERS
                     for msg in check_classical_bits(name, by_runner[runner])]
    _assert_no_failures(failures)


def test_counts_measure_only_the_measured_qubits():
    print("--- Measured-subset probe ---")
    by_runner = _run_measured(QASM_HEADER + SUBSET_QASM)
    _assert_no_failures([f"{runner}: {msg}" for runner in ACTIVE_STATEVECTOR_RUNNERS
                         for msg in check_measured_subset(by_runner[runner])])


def test_mid_circuit_measurement_is_simulated_or_refused():
    print("--- Mid-circuit measurement probe ---")
    by_runner = _run_measured(QASM_HEADER + MID_CIRCUIT_QASM)
    _assert_no_failures([f"{runner}: {msg}" for runner in ACTIVE_STATEVECTOR_RUNNERS
                         for msg in check_mid_circuit(by_runner[runner])])


if __name__ == "__main__":
    try:
        test_active_runner_statevector_ordering_contract()
        test_active_runner_measured_ordering_contract()
        test_statevector_shape_probes()
        test_register_broadcast_without_preprocessing()
        test_counts_keys_are_classical_bits()
        test_counts_measure_only_the_measured_qubits()
        test_mid_circuit_measurement_is_simulated_or_refused()
        print("\nAsymmetric runner contract tests PASSED.")
    except Exception as exc:
        print(f"\nASYMMETRIC CONTRACT TEST FAILED: {exc}")
        raise
