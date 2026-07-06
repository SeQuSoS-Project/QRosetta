"""Tests for the shared runner scaffolding (helpers.register_runner_endpoints / run_cli_main),
which replaced ~750 lines of per-runner boilerplate."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from qrosetta_commons.helpers import register_runner_endpoints, run_cli_main
from tests.unit import _isolated_fixture as fx


def test_register_runner_endpoints_serves_both_routes():
    app = FastAPI()
    # module-level fixture functions so run_isolated can resolve them in the spawned child
    register_runner_endpoints(app, fx.fast, fx.fast)
    client = TestClient(app)

    r1 = client.post("/run", json={"circuit_data": "OPENQASM 2.0;"})
    r2 = client.post("/run_measured", json={"circuit_data": "OPENQASM 2.0;", "n_shots": 8})
    assert r1.status_code == 200 and r1.json() == {"result": 0}
    assert r2.status_code == 200 and r2.json() == {"result": 0}


def test_register_runner_endpoints_hard_timeout_flows_through():
    # A runaway processor is killed at the payload's hard_timeout_seconds and returns a TIMEOUT.
    app = FastAPI()
    register_runner_endpoints(app, fx.slow, fx.slow)
    client = TestClient(app)
    r = client.post("/run", json={"circuit_data": "x", "hard_timeout_seconds": 1})
    assert r.status_code == 200 and "TIMEOUT" in r.json()["error"]


def test_run_cli_main_payload_branch(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["main.py", "--endpoint", "run", "--payload", '{"x": 21}'])
    run_cli_main(None, fx.fast, fx.fast, "Test")
    out = json.loads(capsys.readouterr().out.strip())
    assert out == {"result": 42}


def test_run_cli_main_measured_endpoint_selects_second_fn(monkeypatch, capsys):
    def measured(p):
        return {"n_shots": p["n_shots"]}
    monkeypatch.setattr("sys.argv",
                        ["main.py", "--endpoint", "run_measured", "--payload", '{"n_shots": 128}'])
    run_cli_main(None, fx.fast, measured, "Test")
    assert json.loads(capsys.readouterr().out.strip()) == {"n_shots": 128}


def test_run_cli_main_requires_payload_or_s3(monkeypatch):
    monkeypatch.setattr("sys.argv", ["main.py", "--endpoint", "run"])
    with pytest.raises(SystemExit):  # argparse error() exits
        run_cli_main(None, fx.fast, fx.fast, "Test")
