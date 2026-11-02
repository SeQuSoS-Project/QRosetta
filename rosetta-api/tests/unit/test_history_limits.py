"""Saved runs and circuits per account stop at MAX_SAVED_RUNS and MAX_SAVED_CIRCUITS (409)."""
import pytest

from config import settings
from tests.unit.authz_world import world

BELL = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'


@pytest.fixture
def w(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MAX_SAVED_CIRCUITS", 2)
    with world(tmp_path, monkeypatch) as built:
        yield built


def test_the_circuit_after_the_limit_is_refused(w):
    headers = w.headers(w.user())
    for i in range(2):
        assert w.client.post("/history/circuits", json={"name": f"c{i}", "qasm_string": BELL},
                             headers=headers).status_code == 201
    third = w.client.post("/history/circuits", json={"name": "c2", "qasm_string": BELL}, headers=headers)
    assert third.status_code == 409 and "at most 2 saved circuits" in third.json()["detail"]
    other = w.headers(w.user())
    assert w.client.post("/history/circuits", json={"name": "c0", "qasm_string": BELL},
                         headers=other).status_code == 201
