"""qrosetta run, wait, show summary, export and selftest against the real FastAPI app through
TestClient (job `cli-contract`): plan -> submit -> wait -> save -> summary -> crate on a fake
runner fleet, exit codes from the server's summary, --set and --request through the real
planner, playlists, and an expired job read from the saved files."""

import io
import json
import math
import os
import zipfile

import numpy as np
import pytest

from tests.unit._qrosetta_app import BELL, app_server  # noqa: F401

from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.client import results, waiting  # noqa: E402
from qrosetta_cli.errors import Exit  # noqa: E402
from tests.unit.test_qrosetta_contracts import validate_envelope  # noqa: E402


@pytest.fixture(autouse=True)
def no_pause(monkeypatch):
    monkeypatch.setattr(waiting, "pause", lambda seconds: None)


@pytest.fixture
def env(tmp_path):
    return {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_CONFIG_HOME": str(tmp_path / "cfg"),
            "QROSETTA_RESULTS_DIR": str(tmp_path / "res")}


@pytest.fixture
def bell(tmp_path):
    path = tmp_path / "bell.qasm"
    path.write_text(BELL)
    return str(path)


def cli(argv, env, transport):
    return main(argv, env=env, transport_factory=transport)


def envelope(capsys):
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    return doc


def posted(transport, path):
    return [json.loads(body) for method, p, _, body in transport.requests if method == "POST" and p == path]


def test_full_statevector_and_measured_run(app_server, env, bell, capsys):
    transport, fleet = app_server
    code = cli(["run", bell, "-m", "statevector,measured", "--shots", "2000", "--crate", "--name", "Bell pair",
                "--json"], env, transport)
    doc = envelope(capsys)
    assert code == 0, doc
    jobs = doc["data"]["jobs"]
    assert [j["mode"] for j in jobs] == ["statevector", "measured"]
    assert [j["endpoint"] for j in jobs] == ["/compare", "/compare_measured"]
    inv = doc["data"]["results_dir"]
    assert os.path.basename(inv).endswith("-bell-pair")
    plan = json.load(open(os.path.join(inv, "plan.json")))
    (plan_request,) = posted(transport, "/plan")
    assert plan["plan_request"] == plan_request and plan_request["settings"] == {
        "n_shots": {"value": 2000, "source": "flag"}}
    for job, run in zip(jobs, plan["plan"]["runs"]):
        d = job["dir"]
        assert results.read_status(d) == "complete"
        request = json.load(open(os.path.join(d, "request.json")))
        assert request["payload"] == run["payload"] == posted(transport, run["endpoint"])[0]
        report = transport.client.get(f"/jobs/{job['job_id']}/report").content
        assert open(os.path.join(d, "report.json"), "rb").read() == report
        assert json.load(open(os.path.join(d, "summary.json"))) == transport.client.get(
            f"/jobs/{job['job_id']}/summary").json() == job["summary"]
        with zipfile.ZipFile(os.path.join(d, "ro-crate.zip")) as z:
            assert any(n.endswith("ro-crate-metadata.json") for n in z.namelist())
        assert len(job["summary"]["pair_verdicts"]) == 3 and job["backends"] == ["qiskit", "cirq", "qulacs"]
    assert jobs[0]["summary"]["outcomes"]["agrees"] == 3
    measured_request = json.load(open(os.path.join(jobs[1]["dir"], "request.json")))
    assert measured_request["sources"]["n_shots"] == "flag" and measured_request["sources"]["seed"] == "server_default"
    assert len(fleet.calls) == 2


def test_exit_codes_come_from_the_server_summary(app_server, env, bell, capsys):
    from services.analysis.divergence import ANALYSIS_VERSION
    transport, fleet = app_server
    fleet.vectors["qulacs"] = np.array([1, 0, 0, 0], dtype=complex)
    assert cli(["run", bell, "--fail-on", "differs", "--json"], env, transport) == Exit.DISAGREEMENT
    doc = envelope(capsys)
    assert doc["outcome"] == {"rule_version": ANALYSIS_VERSION, "fail_on": ["differs"], "matched": ["differs"]}
    assert doc["error"] is None and doc["data"]["jobs"][0]["summary"]["outcomes"]["differs"] == 2
    assert cli(["run", bell], env, transport) == 0
    capsys.readouterr()
    fleet.vectors["qulacs"] = np.array([1, 0, 0, 1], dtype=complex) / math.sqrt(2)
    fleet.errors["cirq"] = "simulator crashed"
    assert cli(["run", bell, "--fail-on", "differs,runs-without-output"], env, transport) == Exit.RUNS_WITHOUT_OUTPUT
    assert cli(["run", bell, "--fail-on", "no_such_name"], env, transport) == Exit.INCOMPATIBLE


