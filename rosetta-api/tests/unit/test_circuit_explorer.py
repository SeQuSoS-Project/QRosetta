"""The Circuits view's pure modules (text_diff.js, qasm_text.js, circuit_panes.js), run in
Node: the diff is minimal and complete, normalisation removes only what its option names,
and panes carry the report's text and labels unchanged."""
import json
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from qrosetta_commons.helpers import GATE_METRICS_FROM_QASM

_NODE = shutil.which("node")
_HARNESS = Path(__file__).with_name("circuit_text_harness.mjs")

pytestmark = pytest.mark.skipif(_NODE is None, reason="node not available")


def _call(*calls):
    out = subprocess.run([_NODE, str(_HARNESS)], input=json.dumps({"calls": [
        {"fn": fn, "args": list(args)} for fn, *args in calls]}),
        capture_output=True, text=True, check=True, timeout=60)
    results = json.loads(out.stdout)["results"]
    for result in results:
        assert not (isinstance(result, dict) and "__error__" in result), result
    return results


def _lcs(a, b):
    table = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) - 1, -1, -1):
        for j in range(len(b) - 1, -1, -1):
            table[i][j] = table[i + 1][j + 1] + 1 if a[i] == b[j] else max(table[i + 1][j], table[i][j + 1])
    return table[0][0]


def test_diff_is_a_minimal_edit_script():
    rng = random.Random(7)
    cases = []
    for _ in range(300):
        alphabet = rng.randint(1, 4)
        cases.append(([str(rng.randrange(alphabet)) for _ in range(rng.randint(0, 14))],
                      [str(rng.randrange(alphabet)) for _ in range(rng.randint(0, 14))]))
    results = _call(*[("diffLines", a, b, 10**6) for a, b in cases])
    for (a, b), result in zip(cases, results):
        assert result["complete"]
        ops = result["ops"]
        equal = [op for op in ops if op["type"] == "equal"]
        assert len(equal) == _lcs(a, b)
        assert all(a[op["a"]] == b[op["b"]] for op in equal)
        assert [op["a"] for op in ops if op["a"] is not None] == list(range(len(a)))
        assert [op["b"] for op in ops if op["b"] is not None] == list(range(len(b)))
        assert (result["deleted"], result["inserted"]) == (len(a) - len(equal), len(b) - len(equal))


def test_diff_over_the_edit_budget_is_reported_incomplete():
    a = [f"a{i}" for i in range(300)]
    b = [f"b{i}" for i in range(300)]
    over, within = _call(("diffLines", a, b, 100), ("diffLines", a, b, 1000))
    assert over == {"complete": False}
    assert within["complete"] and within["deleted"] == 300 and within["inserted"] == 300


def test_hunks_keep_every_op_and_collapse_long_equal_runs():
    a = [f"l{i}" for i in range(40)]
    b = list(a)
    b[20] = "changed"
    (diff,) = _call(("diffLines", a, b))
    (hunks,) = _call(("diffHunks", diff["ops"], 3))
    expanded = [op for item in hunks for op in (item["ops"] if item["type"] == "skip" else [item])]
    assert expanded == diff["ops"]
    assert [item["count"] for item in hunks if item["type"] == "skip"] == [17, 16]


QISKIT_STYLE = ('OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nrz(0.5) q[0];\ncx q[0],q[1];\n'
                'gate g(t) a,b { rx(t) a; cx a,b; }\nmeasure q[0] -> c[0];\n')
CIRQ_STYLE = ('// Generated from Cirq\n\nOPENQASM 2.0;\ninclude "hqslib1.inc";\n\nqreg q[2];\n'
              'rz( 0.5 ) q[0];\ncx q[0], q[1]; /* entangle */\ngate g(t) a, b\n{\n  rx(t) a;\n'
              '  cx a, b;\n}\nmeasure q[0]->c[0];')


