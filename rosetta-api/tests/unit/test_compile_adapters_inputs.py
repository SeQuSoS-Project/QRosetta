"""Inputs the compile-only adapters prepare: qelib1.inc definitions renamed for BQSKit and
inserted for Cirq, identity-only qubits counted as idle for QMAP, pass lines that mention
measurements only when there are some, and the compile input's measurement note."""
import ast
import re
from pathlib import Path

import pytest
from qiskit import QuantumCircuit

from qrosetta_commons.compile_checks import process_infidelity
from qrosetta_commons.qelib1 import qelib1_definitions, renamed_qelib1_definitions
from qrosetta_commons.qiskit_circuits import idle_qubits, translate_to_basis

COMPILERS = Path(__file__).resolve().parents[3] / "compilers"
HEAD = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'


def _source(name):
    return (COMPILERS / f"{name}-compiler" / "main.py").read_text()


def _frozenset_assigned(source, name):
    tree = ast.parse(source)
    node = next(n.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
                and getattr(n.targets[0], "id", "") == name)
    return {elt.value for elt in node.args[0].elts}


def test_renamed_definitions_keep_the_unitary_and_rename_calls_inside_definitions():
    qasm = HEAD + "qreg q[5];\nh q[0];\nh q[1];\nry(0.4) q[2];\nc4x q[0],q[1],q[2],q[3],q[4];\nu0(1) q[2];\n"
    out, renames = renamed_qelib1_definitions(qasm, {"c3x", "c3sqrtx", "c4x", "rc3x", "u0"})
    assert renames == {"c3x": "qelib1_c3x", "c3sqrtx": "qelib1_c3sqrtx", "c4x": "qelib1_c4x", "u0": "qelib1_u0"}
    assert not re.search(r"(?<![\w.])(c3x|c3sqrtx|c4x|u0)\b(?!\.)", out.replace("qelib1.inc", ""))
    assert "gate qelib1_c4x a,b,c,d,e" in out and "qelib1_c3x a,b,c,d;" in out
    assert process_infidelity(qasm, out) < 1e-12


def test_renamed_definitions_avoid_names_the_circuit_uses_and_leave_other_circuits_alone():
    qasm = HEAD + "gate qelib1_c3x a { h a; }\nqreg q[4];\nqelib1_c3x q[0];\nc3x q[0],q[1],q[2],q[3];\n"
    out, renames = renamed_qelib1_definitions(qasm, {"c3x"})
    assert renames == {"c3x": "qelib1__c3x"} and "qelib1__c3x q[0],q[1],q[2],q[3];" in out
    assert process_infidelity(qasm, out) < 1e-12
    plain = HEAD + "qreg q[2];\nh q[0];\ncx q[0],q[1];\n"
    assert renamed_qelib1_definitions(plain, {"c3x"}) == (plain, {})


def test_bqskit_renames_the_wide_qelib1_gates_and_unfolds_wide_definitions_by_rebuilding():
    source = _source("bqskit")
    assert _frozenset_assigned(source, "BQSKIT_READS_DIFFERENTLY") == {"c3x", "c3sqrtx", "c4x", "rc3x", "u0"}
    assert _frozenset_assigned(source, "BQSKIT_READS_DIFFERENTLY") <= set(qelib1_definitions())
    assert "renamed_qelib1_definitions(" in source and "_unfold_wide_definitions(" in source
    methods = {c.func.attr for c in ast.walk(ast.parse(source))
               if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)}
    assert not methods & {"unfold", "batch_unfold"}
    assert "a gate defined in the circuit" in source


def test_cirq_inserts_the_rc3x_definition_instead_of_refusing():
    source = _source("cirq")
    assert _frozenset_assigned(source, "MATRIX_IMPORTED_GATES") == {"rc3x"}
    parse = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == "_parse")
    calls = {getattr(c.func, "id", "") for c in ast.walk(parse) if isinstance(c, ast.Call)}
    assert "add_qelib1_definitions" in calls
    assert "imports rc3x as a matrix gate" not in source


@pytest.mark.parametrize("body,idle", [
    ("h q[0];\ncx q[0],q[2];\nbarrier q;\nrz(0) q[1];\n", [1]),
    ("h q[0];\nid q[1];\ncx q[0],q[2];\n", [1]),
    ("h q[0];\nu1(0) q[1];\nu3(0,0,0) q[1];\ncx q[0],q[2];\n", [1]),
    ("h q[0];\ncx q[0],q[2];\n", [1]),
    ("h q[0];\nrz(2*pi) q[1];\ncx q[0],q[2];\n", []),
    ("h q[0];\nrz(1e-9) q[1];\ncx q[0],q[2];\n", []),
    ("h q[0];\ncx q[1],q[2];\ncx q[1],q[2];\ncx q[0],q[2];\n", []),
])
def test_identity_only_qubits_are_idle_after_translation(body, idle):
    circuit = translate_to_basis(QuantumCircuit.from_qasm_str(HEAD + "qreg q[3];\n" + body), ("u3", "cx"))
    assert idle_qubits(circuit) == idle


def test_qmap_refuses_identity_only_qubits_before_mapping():
    source = _source("qmap")
    decompose = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == "_decompose")
    calls = {getattr(c.func, "id", "") for c in ast.walk(decompose) if isinstance(c, ast.Call)}
    assert "idle_qubits" in calls and "barriers and identities" in source


def test_measurement_notes_appear_only_with_measurements():
    for name in ("qsynth", "synthetiq"):
        source = _source(name)
        register = next(n.value for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Assign)
                        and getattr(n.targets[0], "id", "") == "_REGISTER_NOTE")
        assert "measure" not in ast.literal_eval(register), name
        assert "[_MEASURE_NOTE] if measures else []" in source, name


def test_compile_input_note_says_compiled_circuits_have_no_measurements():
    import services.compilation as compilation
    notes = compilation.compile_input_notes([
        "API: removed 2 terminal measurement(s); statevector mode reports the pre-measurement "
        "state (comments removed, classical registers kept)", "API: merged registers"])
    assert notes[0] == ("API: removed 2 terminal measurement(s); compilers receive the unitary part, so "
                        "the compiled circuits have no measurements (comments removed, classical "
                        "registers kept)")
    assert notes[1] == "API: merged registers"
    assert "compiled circuits have no measurements" in compilation.COMPILE_INPUT_DERIVATION
