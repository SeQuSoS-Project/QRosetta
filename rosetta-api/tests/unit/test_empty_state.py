"""emptyStateModel (static/js/empty_state.js): the results area before a run shows the tabs and
table the result will have, with no value in any cell, and its columns match the real tables."""
import re
from pathlib import Path

from tests.unit.frontend_harness import call_js, requires_node

pytestmark = requires_node

_STATIC = Path(__file__).resolve().parents[2] / "static"
EXAMPLES = [{"value": "example:rotation_1q.qasm", "label": "Single rotation (statevector)"}]


def _model(**over):
    data = {"source": "editor", "circuitName": "GHZ State (3q)", "playlist": ["GHZ State (3q)", "qft (4q)"],
            "modes": {"statevector": True, "measured": False}, "preprocessing": "on", "compilerCount": 0,
            "backends": ["Cirq (Google)", "Qiskit (IBM)"], "backendsLoaded": True, "examples": EXAMPLES}
    data.update(over)
    (model,) = call_js(["empty_state.js"], [("emptyStateModel", [data])])
    return model


def _summary_columns():
    return re.findall(r"_th\('([^']+)'", (_STATIC / "js" / "overview_renderer.js").read_text())


def _suite_columns():
    html = (_STATIC / "index.html").read_text()
    block = html[html.index('id="tpl-suite-table-wrapper"'):html.index('id="tpl-suite-summary-row"')]
    return [c for c in re.findall(r"<th[^>]*>([^<]*)</th>", block) if c]


def _tab_labels(tabs):
    text = (_STATIC / "js" / "renderers.js").read_text()
    labels = dict(re.findall(r"'?([a-z-]+)'?: '([A-Za-z ]+)'", text[text.index("const TAB_LABELS"):text.index("export function showTab")]))
    return [labels[t] for t in tabs]


def test_no_cell_holds_a_value():
    for model in (_model(), _model(source="list"), _model(modes={"statevector": False, "measured": True}),
                  _model(preprocessing="both")):
        assert model["kicker"] == "No results yet"
        for row in model["table"]["rows"]:
            assert set(row[1:]) == {"—"}


def test_backend_columns_match_the_summary_table():
    summary = _summary_columns()
    assert _model()["table"]["columns"] == [c for c in summary if c != "Inconclusive with"]
    assert _model(modes={"statevector": False, "measured": True})["table"]["columns"] == summary
    assert [r[0] for r in _model()["table"]["rows"]] == ["Cirq (Google)", "Qiskit (IBM)"]


def test_playlist_columns_match_the_suite_table():
    model = _model(source="list")
    assert model["table"]["columns"] == _suite_columns()
    assert [r[0] for r in model["table"]["rows"]] == ["GHZ State (3q)", "qft (4q)"]
    assert model["tabs"] == _tab_labels(["suite-summary", "raw"])


def test_tabs_are_the_ones_a_result_gets():
    assert _model()["tabs"] == _tab_labels(["summary", "agreement", "performance", "circuits", "export"])
    assert _model(modes={"statevector": False, "measured": False}, compilerCount=2)["tabs"] == _tab_labels(["summary", "circuits", "raw"])


def test_states_without_a_table():
    assert _model(modes={"statevector": False, "measured": False})["title"] == "Nothing to run yet"
    assert _model(backends=[])["title"] == "No backend is ticked"
    loading = _model(backends=[], backendsLoaded=False)
    assert loading["text"] == "Loading the backend list." and loading["table"] is None
    compile_only = _model(modes={"statevector": False, "measured": False}, compilerCount=2)
    assert compile_only["title"] == "Ready to compile GHZ State (3q)" and compile_only["table"] is None


def test_sentence_names_the_runs():
    assert "as a statevector run and compares" in _model()["text"]
    both = _model(modes={"statevector": True, "measured": True})["text"]
    assert "as a statevector run and then as a measured run, and compares" in both
    assert "preprocessing on and then off" in _model(preprocessing="both")["text"]
