"""Round-4 request contracts: runner_config errors and per-runner maxima, timing_repeats,
experiment preprocessing axes, literal batch tasks, requested_target, 422 shape, the default
timeout, the OpenAPI version and per-result dispatch annotations."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from config import settings
from schemas import BatchPayload, ExperimentPayload, MeasuredQasmPayload, QasmPayload

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'


@pytest.fixture
def client(monkeypatch):
    from routers import benchmark, experiment
    from routers.errors import register_error_handlers
    from services.security import limiter

    monkeypatch.setattr(limiter, "enabled", False)
    started = []
    monkeypatch.setattr("fastapi.BackgroundTasks.add_task",
                        lambda self, func, *a, **k: started.append((func.__name__, a)))
    app = FastAPI()
    app.state.limiter = limiter
    register_error_handlers(app)
    app.include_router(benchmark.router)
    app.include_router(experiment.router)
    c = TestClient(app)
    c.started = started
    return c


@pytest.mark.parametrize("value", [{"optimization_level": 1}, "1", True, [0, "x"], 9, [0, 7], []])
def test_malformed_runner_config_is_a_readable_422(client, value):
    r = client.post("/compare", json={"qasm_string": QASM, "runner_config": {"qiskit": value}})
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert detail == [{"loc": ["body", "runner_config", "qiskit"],
                       "msg": "runner_config values must be an int 0–3 or a non-empty list of ints 0–3",
                       "type": "value_error"}]
    assert "0x" not in r.text and "function" not in r.text


def test_level_above_a_runners_max_is_400(client):
    r = client.post("/compare", json={"qasm_string": QASM, "runner_config": {"cirq": 3}})
    assert r.status_code == 400
    assert r.json()["detail"] == ("runner_config requests optimization level 3 for 'cirq', "
                                  "whose highest supported level is 2.")
    assert client.post("/compare", json={"qasm_string": QASM, "optimization_level": 3}).status_code == 200


def test_run_count_errors_are_422_lists(client):
    r = client.post("/compare", json={"qasm_string": QASM, "runner_config": {"qiskit": [0] * 17}})
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], list) and "per-runner limit" in r.json()["detail"][0]["msg"]


@pytest.mark.parametrize("model", [QasmPayload, MeasuredQasmPayload])
def test_timing_repeats_bounds(model):
    assert model(qasm_string=QASM).timing_repeats == 1
    assert model(qasm_string=QASM, timing_repeats=10).timing_repeats == 10
    for bad in (0, 11, True):
        with pytest.raises(ValueError):
            model(qasm_string=QASM, timing_repeats=bad)


def test_timing_repeats_reaches_the_worker(client):
    client.post("/compare_measured", json={"qasm_string": QASM + "creg c[2];\nmeasure q -> c;\n",
                                           "timing_repeats": 4})
    name, args = client.started[-1]
    assert name == "worker_compare_measured" and args[-1] == 4


def test_default_timeout_is_one_setting():
    tasks = [{"algorithm": "ghz", "qubits": 2}]
    assert QasmPayload(qasm_string=QASM).timeout_seconds == settings.DEFAULT_TIMEOUT_SEC == 60
    assert MeasuredQasmPayload(qasm_string=QASM).timeout_seconds == 60
    assert BatchPayload(tasks=tasks, mode="measured").timeout_seconds == 60
    assert ExperimentPayload(circuits=tasks).timeout_seconds == 60


@pytest.mark.parametrize("modes", [[], [True, True], [False, False, True]])
def test_experiment_preprocessing_modes_non_empty_and_unique(client, modes):
    r = client.post("/experiments", json={"circuits": [{"algorithm": "ghz", "qubits": 2}],
                                          "preprocessing_modes": modes})
    assert r.status_code == 422, r.text


def test_literal_batch_task_needs_no_algorithm(client):
    r = client.post("/run_batch_suite", json={"mode": "statevector",
                                              "tasks": [{"source": "qasm", "qasm_string": QASM}]})
    assert r.status_code == 200, r.text
    r = client.post("/run_batch_suite", json={"mode": "statevector", "tasks": [{"qubits": 2}]})
    assert r.status_code == 422


def test_requested_target_is_always_recorded(client):
    body = client.post("/compare", json={"qasm_string": QASM,
                                         "execution_target": settings.EXECUTION_MODE}).json()
    assert body["requested_target"] == settings.EXECUTION_MODE
    body = client.post("/experiments", json={"circuits": [{"algorithm": "ghz", "qubits": 2}]}).json()
    assert body["requested_target"] == settings.EXECUTION_MODE


def test_reserved_gate_name_in_batch_and_experiment_literals(client):
    qasm = QASM.replace("qreg q[2];", "gate sleep a { x a; }\nqreg q[2];")
    r = client.post("/run_batch_suite", json={"mode": "statevector", "tasks": [{"qasm_string": qasm}]})
    assert r.status_code == 400 and "reserved by the pytket parser" in r.json()["detail"]
    r = client.post("/experiments", json={"circuits": [{"source": "qasm", "qasm_string": qasm}],
                                          "mode": "statevector"})
    assert r.status_code == 400 and "rename the gate" in r.json()["detail"]


def test_http_422_string_detail_becomes_a_list():
    from fastapi import HTTPException
    from routers.errors import register_error_handlers
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise HTTPException(status_code=422, detail="plain text")
    r = TestClient(app).get("/boom")
    assert r.status_code == 422
    assert r.json() == {"detail": [{"loc": [], "msg": "plain text", "type": "value_error"}]}


def test_validation_loc_drops_pydantic_internals():
    from routers.errors import validation_error_items
    items = validation_error_items([
        {"loc": ("body", "runner_config", "qiskit",
                 "function-after[functools.partial(<function v at 0x7f70c2424ca0>)]"),
         "msg": "Input should be <function v at 0x7f70c2424ca0>", "type": "int_type"},
        {"loc": ("body", "runner_config", "qiskit", "list[function-after[x]]", 0),
         "msg": "bad", "type": "int_type"},
    ])
    assert items[0]["loc"] == ["body", "runner_config", "qiskit"]
    assert "0x" not in items[0]["msg"]
    assert items[1]["loc"] == ["body", "runner_config", "qiskit", 0]


def test_openapi_version_is_the_platform_version(monkeypatch):
    import main
    assert main.app.version == settings.PLATFORM_VERSION


def test_annotation_records_requested_level_and_timeout_kind():
    from services.dispatcher import annotate_result, expand_runner_jobs
    specs = expand_runner_jobs({"cirq": "http://x/run"}, {"optimization_level": 3})
    assert specs[0]["opt_level"] == 2 and specs[0]["requested_level"] == 3
    r = annotate_result({"simulator": "cirq"}, specs[0], {}, "t")
    assert r["optimization_level"] == 2 and r["optimization_level_requested"] == 3
    assert r["timing_statistic"] == "median" and "timeout_kind" not in r
    queued = annotate_result({"error": "TIMEOUT while queued", "timed_out": True,
                              "never_started": True}, specs[0], {}, "t")
    assert queued["dispatch_status"] == "timeout" and queued["timeout_kind"] == "queue"
    ran = annotate_result({"error": "TIMEOUT (60s): x", "timed_out": True}, specs[0], {}, "t")
    assert ran["timeout_kind"] == "run"


def test_runner_config_outside_target_simulators_is_400(client):
    r = client.post("/compare", json={"qasm_string": QASM, "target_simulators": ["qulacs"],
                                      "runner_config": {"qiskit": 0}})
    assert r.status_code == 400 and "not in target_simulators: qiskit" in r.json()["detail"]


@pytest.mark.parametrize("field,value", [("label", "a\x00b"), ("label", "x" * 201)])
def test_experiment_label_rejects_control_characters_and_long_text(client, field, value):
    body = {"circuits": [{"source": "preset", "algorithm": "bell", "qubits": 2}], field: value}
    assert client.post("/experiments", json=body).status_code == 422


def test_non_finite_and_huge_parameters_are_400(client):
    for param in ("1e308", "1e7", "nan", "1/0"):
        r = client.post("/compare", json={"qasm_string": QASM.replace("h q[0];", f"rx({param}) q[0];")})
        assert r.status_code == 400 and r.json()["detail"].startswith("Invalid gate parameter:"), (param, r.text)
