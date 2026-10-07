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


LIMITS = {"maxRequestBytes": 1_048_576, "maxQasmSize": 1_000_000, "maxExperimentCells": 200,
          "executionMode": "local"}


def _problems(ws, limits=LIMITS):
    (result,) = call_js(["run_plan.js"], [("planRuns", [ws])])
    (problems,) = call_js(["run_plan.js"], [("runLimitProblems", [result["runs"], limits])])
    return problems


def test_experiment_over_the_cell_limit_is_refused_unless_bypassed():
    many = [{"algorithm": "ghz", "qubits": 3, "name": f"g{i}"} for i in range(101)]
    problems = _problems(_ws(source="list", list=many, preprocessing="both"))
    assert len(problems) == 1 and "202 experiment runs" in problems[0] and "at most 100 circuits" in problems[0]
    assert _problems(_ws(source="list", list=many[:100], preprocessing="both")) == []
    bypass = dict(COMMON, bypass_limits=True)
    assert _problems(_ws(source="list", list=many, preprocessing="both", common=bypass)) == []


def test_a_circuit_under_the_size_limit_can_still_overflow_the_request_body():
    qasm = QASM + "".join(f"h q[{i % 2}];\n\n\n" for i in range(95_000))
    assert len(qasm) < 1_000_000
    problems = _problems(_ws(editor={"qasm": qasm, "name": "big"}))
    assert len(problems) == 1 and "upload limit" in problems[0] and "Line breaks" in problems[0]


def test_a_playlist_of_literal_circuits_is_told_to_split():
    part = QASM + "".join(f"x q[{i % 2}];\n" for i in range(30_000))
    items = [{"algorithm": "custom", "qubits": 2, "name": f"c{i}", "qasm_string": part} for i in range(4)]
    problems = _problems(_ws(source="list", list=items))
    assert len(problems) == 1 and "4 circuits" in problems[0] and "Split the playlist" in problems[0]


def test_circuit_text_over_the_size_limit_is_named_unless_bypassed_locally():
    qasm = QASM + "// " + "x" * 1_000_000 + "\n"
    big = {"algorithm": "custom", "qubits": 2, "name": "huge", "qasm_string": qasm}
    roomy = dict(LIMITS, maxRequestBytes=10**8)
    assert _problems(_ws(source="list", list=[big]), roomy) == [
        f'Circuit "huge" has {len(qasm):,} characters; the server accepts circuits of up to 1,000,000.']
    bypass = dict(COMMON, bypass_limits=True)
    assert _problems(_ws(source="list", list=[big], common=bypass), roomy) == []
    assert _problems(_ws(source="list", list=[big], common=bypass), dict(roomy, executionMode="kubernetes")) != []


def test_names_are_printable_and_bounded_everywhere():
    long = "n" * 250
    item = {"algorithm": "x‮" + long, "qubits": 2, "name": "a​b\u0007" + long, "qasm_string": QASM}
    for ws in (_ws(source="list", list=[item]), _ws(source="list", list=[item], preprocessing="both")):
        payload = _plan(ws)["runs"][0]["payload"]
        circuit = (payload.get("tasks") or payload["circuits"])[0]
        for field in ("name", "algorithm"):
            if field in circuit:
                assert len(circuit[field]) <= 200
                assert not {"‮", "​", "\u0007"} & set(circuit[field])
    label = _plan(_ws(preprocessing="both", runName="r " + long))["runs"][0]["payload"]["label"]
    assert len(label) == 200 and " " not in label


def test_label_and_size_helpers():
    results = call_js(["request_limits.js"], [
        ("printableLabel", ["  a\u0000b⁦c  ", 200]),
        ("printableLabel", ["\U0001F600" * 3, 2]),
        ("labelProblem", ["ok", 200, "The run name"]),
        ("labelProblem", ["a‎b", 200, "The run name"]),
        ("labelProblem", ["x" * 201, 200, "The run name"]),
        ("jsonBytes", [{"q": "a\nb\"é"}]),
        ("formatBytes", [1048576]),
    ])
    assert results[0] == "abc"
    assert results[1] == "\U0001F600" * 2
    assert results[2] is None
    assert "control characters" in results[3]
    assert results[4] == "The run name has 201 characters; at most 200 are allowed."
    assert results[5] == len('{"q":"a\\nb\\"é"}'.encode())
    assert results[6] == "1,048,576 bytes (1.00 MiB)"
