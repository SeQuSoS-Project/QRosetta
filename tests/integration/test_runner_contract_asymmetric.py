"""Live-stack asymmetric contract test for active runners.

Run against the live stack:
    python3 tests/integration/test_runner_contract_asymmetric.py

The probe flips q[0] of a 3-qubit register and leaves q[1], q[2] idle, so a runner that
returns |0...0>, mislabels its bit order, or drops idle qubits from the statevector fails.

The classical-bit probes check the counts contract: keys hold every declared classical bit
(flat index in creg declaration order), flat clbit 0 rightmost under "lsb" and leftmost
under "msb", and unmeasured classical bits read 0, including one inside a creg and one in
the creg declared first. The mid-circuit probe accepts either the correct distribution or an
error naming mid-circuit measurement.

The statevector-shape probes check that a gate-free circuit returns |0...0> over every
declared qubit, and that with apply_preprocessing off the statevector follows register
declaration order; a runner may instead refuse several registers with an error that says to
enable apply_preprocessing.
"""

import os
import base64
import math
import struct
import time

import httpx


BASE_URL = os.environ.get("QROSETTA_BASE_URL", "http://localhost")
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

N_QUBITS = 3

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


QASM_HEADER = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'

# name -> (QASM body, {ordering: expected single key})
CLASSICAL_BIT_PROBES = {
    "clbit_order": (
        "qreg q[2]; creg c[2]; x q[0]; measure q[0] -> c[0]; measure q[1] -> c[1];",
        {"lsb": "01", "msb": "10"}),
    "clbit_swap": (
        "qreg q[4]; creg c[2]; x q[0]; x q[3]; measure q[0] -> c[1]; measure q[3] -> c[0];",
        {"lsb": "11", "msb": "11"}),
    "creg_declaration_order": (
        "qreg q[2]; creg b[1]; creg a[1]; x q[0]; measure q[0] -> b[0]; measure q[1] -> a[0];",
        {"lsb": "01", "msb": "10"}),
    "unmeasured_creg": (
        "qreg q[2]; creg c[2]; creg d[1]; x q[0]; measure q[0] -> c[0]; measure q[1] -> c[1];",
        {"lsb": "001", "msb": "100"}),
    "unmeasured_clbit_mid_creg": (
        "qreg q[3]; creg c[1]; creg d[3]; x q[0]; x q[2]; "
        "measure q[0] -> d[2]; measure q[1] -> c[0]; measure q[2] -> d[0];",
        {"lsb": "1010", "msb": "0101"}),
    "unmeasured_clbit_first_creg": (
        "qreg q[2]; creg a[2]; creg b[1]; x q[1]; measure q[0] -> a[0]; measure q[1] -> b[0];",
        {"lsb": "100", "msb": "001"}),
}

# name -> (QASM body, apply_preprocessing, n_qubits, {ordering: populated index})
STATEVECTOR_SHAPE_PROBES = {
    "gate_free": ("qreg q[2];", True, 2, {"lsb": 0, "msb": 0}),
    "barrier_only": ("qreg q[2]; barrier q;", True, 2, {"lsb": 0, "msb": 0}),
    "qreg_declaration_order": (
        "qreg b[1]; qreg a[2]; x b[0]; x a[0];", False, 3, {"lsb": 3, "msb": 6}),
}
MULTI_QREG_REFUSAL = "enable apply_preprocessing"

SUBSET_QASM = "qreg q[3]; creg c[1]; x q[2]; h q[0]; measure q[0] -> c[0];"

MID_CIRCUIT_QASM = (
    "qreg q[1]; creg c[2]; h q[0]; measure q[0] -> c[0]; h q[0]; measure q[0] -> c[1];")
MID_CIRCUIT_ERROR = "mid-circuit measurement is not supported"
CLASSICAL_N_SHOTS = 2000


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


def _run_statevector(body: str, apply_preprocessing: bool) -> dict:
    payload = {
        "qasm_string": QASM_HEADER + body,
        "mode": "statevector",
        "target_simulators": ACTIVE_STATEVECTOR_RUNNERS,
        "timeout_seconds": 300,
        "execution_target": "local",
        "apply_preprocessing": apply_preprocessing,
    }
    resp = httpx.post(f"{BASE_URL}/compare", json=payload, timeout=30)
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    by_runner = _raw_result_by_runner(_poll_job(resp.json()["job_id"]))
    missing = [runner for runner in ACTIVE_STATEVECTOR_RUNNERS if runner not in by_runner]
    assert not missing, f"Missing statevector results: {missing}"
    return by_runner


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
        assert len(statevector) == 2 ** N_QUBITS, (
            f"{runner} returned {len(statevector)} amplitudes, expected {2 ** N_QUBITS}"
        )
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


