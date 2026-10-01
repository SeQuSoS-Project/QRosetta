"""Tests for the API-side dispatch copies built by services/circuit_resolver.py."""
import numpy as np
import pytest

from services.circuit_resolver import (
    append_measure_all,
    declared_registers,
    flatten_qregs,
    has_measurements,
    prepare_measured_dispatch,
    prepare_statevector_dispatch,
    StatevectorIncompatible,
    strip_terminal_measurements,
)

qiskit = pytest.importorskip("qiskit")
pytest.importorskip("pytket")
from qiskit import qasm2  # noqa: E402
from qiskit.quantum_info import Statevector  # noqa: E402

HEADER = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'

MULTI_QREG = HEADER + """// b is declared first, so it holds flat qubit 0
qreg b[1];
qreg a[2];
x b[0];
h a;
cx b[0],a[1];
barrier a, b[0];
"""


def _statevector(qasm: str) -> np.ndarray:
    circ = qasm2.loads(qasm)
    circ.remove_final_measurements()
    return Statevector(circ).data


def test_append_measure_all_skipped_when_circuit_measures():
    qasm = HEADER + "qreg q[3];\ncreg c[2];\nh q[0];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];\n"
    native = prepare_measured_dispatch(qasm, apply_preprocessing=False)["measured_native"]
    assert native["qasm"] == qasm
    assert native["api_preprocessing_applied"] == []


def test_append_measure_all_uses_a_fresh_register_name():
    qasm = HEADER + "qreg q[2];\ncreg meas[1];\nh q[0];\n"
    out, note = append_measure_all(qasm)
    assert out.startswith(qasm)
    regs = declared_registers(out)
    assert ("creg", "meas0", 2) in regs
    assert "measure q[1] -> meas0[1];" in out
    assert note.startswith("API: ") and "meas0" in note


def test_preprocessing_off_is_textual_and_recorded():
    qasm = HEADER + "gate foo a { u(0.1,0.2,0.3) a; }\nqreg b[1];\nqreg a[1];\nfoo a[0];\nbarrier b[0];\n"
    dispatch = prepare_measured_dispatch(qasm, apply_preprocessing=False)
    assert dispatch["measured_sampled"] == {"qasm": qasm, "api_preprocessing_applied": []}
    native = dispatch["measured_native"]
    assert native["qasm"].startswith(qasm)
    assert "gate foo a" in native["qasm"] and "barrier b[0];" in native["qasm"]
    assert "measure b[0] -> meas[0];" in native["qasm"]
    assert "measure a[0] -> meas[1];" in native["qasm"]
    assert len(native["api_preprocessing_applied"]) == 1
    assert "pytket" not in native["api_preprocessing_applied"][0]
    assert prepare_statevector_dispatch(qasm, apply_preprocessing=False) == {
        "qasm": qasm, "api_preprocessing_applied": []}


def test_flatten_keeps_declaration_order():
    flat, note = flatten_qregs(MULTI_QREG)
    assert [r for r in declared_registers(flat) if r[0] == "qreg"] == [("qreg", "q", 3)]
    assert "b[0..0] -> q[0..0]" in note and "a[0..1] -> q[1..2]" in note
    assert np.allclose(_statevector(flat), _statevector(MULTI_QREG))


def test_preprocessing_on_is_order_safe_through_pytket():
    sv = prepare_statevector_dispatch(MULTI_QREG, apply_preprocessing=True)
    assert np.allclose(_statevector(sv["qasm"]), _statevector(MULTI_QREG))
    notes = sv["api_preprocessing_applied"]
    assert notes[0].startswith("API: merged 2 quantum registers")
    assert any("pytket" in n for n in notes)
    assert any("barrier" in n for n in notes)
    assert "barrier" not in sv["qasm"]


def test_measured_preprocessing_on_measures_in_declaration_order():
    native = prepare_measured_dispatch(MULTI_QREG, apply_preprocessing=True)["measured_native"]
    assert has_measurements(native["qasm"])
    counts_circuit = qasm2.loads(native["qasm"])
    assert [counts_circuit.find_bit(q).index for q in counts_circuit.qubits] == [0, 1, 2]
    assert np.allclose(_statevector(native["qasm"]), _statevector(MULTI_QREG))
    assert native["api_preprocessing_applied"][-1].startswith("API: circuit had no measure")


def test_single_register_is_not_rewritten():
    qasm = HEADER + "qreg q[2];\nh q;\n"
    assert flatten_qregs(qasm) == (qasm, None)


def test_statevector_dispatch_strips_terminal_measurements():
    qasm = HEADER + "qreg q[2];\ncreg c[2];\nh q[0];\nmeasure q[0] -> c[0];\ncx q[1],q[1];\nbarrier q;\nmeasure q -> c;\n"
    qasm = qasm.replace("cx q[1],q[1];\n", "x q[1];\n")
    for pp in (False, True):
        sv = prepare_statevector_dispatch(qasm, apply_preprocessing=pp)
        assert not has_measurements(sv["qasm"])
        assert sv["api_preprocessing_applied"][0].startswith("API: removed 3 terminal measurement(s)")
        assert np.allclose(_statevector(sv["qasm"]), _statevector(qasm))


def test_terminal_measurement_keeps_classical_registers():
    out, note = strip_terminal_measurements(HEADER + "qreg q[1];\ncreg c[1];\nh q[0];\nmeasure q[0] -> c[0];\n")
    assert "creg c[1];" in out and "measure" not in out and note


def test_statevector_dispatch_without_measurements_is_unchanged():
    qasm = HEADER + "qreg q[2];\nh q[0];\n"
    assert strip_terminal_measurements(qasm) == (qasm, None)


@pytest.mark.parametrize("body", [
    "qreg q[2];\ncreg c[2];\nmeasure q -> c;\ncx q[1],q[0];\n",
    "qreg q[1];\nreset q[0];\n",
    "qreg q[1];\ncreg c[1];\nif (c == 1) x q[0];\n",
])
def test_statevector_dispatch_rejects_non_unitary_circuits(body):
    with pytest.raises(StatevectorIncompatible, match="measured mode"):
        prepare_statevector_dispatch(HEADER + body, apply_preprocessing=False)


def test_waves_record_how_many_runs_share_them():
    from services.dispatcher import group_specs_by_phase
    specs = [{"key": "a", "phase": 1}, {"key": "b", "phase": 1}, {"key": "c", "phase": 2}]
    waves = group_specs_by_phase(specs)
    assert [[s["concurrent_runs"] for s in w] for w in waves] == [[2, 2], [1]]
