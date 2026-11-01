"""The V4 known-answer reference and checks (scripts/verify/): gate matrices from qelib1.inc
against textbook matrices, the generated cases, and each check's PASS and FAIL rules."""

import base64
import math
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts" / "verify"))

import qelib1_reference as ref  # noqa: E402
import v4_cases  # noqa: E402
import v4_check  # noqa: E402

sys.path.remove(str(REPO / "scripts" / "verify"))

from services.selftest import reference as selftest_reference  # noqa: E402

LIB = ref.GateLibrary()
H = np.array([[1, 1], [1, -1]]) / math.sqrt(2)
X = np.array([[0, 1], [1, 0]])
Z = np.diag([1, -1])
SX = np.array([[1 + 1j, 1 - 1j], [1 - 1j, 1 + 1j]]) / 2


def _equal_up_to_phase(a, b):
    i = np.argmax(abs(b))
    phase = a.flat[i] / b.flat[i]
    return math.isclose(abs(phase), 1, abs_tol=1e-9) and np.allclose(a, phase * b, atol=1e-9)


def _controlled(u, controls):
    """Controlled-u with operands 0..controls-1 as controls and the last as target (lsb)."""
    k = controls + 1
    m = np.eye(2 ** k, dtype=complex)
    on = (1 << controls) - 1
    idx = [on, on | (1 << controls)]
    m[np.ix_(idx, idx)] = u
    return m


@pytest.mark.parametrize("name,params,matrix", [
    ("h", (), H), ("x", (), X), ("z", (), Z), ("sx", (), SX),
    ("cx", (), _controlled(X, 1)), ("ccx", (), _controlled(X, 2)), ("c3x", (), _controlled(X, 3)),
    ("c4x", (), _controlled(X, 4)), ("ch", (), _controlled(H, 1)), ("csx", (), _controlled(SX, 1)),
    ("c3sqrtx", (), _controlled(SX, 3)), ("swap", (), np.eye(4)[[0, 2, 1, 3]]),
    ("cu1", (0.7,), _controlled(np.diag([1, np.exp(0.7j)]), 1)),
    ("crz", (0.7,), _controlled(np.diag([np.exp(-0.35j), np.exp(0.35j)]), 1)),
    ("rzz", (0.7,), np.diag(np.exp(-0.35j * np.array([1, -1, -1, 1])))),
])
def test_gate_matrices_from_qelib1_equal_the_textbook_matrices(name, params, matrix):
    assert _equal_up_to_phase(LIB.matrix(name, params), np.asarray(matrix, dtype=complex))


def test_every_qelib1_gate_is_unitary_and_generated():
    for name in LIB.names():
        k = LIB.arity(name)
        m = LIB.matrix(name, tuple(0.37 * (i + 1) for i in range(LIB.parameter_count(name))))
        assert np.allclose(m.conj().T @ m, np.eye(2 ** k), atol=1e-12), name
    gates = {c["gate"] for c in v4_cases.build() if c["family"] == "gate"}
    assert gates == set(LIB.names())


def test_expressions_accept_python_keywords_and_exponents():
    assert ref.evaluate("-(phi+lambda)/2", {"phi": 1.0, "lambda": 2.0}) == -1.5
    assert ref.evaluate("1.5e-3*pi", {}) == pytest.approx(1.5e-3 * math.pi)
    with pytest.raises(ref.ReferenceError):
        ref.evaluate("__import__('os')", {})


def test_reference_equals_the_selftest_reference():
    qasm = (REPO / "rosetta-api" / "circuits" / "selftest" / "sv_distinct_amplitudes.qasm").read_text()
    assert ref.fidelity(selftest_reference.statevector(qasm), ref.statevector(qasm)) == pytest.approx(1, abs=1e-14)


def test_cases_are_fixed_and_their_relations_hold_in_the_reference():
    first, second = v4_cases.build(), v4_cases.build()
    assert [c["qasm"] for c in first] == [c["qasm"] for c in second]
    by_name = {c["name"]: c for c in first}
    for case in first:
        if "pair" in case:
            renamed = v4_check.permute(by_name[case["pair"]]["expected"], case["perm"])
            assert ref.fidelity(renamed, case["expected"]) == pytest.approx(1, abs=1e-12), case["name"]
        if case["family"] == "inverse":
            assert abs(case["expected"][0]) == pytest.approx(1, abs=1e-9)


def _result(state, ordering="lsb", **extra):
    vector = ref.to_order(np.asarray(state, dtype=complex), ordering)
    return {"dispatch_status": "ok", "qubit_ordering": ordering,
            "statevector": base64.b64encode(vector.astype(np.complex128).tobytes()).decode(), **extra}