def test_statevector_shape_probes():
    print("--- Statevector shape probes ---")
    failures = []
    for name, (body, preprocessing, n_qubits, expected) in STATEVECTOR_SHAPE_PROBES.items():
        by_runner = _run_statevector(body, preprocessing)
        for runner in ACTIVE_STATEVECTOR_RUNNERS:
            result = by_runner[runner]
            error = result.get("error")
            if error:
                if not (name == "qreg_declaration_order" and MULTI_QREG_REFUSAL in error.lower()):
                    failures.append(f"{name}/{runner}: error {error}")
                continue
            statevector = _decode_complex128_base64(result["statevector"])
            if len(statevector) != 2 ** n_qubits:
                failures.append(f"{name}/{runner}: {len(statevector)} amplitudes")
                continue
            index = expected[result.get("qubit_ordering")]
            if not math.isclose(abs(statevector[index]) ** 2, 1.0, abs_tol=1e-6):
                populated = max(range(len(statevector)), key=lambda i: abs(statevector[i]))
                failures.append(f"{name}/{runner}: expected index {index}, got {populated}")
    assert not failures, "\n".join(failures)
    print("  PASSED")


def _run_measured(body: str) -> dict:
    payload = {
        "qasm_string": QASM_HEADER + body,
        "n_shots": CLASSICAL_N_SHOTS,
        "target_simulators": ACTIVE_STATEVECTOR_RUNNERS,
        "timeout_seconds": 300,
        "execution_target": "local",
        "seed": 12345,
    }
    resp = httpx.post(f"{BASE_URL}/compare_measured", json=payload, timeout=30)
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
    by_runner = _raw_result_by_runner(_poll_job(resp.json()["job_id"]))
    missing = [runner for runner in ACTIVE_STATEVECTOR_RUNNERS if runner not in by_runner]
    assert not missing, f"Missing measured results: {missing}"
    return by_runner


def test_counts_keys_are_classical_bits():
    print("--- Classical-bit counts contract probes ---")
    failures = []
    for name, (body, expected) in CLASSICAL_BIT_PROBES.items():
        by_runner = _run_measured(body)
        for runner in ACTIVE_STATEVECTOR_RUNNERS:
            result = by_runner[runner]
            if result.get("error"):
                failures.append(f"{name}/{runner}: error {result['error']}")
                continue
            key = expected[result.get("qubit_ordering")]
            if result.get("counts") != {key: CLASSICAL_N_SHOTS}:
                failures.append(f"{name}/{runner}: expected {{{key!r}: all}}, got {result.get('counts')}")
    assert not failures, "\n".join(failures)
    print("  PASSED")


def _fraction_bounds(n_shots: int, p: float, sigmas: float = 5.0):
    spread = sigmas * math.sqrt(n_shots * p * (1 - p))
    return n_shots * p - spread, n_shots * p + spread


def test_counts_measure_only_the_measured_qubits():
    print("--- Measured-subset probe ---")
    by_runner = _run_measured(SUBSET_QASM)
    low, high = _fraction_bounds(CLASSICAL_N_SHOTS, 0.5)
    failures = []
    for runner in ACTIVE_STATEVECTOR_RUNNERS:
        result = by_runner[runner]
        counts = result.get("counts") or {}
        if result.get("error") or set(counts) - {"0", "1"} or not low <= counts.get("0", 0) <= high:
            failures.append(f"{runner}: {result.get('error') or counts}")
    assert not failures, "\n".join(failures)
    print("  PASSED")


def test_mid_circuit_measurement_is_simulated_or_refused():
    print("--- Mid-circuit measurement probe ---")
    by_runner = _run_measured(MID_CIRCUIT_QASM)
    low, high = _fraction_bounds(CLASSICAL_N_SHOTS, 0.25)
    failures = []
    for runner in ACTIVE_STATEVECTOR_RUNNERS:
        result = by_runner[runner]
        if result.get("error"):
            if MID_CIRCUIT_ERROR not in result["error"]:
                failures.append(f"{runner}: unexpected error {result['error']}")
            continue
        counts = result.get("counts") or {}
        if set(counts) != {"00", "01", "10", "11"} or not all(
                low <= v <= high for v in counts.values()):
            failures.append(f"{runner}: expected four outcomes near 25%, got {counts}")
    assert not failures, "\n".join(failures)
    print("  PASSED")


if __name__ == "__main__":
    try:
        test_active_runner_statevector_ordering_contract()
        test_active_runner_measured_ordering_contract()
        test_statevector_shape_probes()
        test_counts_keys_are_classical_bits()
        test_counts_measure_only_the_measured_qubits()
        test_mid_circuit_measurement_is_simulated_or_refused()
        print("\nAsymmetric runner contract tests PASSED.")
    except Exception as exc:
        print(f"\nASYMMETRIC CONTRACT TEST FAILED: {exc}")
        raise