def test_normalisation_makes_layout_and_comment_differences_vanish():
    every = {"whitespace": True, "comments": True, "header": True}
    a, b, raw_a, raw_b = _call(("comparableLines", QISKIT_STYLE, every),
                               ("comparableLines", CIRQ_STYLE, every),
                               ("comparableLines", QISKIT_STYLE, {}),
                               ("comparableLines", CIRQ_STYLE, {}))
    assert a == b
    assert a[0] == "qreg q[2];" and "cx q[0], q[1];" in a
    assert raw_a == QISKIT_STYLE.split("\n")[:-1]
    assert raw_b == CIRQ_STYLE.split("\n")


def test_each_option_removes_only_what_it_names():
    text = 'OPENQASM 2.0;\ninclude "a//b.inc"; // note\nh q[0];\n'
    comments, header, whitespace = _call(
        ("comparableLines", text, {"comments": True}),
        ("comparableLines", text, {"header": True}),
        ("comparableLines", "h  q[0] ; x q[1];", {"whitespace": True}))
    assert comments == ['OPENQASM 2.0;', 'include "a//b.inc";', 'h q[0];']
    assert header == ['// note', 'h q[0];']
    assert whitespace == ["h q[0];", "x q[1];"]


def test_a_gate_parameter_change_survives_normalisation():
    every = {"whitespace": True, "comments": True, "header": True}
    a, b = _call(("comparableLines", "rz(0.5) q[0];", every), ("comparableLines", "rz(0.25) q[0];", every))
    assert a != b


def test_trailing_line_break_is_not_a_line_but_is_reported():
    lines, ends, lines_no_break, ends_no_break = _call(
        ("splitLines", "h q;\n"), ("endsWithNewline", "h q;\n"),
        ("splitLines", "h q;"), ("endsWithNewline", "h q;"))
    assert lines == lines_no_break == ["h q;"]
    assert ends is True and ends_no_break is False


def test_text_counted_basis_matches_the_runner_constant():
    (constant,) = _call(("GATE_METRICS_FROM_QASM",))
    assert constant == GATE_METRICS_FROM_QASM


_REPORT = {
    "input_qasm": "OPENQASM 2.0;\nqreg a[1];\nqreg b[1];\nh a[0];\n",
    "dispatched_circuits": [
        {"group": "statevector", "qasm": "OPENQASM 2.0;\nqreg q[2];\nh q[0];\n",
         "api_preprocessing_applied": ["API: merged registers"],
         "runners": ["qiskit", "pennylane-default", "qulacs~opt1~run2"]},
    ],
    "raw_results": [
        {"simulator": "qiskit", "transpiled_qasm": "h q[0];", "dispatch_group": "statevector",
         "preprocessing_applied": ["API: merged registers", "rebase to CX/U3"],
         "gate_count": 1, "circuit_depth": 1, "gate_metrics_basis": GATE_METRICS_FROM_QASM,
         "sdk_versions": {"qiskit": "1.4.4"}, "dispatch_status": "ok"},
        {"simulator": "pennylane-default", "transpiled_qasm": "u3(...) q[0];", "dispatch_group": "statevector",
         "gate_count": 1, "circuit_depth": 1, "gate_metrics_basis": "operations of the executed tape",
         "dispatch_status": "ok"},
        {"simulator": "qulacs~opt1~run2", "dispatch_group": "statevector", "dispatch_status": "error",
         "error": "boom"},
    ],
}


def test_panes_carry_the_report_text_in_order():
    (panes,) = _call(("circuitPanes", _REPORT))
    assert [p["id"] for p in panes] == ["input", "dispatched:statevector", "executed:qiskit",
                                        "executed:pennylane-default", "executed:qulacs~opt1~run2"]
    assert panes[0]["text"] == _REPORT["input_qasm"]
    assert panes[1]["text"] == _REPORT["dispatched_circuits"][0]["qasm"]
    qiskit, pennylane, qulacs = panes[2:]
    assert qiskit["text"] == "h q[0];"
    assert qiskit["apiNotes"] == ["API: merged registers"] and qiskit["runnerNotes"] == ["rebase to CX/U3"]
    assert qiskit["metrics"] == {"fromText": True, "basis": GATE_METRICS_FROM_QASM}
    assert pennylane["metrics"]["fromText"] is False
    assert qulacs["text"] is None and qulacs["status"] == "error" and qulacs["simId"] == "qulacs"


