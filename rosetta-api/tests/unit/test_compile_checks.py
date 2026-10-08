"""Run-time checks of compile-only outputs (qrosetta_commons.compile_checks) and the adapters'
use of them: every adapter records a check of its output, and every image that checks with
Qiskit installs it."""
import ast
import math
import re
from pathlib import Path

import numpy as np
import pytest

from qrosetta_commons import compile_checks
from qrosetta_commons.compile_errors import CompileRefused, OutputRejected

COMPILERS = Path(__file__).resolve().parents[3] / "compilers"
HEADER = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'


def _circuit(n, body):
    return HEADER + f"qreg q[{n}];\n" + body


def test_process_infidelity_is_zero_up_to_global_phase_and_quadratic_in_an_angle_change():
    base = _circuit(2, "h q[0];\ncx q[0],q[1];\nrz(0.3) q[1];\n")
    phased = _circuit(2, "h q[0];\ncx q[0],q[1];\nu1(0.3) q[1];\n")
    moved = _circuit(2, "h q[0];\ncx q[0],q[1];\nrz(0.301) q[1];\n")
    assert compile_checks.process_infidelity(base, phased) < 1e-15
    assert compile_checks.process_infidelity(base, moved) == pytest.approx(1 - math.cos(0.001 / 2), rel=1e-6)


def test_final_measurements_are_ignored_and_a_width_mismatch_is_total_infidelity():
    measured = HEADER + "qreg q[1];\ncreg c[1];\nh q[0];\nmeasure q[0] -> c[0];\n"
    assert compile_checks.process_infidelity(measured, _circuit(1, "h q[0];\n")) < 1e-15
    assert compile_checks.process_infidelity(_circuit(1, "h q[0];\n"), _circuit(2, "h q[0];\n")) == 1.0


def test_check_note_records_the_infidelity_and_rejects_above_the_tolerance():
    source = _circuit(1, "rz(0.3) q[0];\n")
    note = compile_checks.unitary_check_note("X", source, source, 1, 1e-8, "for a reason")
    assert note.startswith("Checked with Qiskit: process infidelity to the input 0 (at most 1e-08 accepted, for a reason)")
    with pytest.raises(OutputRejected, match=r"^X's output has process infidelity 0\.\d+ to the input \(more than 1e-08\)"):
        compile_checks.unitary_check_note("X", source, _circuit(1, "rz(0.5) q[0];\n"), 1, 1e-8, "r")


def test_wide_outputs_are_recorded_as_unchecked_without_building_a_unitary(monkeypatch):
    monkeypatch.setattr(compile_checks, "process_infidelity", lambda *a: pytest.fail("built a unitary"))
    n = compile_checks.CHECKED_UP_TO_QUBITS + 1
    assert compile_checks.unitary_check_note("X", "", "", n, 1e-8, "r") == (
        f"The output's unitary is not checked above {compile_checks.CHECKED_UP_TO_QUBITS} qubits.")


def test_single_precision_reading_of_a_near_pi_over_4_literal_is_reported_though_the_infidelity_hides_it():
    literal = _circuit(1, "rz(0.7853981643974483) q[0];\nh q[0];\n")
    expression = _circuit(1, "rz(pi/4+1e-9) q[0];\nh q[0];\n")
    change = compile_checks.single_precision_angle_change(literal)
    assert change == pytest.approx(2.0855e-8, rel=1e-3)
    assert compile_checks.single_precision_angle_change(expression) < 1e-16
    staq_read = _circuit(1, "rz(0.785398185253143) q[0];\nh q[0];\n")
    assert compile_checks.process_infidelity(literal, staq_read) < 1e-15


def test_single_precision_change_covers_constants_inside_gate_definitions_only():
    body = HEADER + "gate g(t) a { rz(t/2) a; rx(0.1) a; }\nqreg q[1];\ng(0.3) q[0];\n"
    expected = abs(float(np.float32(0.1)) - 0.1)
    assert compile_checks.single_precision_angle_change(body) == pytest.approx(
        max(expected, abs(float(np.float32(0.3)) - 0.3)))


def test_width_refusal_names_the_pipeline_the_limit_and_the_evidence():
    compile_checks.refuse_above_qubits(5, 5, "QMAP", "level 1 (exact mapping)", "why")
    with pytest.raises(CompileRefused, match=r"^QMAP level 1 \(exact mapping\) is offered up to 5 qubits and this circuit has 6: why$"):
        compile_checks.refuse_above_qubits(6, 5, "QMAP", "level 1 (exact mapping)", "why")


def _adapters():
    return sorted(COMPILERS.glob("*-compiler/main.py"))


def test_every_compile_adapter_records_a_check_of_its_output():
    assert len(_adapters()) == 8
    for main in _adapters():
        source = main.read_text()
        assert re.search(r"unitary_check_note\(|\"Checked: the output|\"Checked: the output, read", source), main


def test_bqskit_and_pyzx_check_their_outputs_in_the_pipeline_not_only_in_the_self_test():
    for name in ("bqskit", "pyzx"):
        tree = ast.parse((COMPILERS / f"{name}-compiler" / "main.py").read_text())
        callers = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                   and any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "unitary_check_note"
                           for c in ast.walk(node))}
        assert callers and "equivalent" not in callers, name


def test_every_image_that_checks_with_qiskit_installs_it():
    for main in _adapters():
        source = main.read_text()
        if "compile_checks" in source or "qiskit" in source:
            lock = (main.parent / "requirements.lock").read_text()
            assert re.search(r"^qiskit==2\.5\.2$", lock, re.M), main.parent.name
            assert re.search(r"^qiskit==2\.5\.2$", (main.parent / "requirements.txt").read_text(), re.M)


def test_pyzx_gets_qelib1_definitions_only_for_gates_qelib1_defines():
    from qrosetta_commons.qelib1 import qelib1_definitions
    tree = ast.parse((COMPILERS / "pyzx-compiler" / "main.py").read_text())
    lacks = next(node.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
                 and getattr(node.targets[0], "id", "") == "PYZX_PARSER_LACKS")
    names = {elt.value for elt in lacks.args[0].elts}
    assert names and names <= set(qelib1_definitions())


def test_qmap_exact_mapping_refuses_above_its_measured_width_before_mapping():
    tree = ast.parse((COMPILERS / "qmap-compiler" / "main.py").read_text())
    limit = next(node.value.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
                 and getattr(node.targets[0], "id", "") == "EXACT_MAX_QUBITS")
    run = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "run")
    lines = {getattr(c.func, "id", ""): c.lineno for c in ast.walk(run) if isinstance(c, ast.Call)}
    assert limit == 7
    assert lines["refuse_above_qubits"] < lines["map_"]
