"""Counts construction stays outside the timed simulation window.

Drawing shots is simulation work; turning a backend's raw result into a counts dict is
bookkeeping and belongs in postprocess_fn. These tests check that the split preserves the
sampled counts exactly and that no runner's execute_fn builds counts.

The execute_fn of each ``run_measured_job`` / ``run_statevector_job`` call is found in the
syntax tree (a lambda, or a function of any name defined in the runner module), and every
function it calls that is defined in the same module is inspected with it.
"""
import ast
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from qrosetta_commons.helpers import _counts_from_samples, _draw_statevector_samples

_RUNNERS = Path(__file__).resolve().parents[3] / "runners"

pytestmark = pytest.mark.skipif(
    not _RUNNERS.exists(), reason="runner sources not present in this checkout")

_JOB_CALLS = ("run_measured_job", "run_statevector_job")


def _random_statevector(n_qubits, seed=7):
    rng = np.random.default_rng(seed)
    sv = rng.normal(size=2 ** n_qubits) + 1j * rng.normal(size=2 ** n_qubits)
    return sv / np.linalg.norm(sv)


@pytest.mark.parametrize("n_qubits", [2, 3, 5, 8])
@pytest.mark.parametrize("seed", [0, 42, 12345])
def test_split_draw_and_histogram_match_the_combined_form(n_qubits, seed):
    """Splitting draw and histogram must not perturb the RNG stream or the counts."""
    sv = _random_statevector(n_qubits)
    n_shots = 2048

    rng = np.random.default_rng(seed)
    expected = {
        format(k, f"0{n_qubits}b"): v
        for k, v in Counter(
            rng.choice(len(sv), size=n_shots, p=np.abs(sv) ** 2)).items()
    }

    actual = _counts_from_samples(
        _draw_statevector_samples(sv, n_shots, seed), n_qubits)

    assert actual == expected


def test_draw_is_reproducible_under_a_seed():
    sv = _random_statevector(4)
    a = _draw_statevector_samples(sv, 512, 99)
    b = _draw_statevector_samples(sv, 512, 99)
    assert np.array_equal(a, b)


def _runner_sources():
    return sorted(_RUNNERS.glob("*/main.py"))


def _call_name(call: ast.Call):
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _definitions(tree):
    """``{name: [FunctionDef, ...]}`` for every function defined anywhere in the module."""
    defs = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.setdefault(node.name, []).append(node)
    return defs


def _enclosing_function(tree, target):
    """The innermost function definition containing ``target``, or None."""
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    node = parents.get(target)
    while node is not None and not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        node = parents.get(node)
    return node


def _resolve(expr, scope, defs):
    """The function node an execute_fn expression names, preferring a definition nested in
    the function that makes the job call."""
    if isinstance(expr, ast.Lambda):
        return expr
    if not isinstance(expr, ast.Name):
        return None
    if scope is not None:
        for node in ast.walk(scope):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == expr.id:
                return node
    candidates = defs.get(expr.id, [])
    return candidates[0] if candidates else None


def _with_callees(func, defs):
    """``func`` plus every module-defined function it calls, transitively."""
    seen, stack, out = set(), [func], []
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        out.append(node)
        for call in ast.walk(node):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                stack.extend(defs.get(call.func.id, []))
    return out


def _execute_fns(path):
    """``[(job call name, execute_fn nodes incl. callees or None, has postprocess_fn)]``."""
    tree = ast.parse(path.read_text())
    defs = _definitions(tree)
    found = []
    for call in ast.walk(tree):
        if not (isinstance(call, ast.Call) and _call_name(call) in _JOB_CALLS):
            continue
        keywords = {kw.arg: kw.value for kw in call.keywords}
        scope = _enclosing_function(tree, call)
        func = _resolve(keywords.get("execute_fn"), scope, defs)
        nodes = _with_callees(func, defs) if func is not None else None
        found.append((_call_name(call), nodes, "postprocess_fn" in keywords))
    return found


_DRAW_CALLS = {"_draw_statevector_samples", "choice", "multinomial"}

_COUNTS_CALLS = {
    "unique", "bincount", "Counter", "value_counts", "histogram", "defaultdict",
    "_counts_from_samples", "get_counts", "readout_counts", "counts_from_qubit_samples",
    "counts_from_qubit_counts", "counts_from_register_keys", "counts_from_pytket_result",
    "counts_from_named",
}