def test_set_and_replay_go_through_the_real_planner(app_server, env, bell, capsys):
    transport, fleet = app_server
    assert cli(["run", bell, "--set", "n_shots=5"], env, transport) == Exit.USAGE
    assert cli(["run", bell, "--set", "no_such_field=1"], env, transport) == Exit.INCOMPATIBLE
    assert posted(transport, "/plan") == []
    capsys.readouterr()
    assert cli(["run", bell, "-m", "measured", "--shots", "1000", "--json"], env, transport) == 0
    first = envelope(capsys)["data"]
    original = posted(transport, "/compare_measured")[0]
    assert original["seed"] is None
    report = json.load(open(os.path.join(first["jobs"][0]["dir"], "report.json")))
    assert cli(["run", "--request", os.path.join(first["results_dir"], "plan.json"), "--json"], env, transport) == 0
    second = envelope(capsys)["data"]
    replayed = posted(transport, "/compare_measured")[1]
    assert replayed["seed"] == report["seed"] and replayed["n_shots"] == 1000
    assert replayed["qasm_string"] == original["qasm_string"]
    for field in ("optimization_level", "timing_repeats", "runner_phases", "timeout_seconds", "thresholds",
                  "target_simulators", "apply_preprocessing"):
        assert field in replayed, field
    assert replayed["target_simulators"] == sorted(report["resolved_runners"]["dispatched"])
    sources = json.load(open(os.path.join(second["jobs"][0]["dir"], "request.json")))["sources"]
    assert sources["seed"] == sources["optimization_level"] == sources["target_simulators"] == "replay"
    assert second["jobs"][0]["summary"]["outcomes"] == first["jobs"][0]["summary"]["outcomes"]


def test_playlist_with_server_references(app_server, env, bell, capsys):
    transport, fleet = app_server
    assert cli(["run", "algorithm:ghz:3", bell, "--json"], env, transport) == 0
    doc = envelope(capsys)
    (job,) = doc["data"]["jobs"]
    assert job["endpoint"] == "/run_batch_suite" and job["dir"].split(os.sep)[-1].startswith("statevector-")
    tasks = posted(transport, "/run_batch_suite")[0]["tasks"]
    assert tasks[0] == {"algorithm": "ghz", "qubits": 3} and tasks[1]["qasm_string"] == BELL
    assert len(job["summary"]["benchmark_summary"]) == 2
    assert cli(["show", "summary"], env, transport) == 0
    out = capsys.readouterr().out
    assert "circuit 0:" in out and "circuit 1:" in out


def test_an_expired_job_is_read_from_the_saved_files(app_server, env, bell, capsys, tmp_path):
    import services.job_manager as job_manager
    transport, fleet = app_server
    assert cli(["run", bell, "--json"], env, transport) == 0
    job = envelope(capsys)["data"]["jobs"][0]
    job_manager.ACTIVE_JOBS.pop(job["job_id"])
    os.unlink(os.path.join(job["dir"], "summary.json"))
    assert cli(["show", "summary", "--result", f"job:{job['job_id'][:8]}", "--json"], env, transport) == 0
    shown = envelope(capsys)["data"]["jobs"][0]
    assert shown["source"] == "POST /summary of the saved report.json"
    assert shown["summary"]["report_source"] == "client_supplied" and shown["summary"]["outcomes"]["agrees"] == 3
    assert cli(["export", "crate", "--result", job["dir"]], env, transport) == Exit.USAGE
    assert cli(["export", "crate", "--result", job["dir"], "--allow-supplied", "--json"], env, transport) == 0
    path = envelope(capsys)["data"]["path"]
    assert path.endswith("ro-crate.client-supplied.zip")
    with zipfile.ZipFile(path) as z:
        meta = next(n for n in z.namelist() if n.endswith("ro-crate-metadata.json"))
        assert "client_supplied" in z.read(meta).decode()
    out = tmp_path / "report.json"
    assert cli(["export", "report", "--result", job["dir"], "-o", str(out)], env, transport) == 0
    assert out.read_bytes() == open(os.path.join(job["dir"], "report.json"), "rb").read()


def test_dry_run_prints_the_real_plan_and_runs_nothing(app_server, env, bell, capsys):
    transport, fleet = app_server
    assert cli(["run", bell, "-m", "measured", "--seed", "7", "--dry-run", "--json"], env, transport) == 0
    doc = envelope(capsys)
    (run,) = doc["data"]["plan"]["runs"]
    assert run["endpoint"] == "/compare_measured" and run["payload"]["seed"] == 7 and run["sources"]["seed"] == "flag"
    assert posted(transport, "/compare_measured") == [] and fleet.calls == []


def test_selftest_against_a_server_without_it(app_server, env, capsys):
    from services import server_info
    transport, fleet = app_server
    if server_info.FEATURES.get("selftest"):
        pytest.skip("this server offers the self-test")
    assert cli(["selftest"], env, transport) == Exit.INCOMPATIBLE
    assert "offers no self-test" in capsys.readouterr().err
    assert fleet.calls == []


def test_wait_after_detach_on_the_real_app(app_server, env, bell, capsys):
    transport, fleet = app_server
    assert cli(["run", bell, "--detach"], env, transport) == 0
    capsys.readouterr()
    assert cli(["wait", "--json"], env, transport) == 0
    doc = envelope(capsys)
    assert doc["data"]["jobs"][0]["save_status"] == "complete"
    assert io.BytesIO(open(os.path.join(doc["data"]["jobs"][0]["dir"], "report.json"), "rb").read()).read(1) == b"{"
