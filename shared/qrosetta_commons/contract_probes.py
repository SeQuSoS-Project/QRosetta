"""Asymmetric runner contract probes and their checks.

Used by the live-stack contract test (``tests/integration/test_runner_contract_asymmetric.py``)
and by ``helpers.run_self_test`` (a runner's ``--self-test`` flag). Each ``check_*`` function
takes one runner result dict and returns a list of failure messages, empty when it passes.

The one-hot probe flips q[0] of a 3-qubit register and leaves q[1], q[2] idle, so a runner that
returns |0...0>, mislabels its bit order, or drops idle qubits fails. The classical-bit probes
check the counts contract: keys hold every declared classical bit (flat index in creg
declaration order), flat clbit 0 rightmost under "lsb" and leftmost under "msb", and
unmeasured classical bits read 0. The shape probes check that a gate-free circuit returns
|0...0> over every declared qubit and that, with apply_preprocessing off, the statevector
follows register declaration order (a runner may instead refuse several registers with an
error that says to enable apply_preprocessing).
"""

import base64
import math
import struct

QASM_HEADER = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'

N_QUBITS = 3
N_SHOTS = 64
CLASSICAL_N_SHOTS = 2000
SEED_N_SHOTS = 512

ONE_HOT_QASM = QASM_HEADER + "qreg q[3];\nx q[0];\n"
ONE_HOT_MEASURED_QASM = QASM_HEADER + (
    "qreg q[3];\ncreg c[3];\nx q[0];\n"
    "measure q[0] -> c[0];\nmeasure q[1] -> c[1];\nmeasure q[2] -> c[2];\n")

EXPECTED_STATEVECTOR_INDEX = {"lsb": 1, "msb": 4}
EXPECTED_COUNT_KEY = {"lsb": "001", "msb": "100"}

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

SEED_QASM = QASM_HEADER + (
    "qreg q[4];\ncreg c[4];\nh q[0];\nh q[1];\nh q[2];\nh q[3];\nry(0.7) q[0];\n"
    "cx q[0],q[1];\nrz(0.3) q[2];\ncx q[2],q[3];\nh q[2];\n"
    "measure q[0] -> c[0];\nmeasure q[1] -> c[1];\nmeasure q[2] -> c[2];\n"
    "measure q[3] -> c[3];\n")
SEED_A, SEED_B = 12345, 54321


def decode_complex128_base64(encoded: str) -> list:
    """Base64 complex128 bytes -> list of complex amplitudes."""
    raw = base64.b64decode(encoded)
    if len(raw) % 16:
        raise ValueError(f"statevector byte length {len(raw)} is not complex128")
    return [complex(*struct.unpack("dd", raw[k:k + 16])) for k in range(0, len(raw), 16)]


def fraction_bounds(n_shots: int, p: float, sigmas: float = 5.0) -> tuple:
    """``n_shots * p`` plus or minus ``sigmas`` binomial standard deviations."""
    spread = sigmas * math.sqrt(n_shots * p * (1 - p))
    return n_shots * p - spread, n_shots * p + spread


def _ordering(result: dict, declared, labels) -> tuple:
    ordering = result.get("qubit_ordering")
    if ordering not in labels:
        return None, [f"invalid qubit_ordering {ordering!r}"]
    if declared is not None and ordering != declared:
        return None, [f"result reports qubit_ordering {ordering!r}, runner declares {declared!r}"]
    return ordering, []


def check_one_hot_statevector(result: dict, declared=None) -> list:
    """Norm 1, ``2**N_QUBITS`` amplitudes, all weight on the index the ordering label implies."""
    if result.get("error"):
        return [f"error: {result['error']}"]
    ordering, failures = _ordering(result, declared, EXPECTED_STATEVECTOR_INDEX)
    if failures:
        return failures
    statevector = decode_complex128_base64(result["statevector"])
    if len(statevector) != 2 ** N_QUBITS:
        return [f"{len(statevector)} amplitudes, expected {2 ** N_QUBITS}"]
    probabilities = [abs(v) ** 2 for v in statevector]
    norm = sum(probabilities)
    peak = max(range(len(probabilities)), key=probabilities.__getitem__)
    expected = EXPECTED_STATEVECTOR_INDEX[ordering]
    if not math.isclose(norm, 1.0, rel_tol=0.0, abs_tol=1e-9):
        failures.append(f"norm {norm}, expected 1")
    if peak != expected:
        failures.append(f"declared {ordering}, populated index {peak}, expected {expected}")
    elif not math.isclose(probabilities[peak], 1.0, rel_tol=0.0, abs_tol=1e-9):
        failures.append(f"peak probability {probabilities[peak]}, expected 1")
    return failures


