"""Tests for the shared runner scaffolding (helpers.register_runner_endpoints / run_cli_main),
which replaced ~750 lines of per-runner boilerplate."""
import json
from unittest.mock import MagicMock, patch

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
    assert r1.status_code == 200 and r1.json()["result"] == 0
    assert r2.status_code == 200 and r2.json()["result"] == 0


def test_register_runner_endpoints_hard_timeout_flows_through():
    # A runaway processor is killed at the payload's hard_timeout_seconds and returns a TIMEOUT.
    app = FastAPI()
    register_runner_endpoints(app, fx.slow, fx.slow)
    client = TestClient(app)
    r = client.post("/run", json={"circuit_data": "x", "hard_timeout_seconds": 1})
    assert r.status_code == 200 and "TIMEOUT" in r.json()["error"]


def test_run_cli_main_payload_branch(monkeypatch, capsys):
    # The CLI path (k8s --s3-job-id and manual --payload alike) goes through the same
    # run_with_uniform_measurement wrapper as the local isolated-child path, so it also
    # picks up the additive getrusage-based diagnostics.
    monkeypatch.setattr("sys.argv", ["main.py", "--endpoint", "run", "--payload", '{"x": 21}'])
    run_cli_main(None, fx.fast, fx.fast, "Test")
    out = json.loads(capsys.readouterr().out.strip())
    assert out["result"] == 42
    assert isinstance(out["cpu_time_sec"], float) and out["cpu_time_sec"] >= 0
    assert isinstance(out["process_peak_rss_mb"], float) and out["process_peak_rss_mb"] > 0


def test_run_cli_main_measured_endpoint_selects_second_fn(monkeypatch, capsys):
    def measured(p):
        return {"n_shots": p["n_shots"]}
    monkeypatch.setattr("sys.argv",
                        ["main.py", "--endpoint", "run_measured", "--payload", '{"n_shots": 128}'])
    run_cli_main(None, fx.fast, measured, "Test")
    out = json.loads(capsys.readouterr().out.strip())
    assert out["n_shots"] == 128


def test_run_cli_main_requires_payload_or_s3(monkeypatch):
    monkeypatch.setattr("sys.argv", ["main.py", "--endpoint", "run"])
    with pytest.raises(SystemExit):  # argparse error() exits
        run_cli_main(None, fx.fast, fx.fast, "Test")


def test_run_cli_main_s3_job_path_gets_uniform_measurement(monkeypatch):
    # This is the actual Kubernetes dispatch path (dispatcher_k8s.py invokes
    # `main.py --endpoint run --s3-job-id <id>`) — it must get the same warm-up +
    # getrusage diagnostics as the local isolated-child path, not just --payload.
    monkeypatch.setattr("sys.argv",
                        ["main.py", "--endpoint", "run", "--s3-job-id", "job123"])
    monkeypatch.setenv("QROSETTA_PAYLOAD", '{"x": 21}')
    monkeypatch.setenv("S3_BUCKET_NAME", "test-bucket")

    mock_s3 = MagicMock()
    with patch("boto3.client", return_value=mock_s3):
        run_cli_main(None, fx.fast, fx.fast, "Test")

    assert mock_s3.put_object.called
    uploaded = json.loads(mock_s3.put_object.call_args.kwargs["Body"])
    assert uploaded["result"] == 42
    assert isinstance(uploaded["cpu_time_sec"], float) and uploaded["cpu_time_sec"] >= 0
    assert isinstance(uploaded["process_peak_rss_mb"], float) and uploaded["process_peak_rss_mb"] > 0
