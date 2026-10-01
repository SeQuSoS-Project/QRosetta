"""The frontend's ES-module import graph (static/js) has no cycles, and every relative
import names a module that exists."""
import re
from pathlib import Path

_JS = Path(__file__).resolve().parents[2] / "static" / "js"
_IMPORT = re.compile(r"""^\s*(?:import|export)\s[^'"]*?from\s+['"]\./([\w.-]+\.js)['"]""", re.M)


def _graph() -> dict:
    return {path.name: set(_IMPORT.findall(path.read_text())) for path in sorted(_JS.glob("*.js"))}


def test_relative_imports_resolve():
    graph = _graph()
    missing = sorted((src, dst) for src, deps in graph.items() for dst in deps if dst not in graph)
    assert not missing, f"imports of modules that do not exist: {missing}"


def test_import_graph_is_acyclic():
    graph = _graph()
    state, stack = {}, []

    def visit(node):
        state[node] = "open"
        stack.append(node)
        for dep in sorted(graph.get(node, ())):
            if state.get(dep) == "open":
                cycle = stack[stack.index(dep):] + [dep]
                raise AssertionError("import cycle: " + " -> ".join(cycle))
            if dep not in state:
                visit(dep)
        stack.pop()
        state[node] = "done"

    for node in graph:
        if node not in state:
            visit(node)
