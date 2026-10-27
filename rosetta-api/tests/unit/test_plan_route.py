"""POST /plan as a route: settings rules, field sources, the request checks, check_circuits,
and its body limit."""
import pytest

pytest.importorskip("pytket")

from fastapi.testclient import TestClient  # noqa: E402

from config import settings  # noqa: E402
from main import app  # noqa: E402
from services.plan_text import bare_circuit_name, js_json, js_number_text, js_parse_int_or_zero, printable_label  # noqa: E402

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'


@pytest.fixture
def client(monkeypatch):
    from services.security import limiter
    monkeypatch.setattr(limiter, "enabled", False)
    return TestClient(app)


def _single(**over):
    body = {"source": "single", "circuits": [{"qasm_string": QASM, "name": "Bell (2q)"}],
            "modes": ["statevector", "measured"], "preprocessing": "on"}
    body.update(over)
    return body


def test_only_given_settings_reach_the_payload(client):
    body = _single(settings={"n_shots": {"value": 500, "source": "flag"},
                             "optimization_level": {"value": 1, "source": "replay"}})
    plan = client.post("/plan", json=body).json()
    assert plan["schema"] == "qrosetta.plan@1" and plan["problems"] == []
    sv, ms = plan["runs"]
    assert sv["endpoint"] == "/compare" and ms["endpoint"] == "/compare_measured"
    assert set(sv["payload"]) == {"optimization_level", "compilers", "apply_preprocessing", "qasm_string"}
    assert ms["payload"]["n_shots"] == 500 and ms["payload"]["seed"] is None
    assert ms["sources"]["n_shots"] == "flag" and ms["sources"]["optimization_level"] == "replay"
    assert ms["sources"]["qasm_string"] == "plan" and ms["sources"]["seed"] == "plan"
    assert ms["title"] == "Bell (Measured, 500 shots)"


def test_a_measured_title_without_shots_names_the_default(client):
    plan = client.post("/plan", json=_single(modes=["measured"])).json()
    assert plan["runs"][0]["title"] == f"Bell (Measured, {settings.DEFAULT_SHOTS} shots)"
    assert "n_shots" not in plan["runs"][0]["payload"]


@pytest.mark.parametrize("name,setting", [
    ("tasks", {"value": [], "source": "flag"}),
    ("no_such_field", {"value": 1, "source": "set"}),
    ("n_shots", {"value": 10, "source": "set"}),
    ("timeout_seconds", {"value": 10, "source": "set"}),
])
def test_settings_the_planner_refuses(client, name, setting):
    response = client.post("/plan", json=_single(settings={name: setting}))
    assert response.status_code == 400 and f"settings.{name}" in response.json()["detail"]


def test_a_payload_that_fails_its_schema_is_a_problem(client):
    plan = client.post("/plan", json=_single(settings={"timeout_seconds": {"value": 1, "source": "flag"}})).json()
    assert [p["code"] for p in plan["problems"]] == ["invalid_request", "invalid_request"]
    assert plan["problems"][0]["params"]["field"] == "timeout_seconds"


def test_bypass_needs_an_account_off_local(client, monkeypatch):
    monkeypatch.setattr(settings, "EXECUTION_MODE", "kubernetes")
    plan = client.post("/plan", json=_single(
        modes=["statevector"], settings={"bypass_limits": {"value": True, "source": "flag"}})).json()
    assert [p["code"] for p in plan["problems"]] == ["bypass_needs_account"]


def test_check_circuits_reports_the_route_refusal_with_its_line(client):
    bad = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nnosuchgate q[0];\n'
    body = {"source": "playlist", "modes": ["statevector"], "check_circuits": True,
            "circuits": [{"algorithm": "ghz", "qubits": 3}, {"qasm_string": bad, "name": "bad"}]}
    plan = client.post("/plan", json=body).json()
    (problem,) = plan["problems"]
    assert problem["code"] == "circuit_refused" and problem["circuit_index"] == 1
    assert problem["line"] == 4 and problem["run_index"] == 0
    assert client.post("/plan", json={**body, "check_circuits": False}).json()["problems"] == []


def test_plan_errors_come_back_as_problems(client):
    plan = client.post("/plan", json=_single(modes=[], compilers={})).json()
    assert plan["runs"] == [] and [p["code"] for p in plan["problems"]] == ["no_mode"]
    plan = client.post("/plan", json={"source": "playlist", "circuits": [], "modes": ["measured"]}).json()
    assert [p["code"] for p in plan["problems"]] == ["playlist_empty"]


def test_the_plan_body_limit_is_larger_than_the_run_limit(client):
    big = "x" * (settings.MAX_UPLOAD_BYTES + 10)
    body = _single(modes=["statevector"], circuits=[{"qasm_string": big, "name": "big"}])
    plan = client.post("/plan", json=body)
    assert plan.status_code == 200
    assert {p["code"] for p in plan.json()["problems"]} >= {"circuit_too_large", "request_too_large"}
    assert client.post("/compare", json={"qasm_string": big}).status_code == 413
    huge = _single(circuits=[{"qasm_string": "x" * (settings.MAX_PLAN_REQUEST_BYTES + 1)}])
    assert client.post("/plan", json=huge).status_code == 413


def test_plan_is_rate_limited_and_published(client):
    from services.security import limiter
    from routers.plan import plan_endpoint
    assert "routers.plan.plan_endpoint" in limiter._route_limits
    limits = client.get("/config").json()["limits"]
    assert limits["plan_rate_limit"] == settings.PLAN_RATE_LIMIT
    assert limits["max_plan_request_bytes"] == settings.MAX_PLAN_REQUEST_BYTES
    assert callable(plan_endpoint)


@pytest.mark.parametrize("value,text", [
    (1e-5, "0.00001"), (1e-7, "1e-7"), (1.5e22, "1.5e+22"), (123.456, "123.456"), (8200.0, "8200"),
    (-0.0, "0"), (0.1, "0.1"), (1e21, "1e+21"), (123456789012345680000.0, "123456789012345680000"),
])
def test_numbers_are_written_as_javascript_writes_them(value, text):
    assert js_number_text(value) == text


def test_text_rules():
    assert js_json({"a": "\ud800", "b": [1.0, None]}) == '{"a":"\\ud800","b":[1,null]}'
    assert js_parse_int_or_zero(" 0x1F") == 31 and js_parse_int_or_zero("4q") == 4
    assert js_parse_int_or_zero(None) == 0 and js_parse_int_or_zero(True) == 0
    assert bare_circuit_name("GHZ (3q) (3q) ") == "GHZ" and bare_circuit_name("a (3q)\n") == "a"
    assert printable_label("a​b", 200) == "ab" and printable_label("́", 200) == ""
    assert printable_label("x" * 300, 200) == "x" * 200
