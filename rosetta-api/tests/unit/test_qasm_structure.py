"""Submit-time structural checks: duplicate names, non-ASCII characters, register indices,
unknown gates and the header, and that every bundled circuit still passes them."""

import glob
import os

import pytest
from fastapi import HTTPException

from services.benchmark_library import invalid_qasm_reason
from services.validator import validate_request

HEAD = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def _detail(qasm, mode="statevector"):
    with pytest.raises(HTTPException) as exc:
        validate_request(qasm, mode=mode)
    assert exc.value.status_code == 400
    return exc.value.detail


@pytest.mark.parametrize("decls,first,kind", [
    ("qreg q[1];\nqreg q[2];\n", 3, "quantum register"),
    ("qreg q[1];\ncreg c[1];\ncreg c[2];\n", 4, "classical register"),
    ("qreg q[1];\ncreg q[1];\n", 3, "quantum register"),
    ("qreg q[1];\ngate q a { x a; }\n", 3, "quantum register"),
    ("gate g a { x a; }\ngate g a { h a; }\nqreg q[1];\n", 3, "gate"),
])
def test_a_name_declared_twice_is_rejected(decls, first, kind):
    detail = _detail(HEAD + decls + "x q[0];\n", mode="measured")
    assert f"already declared as a {kind} on line {first}" in detail


def test_duplicate_qreg_is_not_merged_into_another_circuit():
    detail = _detail(HEAD + "qreg q[1];\nqreg q[2];\nx q[0];\n")
    assert "Line 4: 'q' is already declared" in detail


@pytest.mark.parametrize("text,where,name", [
    (HEAD + "qreg q[1];\nh q[0];\n", "Line 4, column 2", "NO-BREAK SPACE"),
    (HEAD + "qreg qü[2];\n", "Line 3, column 7", "LATIN SMALL LETTER U WITH DIAERESIS"),
])
def test_non_ascii_characters_are_named_with_their_position(text, where, name):
    detail = _detail(text)
    assert where in detail and name in detail


def test_non_ascii_inside_comments_is_allowed():
    validate_request(HEAD + "// Grover’s search\nqreg q[1];\nh q[0];\n")


def test_out_of_range_index_names_register_and_size():
    detail = _detail(HEAD + "qreg q[2];\ncx q[0],q[2];\n")
    assert "q[2] is outside the declared register 'q', which has 2 qubits (indices 0 to 1)" in detail


def test_undeclared_register_operand():
    assert "'r' is not a declared register" in _detail(HEAD + "qreg q[2];\nh r[0];\n")


@pytest.mark.parametrize("op,hint", [("H q[0];", "Did you mean 'h'?"),
                                     ("cnot q[0],q[1];", "Did you mean 'cx'?")])
def test_unknown_gate_names_suggest_the_qelib1_name(op, hint):
    detail = _detail(HEAD + "qreg q[2];\n" + op + "\n")
    assert "Line 4: unknown gate" in detail and hint in detail


def test_qelib1_gate_without_the_include():
    detail = _detail("OPENQASM 2.0;\nqreg q[1];\nh q[0];\n")
    assert "add 'include \"qelib1.inc\";'" in detail


def test_unknown_gate_inside_a_definition():
    detail = _detail(HEAD + "gate g a { foo a; }\nqreg q[1];\ng q[0];\n")
    assert "unknown gate 'foo' (inside the definition of 'g')" in detail


@pytest.mark.parametrize("text", ['include "qelib1.inc";\nqreg q[1];\nh q[0];\n',
                                  "qreg q[2]\nh q[0]\n",
                                  "// a comment\nqreg q[2];\nOPENQASM 2.0;\n"])
def test_missing_header(text):
    assert "must start with the header 'OPENQASM 2.0;'" in _detail(text)


def test_openqasm3_keeps_its_own_message():
    assert "OpenQASM 3 is not supported" in _detail("qubit[2] q;\nh q[0];\n")


def test_valid_program_with_definitions_conditions_and_opaque_passes():
    validate_request(HEAD + "opaque magic(a) b;\ngate g(t) a, b { rz(t) a; cx a, b; }\n"
                     "qreg q[2];\ncreg c[2];\ng(pi/2) q[0], q[1];\nh q;\nbarrier q;\n"
                     "measure q -> c;\nif(c==1) x q[0];\n", mode="measured")


def _bundled():
    files = glob.glob(os.path.join(ROOT, "benchmarks", "**", "*.qasm"), recursive=True)
    files += glob.glob(os.path.join(ROOT, "circuits", "*.qasm"))
    return sorted(files)


def test_every_bundled_circuit_passes_the_structural_checks():
    from services.qasm_structure import check_ascii, check_structure
    checked = 0
    for path in _bundled():
        with open(path, encoding="utf-8") as fh:
            qasm = fh.read()
        if invalid_qasm_reason(qasm):
            continue
        check_ascii(qasm)
        check_structure(qasm)
        checked += 1
    assert checked > 300