def test_statevector_check_reads_the_declared_order():
    case = next(c for c in v4_cases.build() if c["name"] == "gate-cx-0")
    assert v4_check.statevector_row(case, "b", _result(case["expected"], "msb"))["status"] == "PASS"
    reversed_but_lsb = _result(ref.to_order(case["expected"], "msb"), "lsb")
    assert v4_check.statevector_row(case, "b", reversed_but_lsb)["status"] == "FAIL"
    refused = {"dispatch_status": "error", "error": "unsupported gate"}
    assert v4_check.statevector_row(case, "b", refused)["status"] == "REFUSED"
    assert v4_check.statevector_row(case, "b", {"dispatch_status": "timeout"})["status"] == "NO_RESULT"


def test_relation_check_compares_a_backend_with_itself():
    cases = {c["name"]: c for c in v4_cases.build()}
    a, b = cases["relabel-0-a"], cases["relabel-0-b"]
    wrong = np.roll(a["expected"], 1)
    ok = v4_check.relation_row(b, a, "x", _result(v4_check.permute(wrong, b["perm"])), _result(wrong))
    assert ok["status"] == "PASS"
    bad = v4_check.relation_row(b, a, "x", _result(wrong), _result(wrong))
    assert bad["status"] == "FAIL"


def test_goodness_of_fit_and_support():
    dist = {"00": 0.5, "11": 0.5}
    p, df, outside = v4_check.goodness_of_fit({"00": 4100, "11": 4100}, dist)
    assert p == pytest.approx(1) and df == 1 and outside == 0
    p, _df, _outside = v4_check.goodness_of_fit({"00": 4600, "11": 3600}, dist)
    assert p < 1e-20
    assert v4_check.goodness_of_fit({"00": 4100, "11": 4099, "01": 1}, dist)[2] == 1


def test_counts_check_reverses_msb_keys_and_holm_decides():
    case = {"name": "c", "family": "gate", "n_qubits": 2, "distribution": {"01": 1.0}}
    rows = [v4_check.counts_row(case, "lsb-backend", {"dispatch_status": "ok", "qubit_ordering": "lsb",
                                                      "counts": {"01": 100}}, 100),
            v4_check.counts_row(case, "msb-backend", {"dispatch_status": "ok", "qubit_ordering": "msb",
                                                      "counts": {"10": 100}}, 100),
            v4_check.counts_row(case, "wrong", {"dispatch_status": "ok", "qubit_ordering": "lsb",
                                                "counts": {"10": 100}}, 100)]
    assert [r["status"] for r in v4_check.holm(rows)] == ["PASS", "PASS", "FAIL"]


def test_holm_rejects_in_order_and_stops():
    rows = [{"status": "PENDING", "p_value": p} for p in (1e-9, 0.004, 0.2)]
    assert [r["status"] for r in v4_check.holm(rows, alpha=0.01)] == ["FAIL", "FAIL", "PASS"]


def test_an_override_changes_only_the_gates_it_names():
    reversed_cu3 = ref.GateLibrary(overrides={"cu3": lambda m, p: ref.reverse_operands(m)})
    assert _equal_up_to_phase(reversed_cu3.matrix("cu3", (0.3, 0.5, 0.9)),
                              ref.reverse_operands(LIB.matrix("cu3", (0.3, 0.5, 0.9))))
    flipped_cu1 = ref.GateLibrary(overrides={"cu1": lambda m, p: LIB.matrix("crz", p)})
    assert _equal_up_to_phase(flipped_cu1.matrix("c4x"), LIB.matrix("c4x"))


def test_a_fail_is_labelled_only_by_a_model_that_reproduces_it():
    case = next(c for c in v4_cases.build() if c["name"] == "gate-cu3-1")
    model = ref.GateLibrary(overrides={"cu3": lambda m, p: ref.reverse_operands(m)})
    wrong = ref.statevector(case["qasm"], model)
    for backend, labelled in (("pennylane-default", "pennylane-qubitunitary-wire-order"), ("qiskit", None)):
        result = _result(wrong, "msb")
        rows = v4_check.evaluate([case], {case["name"]: {backend: result}}, "statevector",
                                 dispatched={case["name"]: {backend: case["qasm"]}})
        assert rows[0]["status"] == "FAIL" and rows[0].get("explained_by") == labelled


def test_the_qibo_fusion_model_reads_the_executed_text_at_levels_one_and_up():
    case = next(c for c in v4_cases.build() if c["name"] == "gate-ch-0")
    executed = case["qasm"].replace('include "qelib1.inc";\n', 'include "qelib1.inc";\n'
                                    "gate ch a,b { h b; sdg b; cx a,b; h b; t b; cx a,b; t b; h b; s b; x b; s a; }\n")
    dropped = ref.statevector(executed, ref.GateLibrary(overrides={"ch": lambda m, p: np.eye(4, dtype=complex)}))
    for level, labelled in ((2, "qibo-fuse-drops-defined-gates"), (0, None)):
        result = _result(dropped, "msb", transpiled_qasm=executed, optimization_level=level)
        rows = v4_check.evaluate([case], {case["name"]: {"qibo": result}}, "statevector",
                                 dispatched={case["name"]: {"qibo": case["qasm"]}})
        assert rows[0]["status"] == "FAIL" and rows[0].get("explained_by") == labelled