def check_one_hot_counts(result: dict, n_shots: int = N_SHOTS, declared=None) -> list:
    """Every shot lands on the one-hot key the ordering label implies."""
    if result.get("error"):
        return [f"error: {result['error']}"]
    ordering, failures = _ordering(result, declared, EXPECTED_COUNT_KEY)
    if failures:
        return failures
    counts = result.get("counts") or {}
    expected = EXPECTED_COUNT_KEY[ordering]
    if counts != {expected: n_shots}:
        return [f"declared {ordering}, expected {{{expected!r}: {n_shots}}}, got {counts}"]
    return []


def check_statevector_shape(name: str, result: dict, declared=None) -> list:
    """One ``STATEVECTOR_SHAPE_PROBES`` entry."""
    _body, _pp, n_qubits, expected = STATEVECTOR_SHAPE_PROBES[name]
    error = result.get("error")
    if error:
        if name == "qreg_declaration_order" and MULTI_QREG_REFUSAL in str(error).lower():
            return []
        return [f"error: {error}"]
    ordering, failures = _ordering(result, declared, expected)
    if failures:
        return failures
    statevector = decode_complex128_base64(result["statevector"])
    if len(statevector) != 2 ** n_qubits:
        return [f"{len(statevector)} amplitudes, expected {2 ** n_qubits}"]
    index = expected[ordering]
    if not math.isclose(abs(statevector[index]) ** 2, 1.0, abs_tol=1e-6):
        populated = max(range(len(statevector)), key=lambda i: abs(statevector[i]))
        return [f"expected index {index}, got {populated}"]
    return []


def check_classical_bits(name: str, result: dict, n_shots: int = CLASSICAL_N_SHOTS,
                         declared=None) -> list:
    """One ``CLASSICAL_BIT_PROBES`` entry: every shot on the expected key."""
    if result.get("error"):
        return [f"error: {result['error']}"]
    _body, expected = CLASSICAL_BIT_PROBES[name]
    ordering, failures = _ordering(result, declared, expected)
    if failures:
        return failures
    key = expected[ordering]
    if result.get("counts") != {key: n_shots}:
        return [f"expected {{{key!r}: {n_shots}}}, got {result.get('counts')}"]
    return []


def check_measured_subset(result: dict, n_shots: int = CLASSICAL_N_SHOTS) -> list:
    """Only the measured qubit contributes a key bit, and it reads 0 about half the time."""
    counts = result.get("counts") or {}
    low, high = fraction_bounds(n_shots, 0.5)
    if result.get("error") or set(counts) - {"0", "1"} or not low <= counts.get("0", 0) <= high:
        return [str(result.get("error") or counts)]
    return []


def check_mid_circuit(result: dict, n_shots: int = CLASSICAL_N_SHOTS) -> list:
    """Four outcomes near 25% each, or an error naming mid-circuit measurement."""
    if result.get("error"):
        if MID_CIRCUIT_ERROR not in result["error"]:
            return [f"unexpected error {result['error']}"]
        return []
    counts = result.get("counts") or {}
    low, high = fraction_bounds(n_shots, 0.25)
    if set(counts) != {"00", "01", "10", "11"} or not all(low <= v <= high for v in counts.values()):
        return [f"expected four outcomes near 25%, got {counts}"]
    return []


def check_seed_reproducibility(first: dict, repeat: dict, other_seed: dict) -> list:
    """``first`` and ``repeat`` share a seed and must match; ``other_seed`` must differ."""
    failures = [f"error: {r['error']}" for r in (first, repeat, other_seed) if r.get("error")]
    if failures:
        return failures
    if first.get("counts") != repeat.get("counts"):
        failures.append("same seed gave different counts")
    if first.get("counts") == other_seed.get("counts"):
        failures.append("different seeds gave identical counts (seed ignored?)")
    return failures
