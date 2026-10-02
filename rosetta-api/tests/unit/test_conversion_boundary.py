"""Circuit conversion stays outside the timed simulation window for the adapters that call a
backend's native routine directly: no execute_fn (or a module function it calls) converts
the circuit, goes through the SDK call that would convert it inside the window, or walks a
circuit (a loop over anything but range())."""
import ast

import pytest

from tests.unit.test_counts_histogram_boundary import _RUNNERS, _call_name, _execute_fns

_SPLIT_RUNNERS = ("pytket-qulacs-runner", "pytket-quest-runner", "qsim-cirq-runner",
                  "pytket-qiskit-runner", "cuquantum-runner")
_CONVERTING_CALLS = {"tk_to_qulacs", "tk_to_quest", "translate_cirq_to_qsim", "QSimCircuit",
                     "assemble_circuits", "prepare", "process_circuit", "process_circuits",
                     "get_result", "simulate", "run", "_compile", "_check_all_circuits",
                     "implicit_qubit_permutation", "_measured_bits", "_sampling_plan", "_records"}


def _walks_something_but_a_range(node) -> bool:
    iters = [n.iter for n in ast.walk(node) if isinstance(n, (ast.For, ast.comprehension))]
    return any(not (isinstance(i, ast.Call) and getattr(i.func, "id", None) == "range") for i in iters)


@pytest.mark.parametrize("runner", _SPLIT_RUNNERS)
def test_execute_fn_does_not_convert_the_circuit(runner):
    found = _execute_fns(_RUNNERS / runner / "main.py")
    assert found
    for job, nodes, _ in found:
        assert nodes is not None, f"{runner}: {job} execute_fn not found"
        calls = {_call_name(c) for node in nodes for c in ast.walk(node) if isinstance(c, ast.Call)}
        assert not calls & _CONVERTING_CALLS, f"{runner} {job}: {sorted(calls & _CONVERTING_CALLS)}"
        assert not any(_walks_something_but_a_range(node) for node in nodes), f"{runner} {job}: loop in execute_fn"
