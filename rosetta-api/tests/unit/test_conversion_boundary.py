"""Circuit conversion stays outside the timed simulation window for the adapters that call a
backend's native routine directly: no execute_fn (or a module function it calls) converts
the circuit or goes through the SDK call that would convert it inside the window."""
import ast

import pytest

from tests.unit.test_counts_histogram_boundary import _RUNNERS, _call_name, _execute_fns

_SPLIT_RUNNERS = ("pytket-qulacs-runner", "pytket-quest-runner", "qsim-cirq-runner",
                  "pytket-qiskit-runner", "cuquantum-runner")
_CONVERTING_CALLS = {"tk_to_qulacs", "tk_to_quest", "translate_cirq_to_qsim", "QSimCircuit",
                     "assemble_circuits", "prepare", "process_circuit", "process_circuits",
                     "get_result", "simulate", "run", "_compile", "_check_all_circuits"}


@pytest.mark.parametrize("runner", _SPLIT_RUNNERS)
def test_execute_fn_does_not_convert_the_circuit(runner):
    found = _execute_fns(_RUNNERS / runner / "main.py")
    assert found
    for job, nodes, _ in found:
        assert nodes is not None, f"{runner}: {job} execute_fn not found"
        calls = {_call_name(c) for node in nodes for c in ast.walk(node) if isinstance(c, ast.Call)}
        assert not calls & _CONVERTING_CALLS, f"{runner} {job}: {sorted(calls & _CONVERTING_CALLS)}"
