"""V1-13: numbers built to exhaust the parsers (huge powers, thousands of digits, deep nesting) are
a 400 within a second on every route that takes a circuit, never a 500."""
import time

import pytest

pytest.importorskip("pytket")

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

H = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
D = "9" * 5000
CIRCUITS = {
    "power": H + "qreg q[1];\nrz(2^1000000) q[0];\n",
    "digits": H + "qreg q[1];\nrz(" + "1" * 5000 + ") q[0];\n",
    "tower": H + "qreg q[1];\nrz(pi^pi^pi) q[0];\n",
    "parentheses": H + "qreg q[1];\nrz(" + "(" * 10000 + "1" + ")" * 10000 + ") q[0];\n",
    "unary": H + "qreg q[1];\nrz(" + "-" * 10000 + "1) q[0];\n",
    "body_power": H + "gate g(t) a { rz(t^1000000) a; }\nqreg q[1];\ng(2) q[0];\n",
    "qreg_digits": H + f"qreg q[{D}];\n",
    "creg_digits": H + f"qreg q[1];\ncreg c[{D}];\n",
    "index_digits": H + f"qreg q[1];\nx q[{D}];\n",
    "if_digits": H + f"qreg q[1];\ncreg c[1];\nmeasure q[0] -> c[0];\nif(c=={D}) x q[0];\n",
}


@pytest.fixture
def client(monkeypatch):
    from services.security import limiter
    monkeypatch.setattr(limiter, "enabled", False)
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("name", sorted(CIRCUITS))
@pytest.mark.parametrize("route", ["/compare", "/compare_measured", "/visualize/quirk"])
def test_v1_13_a_pathological_number_is_a_400_within_a_second(client, name, route):
    qasm = CIRCUITS[name]
    if route == "/compare_measured" and "measure" not in qasm:
        qasm += "creg m[1];\nmeasure q[0] -> m[0];\n"
    started = time.monotonic()
    response = client.post(route, json={"qasm_string": qasm})
    assert time.monotonic() - started < 1.0, (route, name)
    assert response.status_code == 400, (route, name, response.status_code, response.text[:200])


@pytest.mark.parametrize("name", sorted(CIRCUITS))
def test_v1_13_a_playlist_task_with_one_is_refused_at_submit(client, name):
    started = time.monotonic()
    response = client.post("/run_batch_suite", json={"mode": "statevector", "tasks": [
        {"algorithm": "x", "qasm_string": CIRCUITS[name]}]})
    assert time.monotonic() - started < 1.0
    assert response.status_code == 400, (name, response.status_code, response.text[:200])


@pytest.mark.parametrize("name", sorted(CIRCUITS))
def test_v1_13_experiments_and_plans_answer_without_a_500(client, name):
    started = time.monotonic()
    experiment = client.post("/experiments", json={"mode": "statevector", "circuits": [
        {"source": "qasm", "qasm_string": CIRCUITS[name]}]})
    plan = client.post("/plan", json={"source": "single", "modes": ["statevector"], "preprocessing": "on",
                                      "circuits": [{"qasm_string": CIRCUITS[name], "name": "x"}]})
    assert time.monotonic() - started < 2.0
    assert experiment.status_code == 400, (name, experiment.status_code, experiment.text[:200])
    assert plan.status_code == 200, (name, plan.status_code, plan.text[:200])
