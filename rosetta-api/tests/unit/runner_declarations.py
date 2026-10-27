"""Precision and qubit ordering each runner declares in its own source: the ``qubit_ordering``
and ``precision`` arguments of ``run_statevector_job`` / ``run_measured_job``, and a
``CompileResult(precision=...)`` in the same endpoint function, read statically. A value
computed at run time reads as None."""
import ast
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_JOBS = {"run_statevector_job": "statevector", "run_measured_job": "measured"}


def _constants(tree: ast.Module) -> dict:
    out = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
            out[node.targets[0].id] = node.value.value
    return out


def _value(node, constants: dict):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    return None


def _call_name(call: ast.Call) -> str:
    func = call.func
    return func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""


def _keyword(call: ast.Call, name: str):
    return next((kw.value for kw in call.keywords if kw.arg == name), None)


def declared(infra_name: str) -> dict:
    """``{"statevector": {"precision", "qubit_ordering"}, "measured": {...}}`` for the runner
    in ``runners/<infra_name>/main.py``; an endpoint whose job call is not found is absent."""
    tree = ast.parse((_REPO / "runners" / infra_name / "main.py").read_text())
    constants = _constants(tree)
    out = {}
    for func in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        calls = [n for n in ast.walk(func) if isinstance(n, ast.Call)]
        jobs = [c for c in calls if _call_name(c) in _JOBS]
        if len(jobs) != 1:
            continue
        job = jobs[0]
        endpoint = _JOBS[_call_name(job)]
        compile_results = [c for c in calls if _call_name(c) == "CompileResult"]
        precision_nodes = [_keyword(c, "precision") for c in compile_results]
        precision_nodes = [n for n in precision_nodes if n is not None] or [_keyword(job, "precision")]
        values = {_value(n, constants) for n in precision_nodes if n is not None}
        precision = values.pop() if len(values) == 1 else None
        ordering = _value(_keyword(job, "qubit_ordering"), constants)
        entry = {"precision": precision, "qubit_ordering": ordering}
        if endpoint in out and out[endpoint] != entry:
            entry = {k: v if out[endpoint][k] == v else None for k, v in entry.items()}
        out[endpoint] = entry
    return out
