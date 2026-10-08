"""Legal OpenQASM 2.0 forms that must run, and illegal ones that must be refused at submit
with their line: index spacing, block comments, register-name case, use before declaration,
measure sizes, gate-body parameter names, keyword-like parameter names."""
import pytest
from fastapi import HTTPException

from services.circuit_resolver import (
    normalise_index_spacing, prepare_measured_dispatch, prepare_statevector_dispatch,
)
from services.validator import validate_request

HEAD = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'


def _detail(qasm, **kwargs):
    with pytest.raises(HTTPException) as caught:
        validate_request(qasm, **kwargs)
    assert caught.value.status_code == 400
    return caught.value.detail


@pytest.mark.parametrize("body", [
    "qreg q[2];\nh q [0];\ncx q[0], q [1];\n",
    "qreg  q [ 2 ] ;\nh q [ 0 ] ;\ncx q[0] , q[1];\n",
    "qreg q[2];\ncreg c [2];\nh q[0];\nmeasure q [0] -> c [ 0 ];\n",
])
def test_spaces_around_register_indices_are_accepted_and_removed_before_pytket(body):
    pytest.importorskip("pytket")
    qasm = HEAD + body
    validate_request(qasm, mode="measured")
    text, note = normalise_index_spacing(qasm)
    assert " [" not in text and "[ " not in text and note.startswith("API: removed spaces")
    if "measure" in body:
        out = prepare_measured_dispatch(qasm, True)["measured_native"]
    else:
        out = prepare_statevector_dispatch(qasm, True)
    assert out["api_preprocessing_applied"][0] == note
    assert "cx q[0],q[1];" in out["qasm"] or "measure q[0] -> c[0];" in out["qasm"]


def test_text_without_index_spaces_is_unchanged():
    qasm = HEAD + "// keep\nqreg q[1];\nh q[0];\n"
    assert normalise_index_spacing(qasm) == (qasm, None)


def test_preprocessing_off_dispatches_the_spaced_text_unchanged():
    qasm = HEAD + "qreg q[2];\nh q [0];\n"
    assert prepare_statevector_dispatch(qasm, False)["qasm"] == qasm


@pytest.mark.parametrize("pre", [True, False])
def test_block_comments_are_refused_with_their_line(pre):
    qasm = HEAD + "qreg q[1];\n/* a\nb */\nh q[0];\n"
    assert _detail(qasm, apply_preprocessing=pre).startswith(
        "Line 4: '/* ... */' comments are not part of OpenQASM 2.0")


def test_block_comment_markers_inside_a_line_comment_are_text():
    validate_request(HEAD + "qreg q[1];\n// see /* here */\nh q[0];\n")


def test_bundled_circuits_skip_the_block_comment_check():
    validate_request(HEAD + "qreg q[1];\n/* note */\nh q[0];\n", check_reserved_names=False)


@pytest.mark.parametrize("decl,line,name,suggestion", [
    ("qreg Q[1];\nh Q[0];\n", 3, "Q", "q"),
    ("qreg _q[1];\nh _q[0];\n", 3, "_q", "qq"),
    ("qreg q[1];\ncreg C[1];\nmeasure q[0] -> C[0];\n", 4, "C", "c"),
])
def test_a_register_name_must_start_lowercase(decl, line, name, suggestion):
    detail = _detail(HEAD + decl, mode="measured")
    assert detail.startswith(f"Line {line}: register name '{name}' must start with a lowercase letter")
    assert f"for example to '{suggestion}'" in detail


def test_mixed_case_after_the_first_letter_is_accepted():
    validate_request(HEAD + "qreg qA_1[1];\nh qA_1[0];\n")


@pytest.mark.parametrize("body,expected", [
    ("qreg q[1];\ng q[0];\ngate g a { h a; }\n",
     "Line 4: gate 'g' is used before its declaration on line 5"),
    ("qreg q[1];\nh q[0]; gate g a { h a; } g q[0];\nh r[0];\nqreg r[1];\n",
     "Line 5: quantum register 'r' is used before its declaration on line 6"),
    ("qreg q[1];\nmeasure q[0] -> c[0];\ncreg c[1];\n",
     "Line 4: classical register 'c' is used before its declaration on line 5"),
])
def test_use_before_declaration_is_refused(body, expected):
    assert expected in _detail(HEAD + body, mode="measured")


@pytest.mark.parametrize("body,expected", [
    ("qreg a[2];\ncreg c[2];\nmeasure a[0] -> c;\n",
     "Line 5: measure a[0] -> c has operands of different sizes (1 qubit, 2 bits)"),
    ("qreg a[2];\ncreg c[3];\nmeasure a -> c;\n",
     "Line 5: measure a -> c has operands of different sizes (2 qubits, 3 bits)"),
    ("qreg a[2];\ncreg c[2];\nmeasure c -> a;\n",
     "Line 5: measure reads a quantum register and writes a classical one"),
])
def test_measure_size_and_kind_errors_name_the_line(body, expected):
    assert expected in _detail(HEAD + body, mode="measured")


@pytest.mark.parametrize("body,expected", [
    ("gate g a { rz(t) a; }\nqreg q[1];\ng q[0];\n",
     "Line 3: 't' in the parameter 't' of 'rz' (inside the definition of 'g') is not a parameter "
     "of 'g' (it has no parameters)"),
    ("gate g(theta) a { rz(theta + phi) a; }\nqreg q[1];\ng(1) q[0];\n",
     "Line 3: 'phi' in the parameter 'theta + phi' of 'rz' (inside the definition of 'g') is not "
     "a parameter of 'g' (its parameters are theta)"),
])
def test_unknown_names_in_gate_body_parameters_name_the_line(body, expected):
    assert expected in _detail(HEAD + body)


def test_numbers_with_exponents_in_gate_bodies_are_not_names():
    validate_request(HEAD + "gate g(t) a { rz(2.5E+0*t + 1e-3) a; }\nqreg q[1];\ng(1) q[0];\n")


@pytest.mark.parametrize("name", ["lambda", "in", "is", "if", "or", "not", "for", "as", "def",
                                  "None", "True", "class", "lambda_"])
@pytest.mark.parametrize("pre", [True, False])
def test_keyword_like_parameter_names_are_accepted(name, pre):
    qasm = HEAD + (f"gate g(theta,phi,{name}) a {{ u3(theta,phi,{name}) a; }}\n"
                   f"qreg q[1];\ng(0.1,0.2,0.3) q[0];\n")
    validate_request(qasm, apply_preprocessing=pre)


def test_parameter_values_are_still_checked_through_a_keyword_name():
    qasm = HEAD + "gate g(lambda) a { rz(lambda*1e7) a; }\nqreg q[1];\ng(1) q[0];\n"
    assert "exceeds 1e+06" in _detail(qasm)


def test_an_uncalled_definition_using_an_opaque_gate_round_trips():
    pytest.importorskip("pytket")
    qasm = HEAD + "opaque zz a;\ngate g a { zz a; }\nqreg q[1];\nh q[0];\n"
    validate_request(qasm)
    assert "h q[0];" in prepare_statevector_dispatch(qasm, True)["qasm"]
