"""Output permutations left by optimisation passes are written back as gates.

Qiskit's transpiler (ElidePermutations, levels 2-3) deletes swap gates and records the
permutation only in ``circuit.layout``; pytket passes with ``allow_swaps=True`` leave an
implicit wire permutation that the ``tk_to_*`` converters (other than with
``replace_implicit_swaps``) ignore. Either way a simulator that runs the gates returns the
state with its qubits permuted. Every runner that runs such a pass must restore it.
"""
import ast
import itertools
from pathlib import Path

import pytest

_RUNNERS = Path(__file__).resolve().parents[3] / "runners"

pytestmark = pytest.mark.skipif(
    not _RUNNERS.exists(), reason="runner sources not present in this checkout")

_TKET_PERMUTING = {"FullPeepholeOptimise", "PeepholeOptimise2Q", "CliffordSimp",
                   "KAKDecomposition", "CliffordResynthesis", "get_compiled_circuit"}
_QISKIT_TRANSPILE = {"transpile", "qiskit_transpile"}


def _calls(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            yield name, node


def _modules():
    return sorted(p for p in _RUNNERS.glob("*/main.py"))


def _optimising_transpile(node) -> bool:
    level = next((k.value for k in node.keywords if k.arg == "optimization_level"), None)
    return not (isinstance(level, ast.Constant) and level.value == 0)


@pytest.mark.parametrize("path", _modules(), ids=lambda p: p.parent.name)
def test_qiskit_transpile_output_permutation_is_restored(path):
    names = [(n, node) for n, node in _calls(ast.parse(path.read_text()))]
    optimising = [node for n, node in names if n in _QISKIT_TRANSPILE and _optimising_transpile(node)]
    if optimising:
        assert any(n == "restore_final_layout" for n, _ in names), (
            f"{path.parent.name}: transpiles at a non-zero optimization_level without "
            "restore_final_layout")


@pytest.mark.parametrize("path", _modules(), ids=lambda p: p.parent.name)
def test_tket_implicit_permutation_is_replaced_before_conversion(path):
    names = {n for n, _ in _calls(ast.parse(path.read_text()))}
    converts = any(n and n.startswith("tk_to_") for n in names)
    if converts and names & _TKET_PERMUTING:
        assert "replace_implicit_wire_swaps" in names, (
            f"{path.parent.name}: runs {sorted(names & _TKET_PERMUTING)} and converts with "
            "tk_to_* without replace_implicit_wire_swaps")


@pytest.fixture
def qk():
    pytest.importorskip("qiskit")
    import qiskit
    from qiskit.quantum_info import Statevector, state_fidelity
    from qrosetta_commons.qiskit_circuits import restore_final_layout, swaps_restoring
    return qiskit, Statevector, state_fidelity, restore_final_layout, swaps_restoring


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5])
def test_swaps_restoring_undoes_every_permutation(n, qk):
    swaps_restoring = qk[4]
    for final_positions in itertools.permutations(range(n)):
        holder = [None] * n
        for v, p in enumerate(final_positions):
            holder[p] = v
        swaps = swaps_restoring(final_positions)
        for a, b in swaps:
            holder[a], holder[b] = holder[b], holder[a]
        assert holder == list(range(n))
        assert len(swaps) <= n - 1


_REPRO = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[3];\nx q[0];\nswap q[0],q[2];\nh q[1];\n'


@pytest.mark.parametrize("level", [0, 1, 2, 3])
def test_restore_final_layout_gives_the_input_state(level, qk):
    qiskit, Statevector, state_fidelity, restore_final_layout, _ = qk
    source = qiskit.QuantumCircuit.from_qasm_str(_REPRO)
    restored, swaps = restore_final_layout(qiskit.transpile(source, optimization_level=level))
    assert state_fidelity(Statevector(source), Statevector(restored)) == pytest.approx(1.0)
    assert bool(swaps) == (level >= 2)
    if swaps:
        assert restored.layout is None


def test_restore_final_layout_leaves_an_unpermuted_circuit_alone(qk):
    qiskit, _, _, restore_final_layout, _ = qk
    source = qiskit.QuantumCircuit.from_qasm_str(
        'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n')
    compiled = qiskit.transpile(source, optimization_level=2)
    before = list(compiled.data)
    restored, swaps = restore_final_layout(compiled)
    assert swaps == []
    assert list(restored.data) == before
