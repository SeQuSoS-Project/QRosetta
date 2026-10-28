"""V6 fuzzing findings: each input that broke a harness (a 500, a silently changed circuit, a
request that held the API for seconds) is a 400 or an unchanged result within a second."""
import sys
import time
from pathlib import Path

import pytest
from fastapi import HTTPException

pytest.importorskip("pytket")

from services.validator import validate_request, validate_submission  # noqa: E402

CORPUS = Path(__file__).resolve().parents[1] / "fuzz_corpus" / "validator"
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "fuzz"))
HEAD = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
MB = 1_000_000


def _refusal(qasm, **kwargs):
    with pytest.raises(HTTPException) as exc:
        validate_request(qasm, **kwargs)
    assert exc.value.status_code == 400
    return exc.value.detail


def _timed_refusal_or_pass(qasm, limit=1.0, **kwargs):
    start = time.perf_counter()
    try:
        validate_submission(qasm, **kwargs)
    except HTTPException as exc:
        assert exc.status_code in (400, 413)
    elapsed = time.perf_counter() - start
    assert elapsed < limit, f"{elapsed:.2f} s"


@pytest.mark.parametrize("mode", ["statevector", "measured", "compile"])
def test_v6_01_statement_without_a_name_is_a_400(mode):
    qasm = (CORPUS / "V6-01-statement-without-a-name.qasm").read_text()
    assert _refusal(qasm, mode=mode, apply_preprocessing=False) == (
        "Line 1: ',q[1]' is not a statement. Each statement starts with a gate name, 'measure', "
        "'reset', 'barrier' or 'if', and ends with ';'.")


def test_v6_01_statement_without_a_name_inside_a_gate_body_is_a_400():
    detail = _refusal(HEAD + "gate g a { , x a; }\nqreg q[1];\ng q[0];\n")
    assert detail.startswith("Line 3: ', x a' (inside the definition of 'g') is not a statement.")


def test_v6_01_stray_braces_are_a_400():
    assert "is not a statement" in _refusal(HEAD + "qreg q[1];\n{ x q[0]; }\n")


def test_v6_02_unclosed_block_marker_in_a_line_comment_is_a_400():
    qasm = (CORPUS / "V6-02-unclosed-block-marker-in-line-comment.qasm").read_text()
    for pre in (True, False):
        assert _refusal(qasm, apply_preprocessing=pre).startswith(
            "Line 4: the '//' comment holds '/*' with no '*/' after it on the same line.")


@pytest.mark.parametrize("comment", ["// see /* here */", "// a /* b */ c /* d */",
                                     "// */ only", "// /**/"])
def test_v6_02_block_markers_closed_in_the_same_line_comment_are_text(comment):
    validate_request(HEAD + f"qreg q[1];\n{comment}\nh q[0];\n")


@pytest.mark.parametrize("comment", ["// /*", "// /* a */ /*", "// /*/", "// x */ /* y"])
def test_v6_02_block_markers_left_open_in_a_line_comment_are_refused(comment):
    assert "holds '/*' with no '*/'" in _refusal(HEAD + f"qreg q[1];\n{comment}\nh q[0];\n")


def test_v6_02_bundled_circuits_keep_their_comments():
    validate_request(HEAD + "qreg q[1];\n// see /* here\nh q[0];\n", check_reserved_names=False)


@pytest.mark.parametrize("filler", ["\n", " \n", "\n\t", "bit" + " " * 50 + "\n", "/*",
                                    "// /*\n"])