def test_every_algorithm_template_passes_the_structural_checks():
    from services import circuit_library
    from services.qasm_structure import check_ascii, check_structure
    for algorithm in circuit_library.PRESET_ORDER:
        for n in (2, 3, 5):
            qasm = circuit_library.generate_circuit(algorithm, n)
            check_ascii(qasm)
            check_structure(qasm)


@pytest.mark.parametrize("body,expected", [
    ("qreg a[2];\nqreg b[3];\ncx a,b;\n", "Line 5: 'cx' broadcasts over registers of different sizes (a[2], b[3])"),
    ("qreg q[2];\ncx q[0];\n", "Line 4: 'cx' acts on 2 qubits, but the call lists 1 operand"),
    ("qreg q[2];\ncx q[0] q[1];\n", "Line 4: 'cx' acts on 2 qubits, but the call lists 1 operand"),
    ("qreg q[2];\nrx q[0];\n", "Line 4: 'rx' takes 1 parameter in parentheses, but the call gives 0"),
    ("qreg q[2];\nh(0.1) q[0];\n", "Line 4: 'h' takes 0 parameters in parentheses, but the call gives 1"),
    ("qreg q[2];\ncx q[0],q[0];\n", "Line 4: 'cx' names q[0] more than once"),
    ("qreg q[2];\ncx q,q[1];\n", "Line 4: 'cx' names q[1] more than once"),
    ("qreg q[1];\n;\nh q[0];\n", "Line 4: a semicolon with no statement before it"),
    ("qreg q[1];\nh q[0];;\n", "Line 4: a semicolon with no statement before it"),
    ("qreg q[1];\nh\x0bq[0];\n", "Line 4, column 2: control character U+000B (vertical tab)"),
    ("qreg q[1];\ncreg c[1];\nh c[0];\n", "Line 5: 'c' is a classical register; 'h' acts on qubits"),
    ("gate g a, b { cx a; }\nqreg q[2];\ng q[0], q[1];\n",
     "Line 3: 'cx' (inside the definition of 'g') acts on 2 qubits"),
    ("gate g a, b { cx a, a; }\nqreg q[2];\ng q[0], q[1];\n",
     "Line 3: 'cx' (inside the definition of 'g') names 'a' twice"),
    ("gate g a { h b; }\nqreg q[1];\ng q[0];\n",
     "Line 3: 'b' (inside the definition of 'g') is not one of the gate's qubit arguments"),
    ("qreg q[2];\ncreg c[2];\nmeasure q[0], q[1] -> c;\n", "Line 5: measure is written"),
])
def test_malformed_calls_are_rejected_with_their_line(body, expected):
    assert expected in _detail(HEAD + body, mode="measured")


def test_short_version_header_is_rejected():
    detail = _detail('OPENQASM 2;\ninclude "qelib1.inc";\nqreg q[1];\nh q[0];\n')
    assert "Line 1: write the version as 'OPENQASM 2.0;'" in detail


@pytest.mark.parametrize("body,line", [
    ("opaque myop a;\nqreg q[1];\nmyop q[0];\n", 5),
    ("opaque myop(t) a, b;\nqreg q[2];\ncreg c[1];\nif(c==0) myop(0.1) q[0], q[1];\n", 6),
    ("opaque myop a;\ngate g a { myop a; }\nqreg q[1];\ng q[0];\n", 4),
])
def test_a_call_of_an_opaque_gate_is_rejected(body, line):
    detail = _detail(HEAD + body, mode="measured")
    assert f"Line {line}: 'myop'" in detail and "declared 'opaque' on line 3" in detail


@pytest.mark.parametrize("text,line,name", [
    ("qreg x[1];\ncreg c[1];\nmeasure x[0] -> c[0];\n", 3, "x"),
    ("qreg q[1];\ncreg h[1];\nmeasure q[0] -> h[0];\n", 4, "h"),
    ("qreg q[1];\ncreg U[1];\nmeasure q[0] -> U[0];\n", 4, "U"),
])
def test_a_register_named_like_an_included_gate_is_a_duplicate_name(text, line, name):
    detail = _detail(HEAD + text, mode="measured")
    assert f"Line {line}: '{name}' is already declared as a" in detail
    assert "rename the register" in detail


def test_a_register_named_like_a_qelib1_gate_is_allowed_without_the_include():
    validate_request("OPENQASM 2.0;\nqreg x[1];\nU(0.1,0,0) x[0];\n")


def test_broadcasts_over_equal_registers_and_a_register_with_an_index_pass():
    validate_request(HEAD + "qreg a[2];\nqreg b[2];\ncx a,b;\ncx a[0],b;\nh a;\nbarrier a,a[0];\n")