def test_executed_pane_diffs_against_its_dispatch_group_by_default():
    (panes,) = _call(("circuitPanes", _REPORT))
    source_of_executed, source_of_dispatched, source_of_input = _call(
        ("sourcePaneId", panes[2], panes), ("sourcePaneId", panes[1], panes), ("sourcePaneId", panes[0], panes))
    assert (source_of_executed, source_of_dispatched, source_of_input) == (
        "dispatched:statevector", "input", None)


def test_malformed_report_fields_are_skipped():
    (panes,) = _call(("circuitPanes", {"input_qasm": 5, "dispatched_circuits": [None, {"group": 1}],
                                       "raw_results": [None, {"simulator": "x", "transpiled_qasm": 3}]}))
    assert [p["id"] for p in panes] == ["executed:x"]
    assert panes[0]["text"] is None


def test_compile_input_and_compiled_panes_follow_the_executed_ones():
    report = {**_REPORT,
              "compile_input": {"qasm": "OPENQASM 2.0;\nqreg q[2];\nh q[0];\n", "api_preprocessing_applied": ["API: x"]},
              "compiled_circuits": [
                  {"compiler": "pyzx~opt1~run1", "compiler_id": "pyzx", "compiler_name": "PyZX",
                   "optimization_level": 1, "transpiled_qasm": "h q[0];", "passes_applied": ["full_reduce"],
                   "gate_count": 1, "circuit_depth": 1, "gate_metrics_basis": GATE_METRICS_FROM_QASM,
                   "dispatch_status": "ok"},
                  {"compiler": "qmap", "compiler_id": "qmap", "optimization_level": 0,
                   "dispatch_status": "skipped"}]}
    (panes,) = _call(("circuitPanes", report))
    assert [p["id"] for p in panes][-3:] == ["compile-input", "compiled:pyzx~opt1~run1", "compiled:qmap"]
    pyzx, qmap = panes[-2:]
    assert pyzx["compilerName"] == "PyZX" and pyzx["level"] == 1 and pyzx["passes"] == ["full_reduce"]
    assert pyzx["metrics"]["fromText"] is True
    assert qmap["text"] is None and qmap["status"] == "skipped" and qmap["compilerName"] is None
    (source,) = _call(("sourcePaneId", pyzx, panes))
    assert source == "compile-input"


def test_comment_removal_leaves_no_trailing_whitespace():
    a, b = _call(("comparableLines", "h q[0]; // c\n", {"comments": True}),
                 ("comparableLines", "h q[0];\n", {"comments": True}))
    assert a == b == ["h q[0];"]


def test_whitespace_mode_keeps_comments_on_their_own_lines():
    text = "qreg q[3];\n// bell pair then {\nh q[0];\ncx q[0],q[1]; // entangle\ngate g a { h a; } // x\n"
    (lines,) = _call(("comparableLines", text, {"whitespace": True}))
    assert lines == ["qreg q[3];", "// bell pair then {", "h q[0];", "cx q[0], q[1];", "// entangle",
                     "gate g a {", "h a;", "}", "// x"]
    edited = text.replace("bell pair then", "bell pair, then")
    (other,) = _call(("comparableLines", edited, {"whitespace": True}))
    assert [x for x in lines if x not in other] == ["// bell pair then {"]


def test_header_option_removes_a_one_line_header_but_not_comments():
    one_line, commented = _call(
        ("comparableLines", 'OPENQASM 2.0; include "qelib1.inc";\nh q[0];', {"header": True}),
        ("comparableLines", '// include "x.inc";\nh q;', {"header": True}))
    assert one_line == ["h q[0];"]
    assert commented == ['// include "x.inc";', "h q;"]


def test_line_break_only_differences_are_detected():
    crlf, same = _call(("differOnlyInLineBreaks", "a\r\nb", "a\nb"), ("differOnlyInLineBreaks", "a\nb", "a\nb"))
    assert crlf is True and same is False