@pytest.mark.parametrize("mode", ["statevector", "measured"])
def test_v6_03_a_megabyte_of_filler_is_answered_within_a_second(filler, mode):
    body = (filler * (MB // len(filler)))[:MB - 200]
    for qasm in (body, HEAD + body, HEAD + "qreg q[1];\n" + body + "h q[0];\n"):
        _timed_refusal_or_pass(qasm, mode=mode, statevector=mode == "statevector")


@pytest.mark.parametrize("qasm,expected", [
    ((CORPUS / "V6-04-unbalanced-brace.qasm").read_text(), "Syntax error on line 1: '{' inside"),
    (HEAD + "qreg q[1];\ngate g a { x a;\nh q[0];\n", "Syntax error on line 4: the gate body opened"),
    (HEAD + "qreg q[1];\nh q[0];\n}\n", "Syntax error on line 5: '}' closes no gate body."),
    (HEAD + "gate g a { qreg r[3]; }\n", "Line 3: 'qreg' declares a register only as a statement"),
])
def test_v6_04_braces_and_nested_qreg_are_a_400(qasm, expected):
    for mode in ("statevector", "measured", "compile"):
        assert _refusal(qasm, mode=mode).startswith(expected)


@pytest.mark.parametrize("decl", ["creg c[1025];", "creg c[100000000000];",
                                  "creg c[" + "9" * 40 + "];", "creg c[1000];\ncreg d[25];"])
def test_v6_05_more_than_max_classical_bits_is_a_400_at_once(decl):
    start = time.perf_counter()
    detail = _refusal(HEAD + f"qreg q[1];\n{decl}\nmeasure q[0] -> c[0];\n", mode="measured")
    assert detail.startswith("Circuit declares more than 1024 classical bits")
    assert time.perf_counter() - start < 0.5


def test_v6_05_classical_bits_up_to_the_limit_pass():
    validate_request(HEAD + "qreg q[1];\ncreg c[1000];\ncreg d[24];\nmeasure q[0] -> d[3];\n",
                     mode="measured")


def test_v6_05_the_limit_is_published():
    from fastapi.testclient import TestClient

    from config import settings
    from main import app
    limits = TestClient(app).get("/config").json()["limits"]
    assert limits["max_classical_bits"] == settings.MAX_CLASSICAL_BITS == 1024


@pytest.mark.parametrize("qasm,expected", [
    (HEAD + "gate g a {\n" + "x a;\n" * 10_001 + "}\nqreg q[1];\n",
     "Circuit too complex: 10001 gate statements"),
    (HEAD + "".join(f"gate g{i} a {{ }}\n" for i in range(10_001)) + "qreg q[1];\n",
     "Circuit too complex: 10001 gate statements"),
    (HEAD + "qreg q[1];\ncreg c[0];\n", "Line 4: register 'c' has size 0"),
    (HEAD + "qreg q[0];\nqreg r[1];\n", "Line 3: register 'q' has size 0"),
    (HEAD + "qreg q[1];\nrz(" + "+".join(["1"] * 600) + ") q[0];\n",
     "Line 4: a parameter of 'rz' is 1199 characters long"),
])
def test_v6_06_long_inputs_that_took_seconds_are_a_400(qasm, expected):
    assert _refusal(qasm).startswith(expected)


def test_v6_06_every_large_input_shape_takes_under_a_second():
    import fuzz_targets
    for name, qasm in fuzz_targets.large_inputs().items():
        start = time.perf_counter()
        try:
            validate_submission(qasm, "statevector", statevector=True)
        except HTTPException as exc:
            assert exc.status_code in (400, 413), name
        assert time.perf_counter() - start < 1.5, name


def test_v6_07_a_run_name_of_whitespace_is_planned_at_once():
    import random
    import re

    from services import plan_text
    start = time.perf_counter()
    assert plan_text.bare_circuit_name(" " * 1_000_000 + "x") == "x"
    assert time.perf_counter() - start < 0.5
    space = "".join(sorted(plan_text._WS_SET))
    regex = re.compile(rf"(?:[{space}]*\([0-9]+q\))+[{space}]*\Z")
    rng = random.Random(7)
    alphabet = ["(", ")", "q", "1", "23", " ", "\t", "\u2003", "\u2028", "x", "Q", "(4q)", " (12q)"]
    for _ in range(5000):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randrange(0, 12)))
        assert plan_text._without_qubit_suffix(text) == regex.sub("", text, count=1), repr(text)


