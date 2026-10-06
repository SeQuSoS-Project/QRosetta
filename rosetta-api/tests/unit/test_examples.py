"""GET /examples lists the bundled circuits; GET /examples/{name} serves only those."""
import pytest


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


def test_examples_are_listed_and_served(client):
    listed = client.get("/examples").json()
    names = [e["name"] for e in listed]
    assert "qrisp_measured_bias_16q.qasm" in names
    entry = next(e for e in listed if e["name"] == "qrisp_measured_bias_16q.qasm")
    assert entry["mode"] == "measured" and entry["qubits"] == 16
    assert "ghz_state_3q.qasm" not in names and "bell_state_2q.qasm" not in names
    r = client.get("/examples/ghz_state_3q.qasm")
    assert r.status_code == 200 and r.json()["qasm"].startswith("OPENQASM 2.0;")


def test_names_outside_the_bundle_are_refused(client):
    for bad in ("nope.qasm", "..%2Fconfig.py", "ghz_state_3q.txt"):
        assert client.get(f"/examples/{bad}").status_code == 404
