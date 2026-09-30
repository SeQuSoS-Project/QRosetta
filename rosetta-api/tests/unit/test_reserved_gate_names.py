"""Gate definitions under names a runner's parser reserves are rejected, '^' parameters are
evaluated before the pytket round-trip, and the round-trip refuses to drop a user gate."""
import glob

import pytest
from fastapi import HTTPException

from services import circuit_resolver as cr
from services.reserved_gate_names import reserved_gate_reason
from services.validator import count_gate_statements, validate_request

HEADER = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
SLEEP = HEADER + "gate sleep a { x a; }\nqreg q[2];\ncreg c[2];\nh q[0];\nsleep q[1];\ncx q[0],q[1];\n"
ORDER2 = HEADER + "gate order2 a,b { cx a,b; }\nqreg q[2];\nh q[0];\norder2 q[0],q[1];\n"
YYPHASE = HEADER + "gate yyphase(t) a,b { }\nqreg q[2];\ncreg c[2];\nh q[0];\nyyphase(0.7) q[0],q[1];\nh q[1];\n"
FSIM = HEADER + "gate fsim(t,p) a,b { }\nqreg q[2];\nfsim(0.7,0.1) q[0],q[1];\n"
ISWAP = HEADER + "gate iswap(t) a,b { rx(t) a; }\nqreg q[2];\niswap(0.3) q[0],q[1];\n"


def _detail(qasm, **kw):
    with pytest.raises(HTTPException) as exc:
        validate_request(qasm, **kw)
    assert exc.value.status_code == 400
    return exc.value.detail


@pytest.mark.parametrize("mode", ["statevector", "measured"])
def test_sleep_is_rejected_with_the_parser_named(mode):
    assert _detail(SLEEP, mode=mode) == (
        "gate name 'sleep' is reserved by the pytket parser (treated as a barrier); rename the gate")


@pytest.mark.parametrize("qasm,name", [(ORDER2, "order2"), (YYPHASE, "yyphase"), (FSIM, "fsim"),
                                       (ISWAP, "iswap")])
def test_red_team_repros_are_rejected(qasm, name):
    detail = _detail(qasm, mode="measured", apply_preprocessing=False)
    assert detail.startswith(f"gate name '{name}' is reserved by the")
    assert detail.endswith("rename the gate")


@pytest.mark.parametrize("name", ["group20", "tk2", "h", "cu", "rcccx", "pH", "toffoli", "GPI2",
                                  "measure_all", "barrier2"])
def test_reserved_names(name):
    assert reserved_gate_reason(name)


@pytest.mark.parametrize("name", ["mine", "gate_Q", "mcx", "mcphase", "unitary", "order21",
                                  "sleepy", "oracle"])
def test_ordinary_names_are_allowed(name):
    assert reserved_gate_reason(name) is None


def test_opaque_definitions_are_checked():
    assert "'sleep'" in _detail(HEADER + "opaque sleep a;\nqreg q[1];\n")


def test_bundled_circuits_skip_the_name_check():
    grover = open("benchmarks/mqtbench/grover-noancilla_n6.qasm").read()
    validate_request(grover, mode="measured", check_reserved_names=False)


def test_bundled_circuits_use_no_pytket_reserved_name():
    from services.reserved_gate_names import PYTKET_BARRIER_NAMES, PYTKET_EXTRA_NAMES
    for path in glob.glob("benchmarks/*/*.qasm"):
        for stmt in cr.split_statements(open(path).read()):
            m = cr._GATE_NAME_RE.match(stmt)
            if m:
                assert m.group(1) not in PYTKET_BARRIER_NAMES | PYTKET_EXTRA_NAMES, path


def test_round_trip_refuses_a_gate_turned_into_a_barrier():
    with pytest.raises(cr.RoundTripIntegrityError, match="barrier"):
        cr.prepare_statevector_dispatch(SLEEP, apply_preprocessing=True)


def test_round_trip_refuses_a_gate_replaced_by_a_builtin():
    with pytest.raises(cr.RoundTripIntegrityError, match="yyphase"):
        cr.prepare_measured_dispatch(YYPHASE, apply_preprocessing=True)


def test_round_trip_keeps_ordinary_custom_gates():
    qasm = HEADER + ("gate mine(t) a,b { rx(t) a; cx a,b; }\ngate e a { }\nqreg q[2];\ncreg c[1];\n"
                     "mine(0.3) q[0],q[1];\ne q[0];\nif(c==1) mine(0.1) q[1],q[0];\n")
    out = cr.prepare_measured_dispatch(qasm, apply_preprocessing=True)
    assert "barrier" not in out["measured_native"]["qasm"]


def test_caret_parameters_are_evaluated_before_the_round_trip():
    qasm = HEADER + "qreg q[1];\nrx(-pi^2/4) q[0];\n"
    out = cr.prepare_statevector_dispatch(qasm, apply_preprocessing=True)
    assert any("pytket's parser does not accept '^'" in n for n in out["api_preprocessing_applied"])
    text, note = cr.evaluate_caret_parameters(qasm)
    assert "rx(-2.4674011002723395) q[0];" in text and note
    validate_request(qasm, mode="statevector")


def test_caret_is_left_alone_without_preprocessing():
    qasm = HEADER + "qreg q[1];\nrx(-pi^2/4) q[0];\n"
    assert cr.prepare_statevector_dispatch(qasm, apply_preprocessing=False)["qasm"] == qasm


def test_caret_in_a_gate_body_is_400_with_preprocessing():
    qasm = HEADER + "gate g(t) a { rx(t^2) a; }\nqreg q[1];\ng(0.5) q[0];\n"
    assert "uses '^' in its body" in _detail(qasm)
    validate_request(qasm, apply_preprocessing=False)


@pytest.mark.parametrize("expr", ["theta^2", "9^9^9", "1/0^1", "__import__('os')^1"])
def test_non_constant_or_unsafe_caret_is_400(expr):
    assert _detail(HEADER + f"qreg q[1];\nrx({expr}) q[0];\n").startswith("Invalid gate parameter:")


def test_constant_expression_evaluator():
    import math
    assert cr.evaluate_constant_expression("2^3^2") == 512.0
    assert cr.evaluate_constant_expression("-pi^2") == -math.pi ** 2
    assert cr.evaluate_constant_expression("sqrt(2)^2 + ln(exp(1))") == pytest.approx(3.0)


def test_gate_limit_counts_gate_statements_only(monkeypatch):
    from config import settings
    qasm = HEADER + "gate g a { x a; x a; }\nqreg q[1];\ncreg c[1];\n" + "h q[0];\n" * 5
    assert count_gate_statements(qasm) == 5
    monkeypatch.setattr(settings, "MAX_QASM_GATES", 5)
    validate_request(qasm)
    monkeypatch.setattr(settings, "MAX_QASM_GATES", 4)
    assert "5 gate statements exceeds the limit of 4" in _detail(qasm)
