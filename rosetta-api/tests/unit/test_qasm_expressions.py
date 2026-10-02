"""tket's parameter rounding as the API predicts it, and insertion of qelib1.inc definitions
for gates a parser lacks."""
import math

from qrosetta_commons.qasm_expressions import tket_parameter_note, tket_rounded_parameters
from qrosetta_commons.qelib1 import add_qelib1_definitions, qelib1_definitions

HEAD = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\n'


def test_parameters_tket_moves_are_found_and_others_are_not():
    qasm = HEAD + ("rz(1.3e-13) q[0];\nrz(1e-9) q[0];\nrz(3.14159265359) q[0];\nrz(0.3) q[0];\n"
                   "u3(pi/4+1e-12,0,pi) q[1];\nrz(pi) q[0];\nrz(0.1*pi+1e-12) q[0];\n")
    moved = [(name, text) for name, text, _value, _stored in tket_rounded_parameters(qasm)]
    assert moved == [("rz", "1.3e-13"), ("rz", "3.14159265359"), ("u3", "pi/4+1e-12")]
    stored = {text: s for _n, text, _v, s in tket_rounded_parameters(qasm)}
    assert stored["3.14159265359"] == math.pi and stored["1.3e-13"] == 0


def test_constant_parameters_inside_definitions_count_and_arguments_do_not():
    qasm = HEAD + "gate g(a) x { rz(a) x; rz(2e-12) x; }\ng(1e-13) q[0];\n"
    assert [text for _n, text, _v, _s in tket_rounded_parameters(qasm)] == ["2e-12", "1e-13"]


def test_note_names_the_parameters_and_is_none_without_any():
    assert tket_parameter_note(HEAD + "rz(0.3) q[0];\n", "tket") is None
    note = tket_parameter_note(HEAD + "rz(1.3e-13) q[0];\n", "tket, which builds this backend's circuit,")
    assert note.startswith("tket, which builds this backend's circuit, sets a gate parameter within 1e-11")
    assert "rz(1.3e-13) -> 0 (moved -1.3e-13 rad)" in note


def test_api_round_trip_records_the_moved_parameters():
    import pytest
    pytest.importorskip("pytket")
    from services.circuit_resolver import prepare_statevector_dispatch
    on = prepare_statevector_dispatch(HEAD + "rz(1.3e-13) q[0];\nh q[1];\n", True)
    assert any(n.startswith("API: tket, in the pytket round-trip, sets") for n in on["api_preprocessing_applied"])
    off = prepare_statevector_dispatch(HEAD + "rz(1.3e-13) q[0];\nh q[1];\n", False)
    assert not any("tket" in n for n in off["api_preprocessing_applied"])


def test_tket_runners_get_the_note_only_for_text_tket_has_not_built():
    from services.job_manager import _TKET_RUNNERS, _apply_api_preprocessing
    assert "qiskit" in _TKET_RUNNERS and "qibo" not in _TKET_RUNNERS
    results = [{"simulator": "qiskit~opt1~run1", "preprocessing_applied": ["parse"]},
               {"simulator": "qibo", "preprocessing_applied": ["parse"]}]
    _apply_api_preprocessing(results, "statevector",
                             {"qasm": HEAD + "rz(1.3e-13) q[0];\n", "api_preprocessing_applied": []})
    assert results[0]["preprocessing_applied"][-1].startswith("tket, which builds this backend's circuit,")
    assert results[1]["preprocessing_applied"] == ["parse"]


def test_qelib1_definitions_are_inserted_in_dependency_order():
    qasm = HEAD + "gate mine a,b { ch a,b; }\nmine q[0],q[1];\ncp(0.3) q[0],q[1];\n"
    out, added = add_qelib1_definitions(qasm, {"ch", "cp", "p"})
    assert added == ["ch", "p", "cp"]
    lines = out.splitlines()
    assert lines[2] == qelib1_definitions()["ch"] and lines[3].startswith("gate p(lambda)")
    assert add_qelib1_definitions(qasm.replace('include "qelib1.inc";\n', ""), {"ch"}) == (
        qasm.replace('include "qelib1.inc";\n', ""), [])


def test_user_definitions_win_and_builtins_can_be_rewritten():
    qasm = HEAD + "gate ch a,b { cx a,b; }\nch q[0],q[1];\nu(0.1,0.2,0.3) q[0];\n"
    out, added = add_qelib1_definitions(qasm, {"ch", "u"}, builtin_rewrites={"U": "u3"})
    assert added == ["u"] and "gate u(theta,phi,lambda) q { u3(theta,phi,lambda) q; }" in out


def test_exact_dumps_keeps_every_angle_and_restores_qiskit():
    import pytest
    qiskit = pytest.importorskip("qiskit")
    from qiskit import qasm2
    from qrosetta_commons.qiskit_circuits import exact_qasm2_dumps, qasm_real
    assert [qasm_real(v) for v in (1e-13, 3.0, 5e-324, -0.1)] == ["1.0e-13", "3.0", "5.0e-324", "-0.1"]
    values = [1.3e-13, math.pi + 1e-13, 1 / 3, -2.5e-12]
    circuit = qiskit.QuantumCircuit(1)
    for value in values:
        circuit.rz(value, 0)
    back = qasm2.loads(exact_qasm2_dumps(circuit))
    assert [float(i.operation.params[0]) for i in back.data] == values
    assert "rz(0) q[0];" in qasm2.dumps(circuit)
