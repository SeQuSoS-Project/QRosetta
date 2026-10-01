"""Shared scaffolding of compile-only services: result shape, failures as errors, the
self-test, and the /compile endpoint running once in a spawned process without the timing
instrument."""
import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from qrosetta_commons import compile_service
from qrosetta_commons.helpers import GATE_METRICS_FROM_QASM
from tests.unit import _compile_fixture as fx

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'


def test_success_carries_text_passes_and_text_counted_metrics():
    result = fx.process_compile({"circuit_data": QASM, "optimization_level": 0})
    assert result == {"compiler": "fixture", "optimization_level": 0, "transpiled_qasm": QASM,
                      "passes_applied": ["identity"], "gate_count": 2, "circuit_depth": 2,
                      "gate_counts": {"cx": 1, "h": 1}, "multi_qubit_gate_count": 1,
                      "gate_metrics_basis": GATE_METRICS_FROM_QASM}


def test_gate_counts_by_name_count_statements_and_multi_qubit_ones():
    from qrosetta_commons.helpers import count_qasm_gates_by_name
    text = ('OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[3];\ncreg c[3];\ngate g a,b { cx a,b; }\n'
            'ccx q[0],q[1],q[2];\nrz(0.1) q[0];\nbarrier q;\ng q[0],q[1];\ncx q[1],q[1];\n'
            'measure q[0] -> c[0];\n')
    assert count_qasm_gates_by_name(text) == ({"ccx": 1, "cx": 1, "g": 1, "rz": 1}, 2)


def test_unknown_level_and_oversized_circuits_are_errors():
    unknown = fx.process_compile({"circuit_data": QASM, "optimization_level": 7})
    assert unknown["error"].startswith("ValueError: fixture has no optimization level 7")
    wide = 'OPENQASM 2.0;\nqreg q[%d];\n' % (compile_service.COMPILE_MAX_QUBITS + 1)
    assert "error" in fx.process_compile({"circuit_data": wide, "optimization_level": 0})


def test_self_test_counts_each_failing_probe_and_level():
    out = io.StringIO()
    failures = compile_service.run_compiler_self_test(fx.process_compile, [0, 1], fx.same_text, out)
    assert failures == len(compile_service.SELF_TEST_PROBES)
    lines = out.getvalue().splitlines()
    assert sum(line.startswith("PASS") and line.endswith("level 0") for line in lines) == failures
    assert all(line.endswith("level 1: output unitary differs from the input")
               for line in lines if line.startswith("FAIL"))


def test_cli_self_test_exits_non_zero_on_failure(monkeypatch):
    monkeypatch.setattr("sys.argv", ["main.py", "--self-test"])
    with pytest.raises(SystemExit) as exit_info:
        compile_service.run_compiler_cli_main(None, fx.process_compile, "fx", levels=[1], equivalent=fx.same_text)
    assert exit_info.value.code == 1


def test_compile_endpoint_runs_the_processor_once_in_a_child(monkeypatch):
    calls = []
    real_run_isolated = compile_service.ExecutionSlots.run

    async def spy(self, func, payload, measured=True):
        calls.append(measured)
        return await real_run_isolated(self, func, payload, measured=measured)

    monkeypatch.setattr(compile_service.ExecutionSlots, "run", spy)
    app = FastAPI()
    compile_service.register_compiler_endpoint(app, fx.process_compile)
    result = TestClient(app).post("/compile", json={"circuit_data": QASM, "optimization_level": 0,
                                                    "hard_timeout_seconds": 60}).json()
    assert calls == [False]
    assert result["transpiled_qasm"] == QASM and result["queue_wait_sec"] >= 0
    assert "timing_samples" not in result and "compilation_time_sec" not in result
