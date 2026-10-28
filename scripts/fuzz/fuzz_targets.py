"""Fuzz targets and oracles shared by the long-running fuzzers and the quick unit tests.

``validator_oracle`` (harness 1) feeds bytes to ``validate_submission``: it must return or
raise HTTPException 400/413, within ``TIME_LIMIT_SEC`` and ``MEMORY_LIMIT_MIB``.
"""

import os
import sys
import time
import tracemalloc
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
API_DIR = REPO / "rosetta-api"
for _path in (API_DIR, REPO / "shared"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
os.environ.setdefault("EXECUTION_MODE", "local")

TIME_LIMIT_SEC = 1.0
MEMORY_LIMIT_MIB = 256
ALLOWED_STATUS = {400, 413}
MODES = ("statevector", "measured", "compile")
CORPUS_DIR = API_DIR / "tests" / "fuzz_corpus"


class OracleFailure(AssertionError):
    """An input broke a harness's property."""


def seed_files() -> list:
    """The bundled circuits: MQT Bench, QASMBench, the examples and the self-test set."""
    files = sorted((API_DIR / "benchmarks").rglob("*.qasm"))
    files += sorted((API_DIR / "circuits").rglob("*.qasm"))
    return files


def seed_corpus(max_bytes: int = None) -> list:
    """Bytes of every bundled circuit, at most ``max_bytes`` long each when given."""
    out = []
    for path in seed_files():
        data = path.read_bytes()
        if max_bytes is None or len(data) <= max_bytes:
            out.append(data)
    return out


def validator_flags(data: bytes) -> dict:
    """Request options for an input, derived from its checksum so a saved input replays with
    the same options."""
    h = zlib.crc32(data)
    mode = MODES[h % 3]
    return {
        "mode": mode,
        "apply_preprocessing": not h & 0x10,
        "statevector": mode == "statevector" and not h & 0x20,
        "bypass_limits": bool(h & 0x40) and bool(h & 0x80),
        "check_reserved_names": not (h & 0x100 and h & 0x200),
    }


def _validate(text: str, flags: dict) -> None:
    from services.validator import check_statevector_circuit, validate_request
    validate_request(text, mode=flags["mode"], bypass_limits=flags["bypass_limits"],
                     apply_preprocessing=flags["apply_preprocessing"],
                     check_reserved_names=flags["check_reserved_names"])
    if flags["statevector"]:
        check_statevector_circuit(text)


def validator_oracle(data: bytes, measure_memory: bool = False, flags: dict = None) -> str:
    """Run one input through the validator; return 'accepted' or 'refused <status>', raise
    OracleFailure for any other exception, a call over TIME_LIMIT_SEC, or (with
    ``measure_memory``) a Python allocation peak over MEMORY_LIMIT_MIB."""
    from fastapi import HTTPException
    import services.validator  # noqa: F401  (imported before the clock starts)
    text = data.decode("utf-8", "surrogateescape")
    flags = flags or validator_flags(data)
    if measure_memory:
        tracemalloc.start()
    start = time.perf_counter()
    try:
        _validate(text, flags)
        outcome = "accepted"
    except HTTPException as exc:
        if exc.status_code not in ALLOWED_STATUS:
            raise OracleFailure(f"status {exc.status_code} with {flags}: {exc.detail!r}") from exc
        if not isinstance(exc.detail, str) or not exc.detail:
            raise OracleFailure(f"empty or non-text detail with {flags}") from exc
        outcome = f"refused {exc.status_code}"
    except RecursionError as exc:
        raise OracleFailure(f"RecursionError with {flags}") from exc
    except Exception as exc:
        raise OracleFailure(f"{type(exc).__name__} with {flags}: {exc}") from exc
    finally:
        elapsed = time.perf_counter() - start
        if measure_memory:
            peak = tracemalloc.get_traced_memory()[1] / 2**20
            tracemalloc.stop()
    if elapsed > TIME_LIMIT_SEC:
        raise OracleFailure(f"took {elapsed:.2f} s (limit {TIME_LIMIT_SEC} s) with {flags}")
    if measure_memory and peak > MEMORY_LIMIT_MIB:
        raise OracleFailure(f"allocated {peak:.0f} MiB (limit {MEMORY_LIMIT_MIB}) with {flags}")
    return outcome


def _qiskit_cost(op, user_gates: set) -> int:
    """Gate applications of one Qiskit instruction, counted the way MAX_EXPANDED_GATES is:
    a user-defined gate costs the sum of its body (at least 1), every other gate 1."""
    if op.name == "if_else":
        return sum(_qiskit_cost(inner.operation, user_gates) for inner in op.blocks[0].data)
    if op.name in user_gates and op.definition is not None:
        return max(1, sum(_qiskit_cost(inner.operation, user_gates)
                          for inner in op.definition.data))
    return 1


def qiskit_expanded_count(text: str, user_gates: set) -> int:
    """Expanded gate count of a barrier-free program read by Qiskit's OpenQASM 2.0 parser
    (``QuantumCircuit.from_qasm_str``: qasm2 with the legacy gate set, as the compile checks
    read circuits)."""
    from qiskit import QuantumCircuit
    circuit = QuantumCircuit.from_qasm_str(text)
    return sum(_qiskit_cost(inst.operation, user_gates) for inst in circuit.data)


def _statevector(text: str):
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector
    circuit = QuantumCircuit.from_qasm_str(text)
    circuit.remove_final_measurements(inplace=True)
    return Statevector(circuit)


def grammar_oracle(program, qiskit: bool = True) -> str:
    """Harness 2. A program the validator accepts must prepare for both run modes (the pytket
    round-trip), parse in Qiskit's qasm2, have the expanded-gate count Qiskit's parse gives,
    and (statevector-compatible programs up to 8 qubits) prepare to the same state as the
    input, up to global phase. Returns 'accepted' or 'refused'."""
    from fastapi import HTTPException
    from services.circuit_resolver import (
        StatevectorIncompatible, prepare_measured_dispatch, prepare_statevector_dispatch,
    )
    from services.validator import expanded_counts, validate_request
    text = program.text()
    start = time.perf_counter()
    try:
        validate_request(text, mode="measured")
    except HTTPException as exc:
        if exc.status_code != 400:
            raise OracleFailure(f"status {exc.status_code}: {exc.detail!r}") from exc
        return "refused"
    except Exception as exc:
        raise OracleFailure(f"validator raised {type(exc).__name__}: {exc}") from exc
    if time.perf_counter() - start > TIME_LIMIT_SEC:
        raise OracleFailure("validator took over the time limit")
    try:
        prepare_measured_dispatch(text, apply_preprocessing=True)
    except Exception as exc:
        raise OracleFailure(f"measured preparation raised {type(exc).__name__}: {exc}") from exc
    try:
        prepared = prepare_statevector_dispatch(text, apply_preprocessing=True)["qasm"]
    except StatevectorIncompatible:
        prepared = None
    except Exception as exc:
        raise OracleFailure(f"statevector preparation raised {type(exc).__name__}: {exc}") from exc
    if not qiskit:
        return "accepted"
    plain = program.text(barriers=False)
    user_gates = {name for name, *_ in program.gates}
    try:
        reference = qiskit_expanded_count(plain, user_gates)
    except Exception as exc:
        raise OracleFailure(f"Qiskit qasm2 refused an accepted program: {exc}") from exc
    counted = expanded_counts(plain)[0]
    if counted != reference:
        raise OracleFailure(f"expanded gate count {counted}, Qiskit's parse gives {reference}")
    n_qubits = sum(size for _, size in program.qregs)
    if prepared is not None and n_qubits <= 8:
        import numpy as np
        before, after = _statevector(text), _statevector(prepared)
        fidelity = abs(np.vdot(before.data, after.data)) ** 2
        if fidelity < 1 - 1e-9:
            raise OracleFailure(f"prepared statevector circuit has fidelity {fidelity:.12f} "
                                f"with the input")
    return "accepted"


def large_inputs(size: int = 1_000_000) -> dict:
    """Circuits of about ``size`` characters, each one construct repeated: the inputs whose
    cost grows with length (blank lines, comments, declarations, gate bodies, operand lists,
    expressions), for the time limit on a full-size request."""
    head = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
    q = head + "qreg q[2];\ncreg c[2];\n"

    def fill(prefix, unit, suffix=""):
        return prefix + unit * max(1, (size - len(prefix) - len(suffix)) // len(unit)) + suffix

    def numbered(prefix, template, width):
        return prefix + "".join(template.format(i) for i in range(size // width))
    return {
        "blank_lines": fill(q, "\n", "h q[0];\n"),
        "spaces": fill(q + "h", " ", " q[0];\n"),
        "line_comments": fill(q, "// comment /* closed */ here\n", "h q[0];\n"),
        "long_comment": fill(q + "//", "a", "\nh q[0];\n"),
        "block_openers": fill(head, "/*"),
        "line_comment_openers": fill(head, "// /*\n"),
        "zero_cregs": numbered(q, "creg z{}[0];\n", 16),
        "gate_body": fill(q + "gate g a {\n", "x a;\n", "}\ng q[0];\n"),
        "gate_body_params": fill(q + "gate g(t) a {\n", "rz(t*2+1) a;\n", "}\ng(1) q[0];\n"),
        "gate_definitions": numbered(q, "gate g{} a {{ x a; }}\n", 24),
        "barrier_operands": fill(q + "barrier q[0]", ", q[1]", ";\n"),
        "cx_operands": fill(q + "cx q[0]", ", q[1]", ";\n"),
        "expression_terms": fill(q + "rz(0", "+1", ") q[0];\n"),
        "expression_parens": fill(q + "rz(", "(", "1) q[0];\n"),
        "if_statements": fill(q + "measure q -> c;\n", "if(c==1) x q[0];\n"),
        "semicolons": fill(q, ";"),
        "braces": fill(q, "{}"),
        "names": fill(q + "h ", "q", "[0];\n"),
        "digits": fill(q + "h q[", "0", "];\n"),
        "decimal": fill(q + "rz(0.", "0", "1) q[0];\n"),
        "headers": fill("", "OPENQASM 2.0;\n"),
        "qasm3": fill("", "bit "),
    }