@pytest.mark.parametrize("decl,kind", [
    ("qreg gate[2];", "quantum register"), ("creg measure[2];", "classical register"),
    ("qreg pi[1];", "quantum register"), ("qreg sin[1];", "quantum register"),
    ("gate barrier a { x a; }", "gate"), ("opaque if a;", "opaque gate"),
])
def test_v6_08_keywords_cannot_name_registers_or_gates(decl, kind):
    detail = _refusal(HEAD + "qreg q[1];\n" + decl + "\n")
    assert detail.startswith(f"Line 4: '{decl.split()[1].split('[')[0]}' is an OpenQASM 2.0 keyword "
                             f"and cannot name a {kind}")


def test_v6_08_a_register_named_gate_is_refused_before_the_quadratic_pass():
    start = time.perf_counter()
    _refusal(HEAD + "qreg gate[2];\nbarrier gate" + " , gate" * 140_000 + ";\n", mode="measured")
    assert time.perf_counter() - start < 1.0


def _bundled_and_templates():
    from services import circuit_library
    root = Path(__file__).resolve().parents[2]
    texts = [p.read_text() for p in sorted((root / "benchmarks").rglob("*.qasm"))]
    texts += [p.read_text() for p in sorted((root / "circuits").rglob("*.qasm"))]
    texts += [circuit_library.generate_circuit(a, n) for a in circuit_library.PRESET_ORDER
              for n in (2, 5)]
    return texts


def test_v6_09_tket_note_of_many_calls_of_a_gate_ending_in_gate_is_fast():
    from qrosetta_commons.qasm_expressions import tket_parameter_note
    qasm = (HEAD + "gate mygate(t) a { rz(t) a; }\nqreg q[1];\n"
            + ("mygate(1e-12)" + " " * 80 + "q[0];\n") * 9_900)
    validate_request(qasm)
    start = time.perf_counter()
    assert "mygate(1e-12)" in tket_parameter_note(qasm, "tket")
    assert time.perf_counter() - start < 1.0


def test_v6_09_tket_note_is_unchanged_on_the_bundled_circuits(monkeypatch):
    import re

    from qrosetta_commons import qasm_expressions as qe
    texts = _bundled_and_templates()
    new = [qe.tket_rounded_parameters(t) for t in texts]
    monkeypatch.setattr(qe, "_GATE_DEF_RE", re.compile(
        r"gate\s+([A-Za-z_]\w*)\s*(?:\(([^)]*)\))?[^{]*\{([^}]*)\}"))
    assert [qe.tket_rounded_parameters(t) for t in texts] == new
    assert len(texts) > 330


def _cnx_texts():
    import random
    rng = random.Random(3)
    pieces = ["c4x q[0],q[1],q[2],q[3],q[4];", "c4x q[0],q[1];", "c4x q[0], q[1], q[2];",
              "if(c==1) c4x q[0],q[1],q[2],q[3];", "  c4x  q[1],q[0],q[2];", "h q[0];",
              "\n", "\n\n   ", "x q[1];", "if (c==2)\n  c4x q[0],q[1];", "\t"]
    texts = [HEAD + "qreg q[5];\ncreg c[2];\n" + "".join(rng.choice(pieces) for _ in range(30))
             for _ in range(300)]
    return texts + _bundled_and_templates()


def test_v6_12_cnx_renaming_is_unchanged_and_linear(monkeypatch):
    import re

    from services import circuit_resolver as cr
    texts = _cnx_texts()
    new = [cr._name_cnx_by_size(t) for t in texts]
    monkeypatch.setattr(cr, "_PYTKET_CNX_RE", re.compile(
        r"^(\s*(?:if\s*\([^)]*\)\s*)?)c4x(\s+)([^;]*);", re.MULTILINE))
    assert [cr._name_cnx_by_size(t) for t in texts] == new
    monkeypatch.undo()
    start = time.perf_counter()
    cr._name_cnx_by_size("\n" * MB + "c4x q[0],q[1];")
    assert time.perf_counter() - start < 0.5