_LOOPS = (ast.For, ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _calls(nodes):
    return [n for node in nodes for n in ast.walk(node) if isinstance(n, ast.Call)]


def _histogram_loops(nodes):
    """Loop constructs that tally into a dict or format a key per item."""
    found = []
    for node in nodes:
        for loop in ast.walk(node):
            if not isinstance(loop, _LOOPS):
                continue
            for inner in ast.walk(loop):
                if isinstance(inner, ast.AugAssign) and isinstance(inner.target, ast.Subscript):
                    found.append("d[k] += ... in a loop")
                elif (isinstance(inner, ast.Assign)
                      and any(isinstance(t, ast.Subscript) for t in inner.targets)
                      and any(isinstance(c, ast.Call) and _call_name(c) == "get"
                              for c in ast.walk(inner.value))):
                    found.append("d[k] = d.get(k, 0) + ... in a loop")
                elif isinstance(inner, ast.Call) and _call_name(inner) in (
                        "setdefault", "count", "format", "bin"):
                    found.append(f"{_call_name(inner)}() in a loop")
    return found


def _counts_work(nodes):
    names = {_call_name(c) for c in _calls(nodes)}
    return sorted(names & _COUNTS_CALLS) + sorted(set(_histogram_loops(nodes)))


def _draws(nodes):
    return bool({_call_name(c) for c in _calls(nodes)} & _DRAW_CALLS)


def test_no_runner_builds_counts_inside_execute_fn():
    """execute_fn returns the backend's raw result; postprocess_fn builds the counts dict."""
    offenders = []
    for path in _runner_sources():
        for job, nodes, _post in _execute_fns(path):
            if nodes is None:
                continue
            found = _counts_work(nodes)
            if found:
                offenders.append(f"{path.parent.name} {job} ({', '.join(found)})")
    assert not offenders, (
        "these runners build counts inside the timed simulation window: "
        + "; ".join(offenders))


def test_statevector_samplers_pass_a_postprocess_fn():
    """A measured execute_fn that draws its own shots hands them to postprocess_fn."""
    offenders = [
        path.parent.name for path in _runner_sources()
        for job, nodes, has_post in _execute_fns(path)
        if job == "run_measured_job" and nodes is not None and _draws(nodes) and not has_post]
    assert not offenders, f"sampling runners without postprocess_fn: {offenders}"


def test_every_job_call_has_a_resolvable_execute_fn():
    """Guard the guard: every runner makes both job calls and each execute_fn is found."""
    problems = []
    for path in _runner_sources():
        calls = _execute_fns(path)
        kinds = {job for job, _nodes, _post in calls}
        if kinds != set(_JOB_CALLS):
            problems.append(f"{path.parent.name}: job calls {sorted(kinds)}")
        problems += [f"{path.parent.name}: {job} execute_fn not resolved"
                     for job, nodes, _post in calls if nodes is None]
    assert _runner_sources() and not problems, "\n".join(problems)


def test_the_boundary_check_actually_inspects_the_sampling_runners():
    """Guard the guard: if resolution stops working, the checks above pass vacuously."""
    sampling = [
        path.parent.name for path in _runner_sources()
        for job, nodes, _post in _execute_fns(path)
        if job == "run_measured_job" and nodes is not None and _draws(nodes)]
    # quest, projectq, both pennylane runners, torchquantum and pyquil all sample.
    assert len(sampling) >= 6, f"expected the statevector samplers, matched only {sampling}"


_PLANTED = '''
from qrosetta_commons.helpers import run_measured_job, run_statevector_job
import numpy as np

def _tally(samples):
    out = {}
    for s in samples:
        out[s] = out.get(s, 0) + 1
    return out

def process_run(payload):
    return run_statevector_job(execute_fn=lambda compiled, _p: compiled.circuit)

def process_run_measured(payload):
    def sample_everything(compiled, _payload):
        idx = np.random.default_rng().choice(4, size=10)
        keys, freq = np.unique(idx, return_counts=True)
        return _tally(idx)
    return run_measured_job(execute_fn=sample_everything)
'''


def test_the_check_catches_a_planted_histogram(tmp_path):
    """A draw via default_rng().choice plus np.unique and a dict tally in a helper is found,
    whatever the execute function is called."""
    path = tmp_path / "planted-runner" / "main.py"
    path.parent.mkdir()
    path.write_text(_PLANTED)
    by_job = {job: nodes for job, nodes, _post in _execute_fns(path)}
    assert set(by_job) == set(_JOB_CALLS)
    found = _counts_work(by_job["run_measured_job"])
    assert "unique" in found and "d[k] = d.get(k, 0) + ... in a loop" in found
    assert _draws(by_job["run_measured_job"])
    assert not _counts_work(by_job["run_statevector_job"])
