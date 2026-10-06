"""planRuns (static/js/run_plan.js): the requests one press of Run sends, and that every
payload is accepted by the request schema it is sent to."""
import pytest

from schemas import BatchPayload, ExperimentPayload, MeasuredQasmPayload, QasmPayload
from tests.unit.frontend_harness import call_js, requires_node

pytestmark = requires_node

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'
COMMON = {"optimization_level": 0, "timeout_seconds": 60, "timing_repeats": 1, "exclusive": False,
          "runner_config": {}, "runner_phases": {}, "target_simulators": ["qiskit", "cirq"],
          "execution_target": "local", "bypass_limits": False, "thresholds": None}
SCHEMA = {"/compare": QasmPayload, "/compare_measured": MeasuredQasmPayload,
          "/run_batch_suite": BatchPayload, "/experiments": ExperimentPayload}
LIST = [{"algorithm": "ghz", "qubits": 3, "name": "GHZ State (Entanglement)"},
        {"source": "mqt", "algorithm": "qft", "qubits": 4, "name": "qft (4q)"},
        {"algorithm": "custom", "qubits": 2, "name": "mine", "qasm_string": QASM}]


def _ws(**over):
    ws = {"source": "editor", "editor": {"qasm": QASM, "name": "Bell (2q)"}, "list": LIST,
          "modes": {"statevector": True, "measured": False}, "compilers": {}, "preprocessing": "on",
          "runName": "", "shots": 8200, "seed": None, "common": COMMON}
    ws.update(over)
    return ws


def _plan(ws):
    (result,) = call_js(["run_plan.js"], [("planRuns", [ws])])
    for run in result["runs"]:
        SCHEMA[run["endpoint"]](**run["payload"])
    return result


def test_editor_circuit_statevector_is_one_compare():
    plan = _plan(_ws())
    assert [r["endpoint"] for r in plan["runs"]] == ["/compare"]
    assert plan["runs"][0]["payload"]["apply_preprocessing"] is True
    assert "n_shots" not in plan["runs"][0]["payload"]


def test_list_runs_as_one_batch_with_names():
    plan = _plan(_ws(source="list", modes={"statevector": False, "measured": True}, seed=7))
    (run,) = plan["runs"]
    assert run["endpoint"] == "/run_batch_suite" and run["payload"]["mode"] == "measured"
    assert run["payload"]["n_shots"] == 8200 and run["payload"]["seed"] == 7
    assert [t.get("name") for t in run["payload"]["tasks"]] == ["GHZ State (Entanglement)", None, "mine"]
    assert run["payload"]["tasks"][1]["source"] == "mqt"


def test_both_modes_make_two_runs_with_compilers_on_the_first_only():
    plan = _plan(_ws(modes={"statevector": True, "measured": True}, compilers={"pyzx": [1]}))
    assert [r["endpoint"] for r in plan["runs"]] == ["/compare", "/compare_measured"]
    assert plan["runs"][0]["payload"]["compilers"] == {"pyzx": [1]}
    assert plan["runs"][1]["payload"]["compilers"] == {}


def test_preprocessing_both_is_an_experiment():
    plan = _plan(_ws(source="list", preprocessing="both"))
    (run,) = plan["runs"]
    assert run["endpoint"] == "/experiments" and run["payload"]["preprocessing_modes"] == [True, False]
    assert run["payload"]["circuits"][1] == {"source": "mqt", "algorithm": "qft", "qubits": 4, "name": "qft"}
    editor = _plan(_ws(preprocessing="both"))["runs"][0]
    assert editor["payload"]["circuits"][0]["source"] == "qasm"


def test_compilers_only_is_a_compile_only_request():
    plan = _plan(_ws(modes={"statevector": False, "measured": False}, compilers={"staq": [1]}, preprocessing="off"))
    (run,) = plan["runs"]
    assert run["endpoint"] == "/compare" and run["payload"]["simulate"] is False
    assert run["payload"]["apply_preprocessing"] is False
    assert "target_simulators" not in run["payload"] and "runner_config" not in run["payload"]
    batch = _plan(_ws(source="list", modes={"statevector": False, "measured": False}, compilers={"staq": [1]}))
    assert batch["runs"][0]["payload"]["simulate"] is False and batch["runs"][0]["payload"]["mode"] == "statevector"


@pytest.mark.parametrize("over,needle", [
    ({"modes": {"statevector": False, "measured": False}}, "Choose at least one"),
    ({"source": "list", "list": []}, "playlist is empty"),
    ({"editor": {"qasm": "  ", "name": ""}}, "editor is empty"),
    ({"modes": {"statevector": False, "measured": False}, "compilers": {"staq": [1]}, "preprocessing": "both"}, "one preprocessing"),
])
def test_impossible_requests_explain_why(over, needle):
    plan = _plan(_ws(**over))
    assert plan["runs"] == [] and needle in plan["error"]


def test_button_label_says_what_will_run():
    labels = call_js(["run_plan.js"], [
        ("runButtonLabel", [_ws(), 14]),
        ("runButtonLabel", [_ws(source="list", modes={"statevector": True, "measured": True}), 14]),
        ("runButtonLabel", [_ws(modes={"statevector": False, "measured": False}, compilers={"staq": [1]}), 14]),
    ])
    assert labels == ["Run Editor Code · Statevector · 14 backends",
                      "Run Batch (3 circuits) · Statevector + Measured · 14 backends",
                      "Compile Editor Code"]
