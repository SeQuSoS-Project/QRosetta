"""qrosetta show circuits, show diff, show artifacts, show views, export figure and export views
against the real app (experimental views, spec §6.20-§6.21): the panes GET /jobs/{id}/circuit-texts
serves, kept in the job's directory with SHA256SUMS refreshed; after the job expires, the panes of
the saved crate and figures drawn from the saved report.json as client-supplied."""

import json
import os

import pytest

from tests.unit._qrosetta_app import BELL, app_server  # noqa: F401

from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.client import circuits, figures, results, waiting  # noqa: E402
from qrosetta_cli.errors import Exit  # noqa: E402
from tests.unit.test_qrosetta_contracts import validate_envelope  # noqa: E402

CIRQ_TEXT = BELL + "// cirq\n"


@pytest.fixture(autouse=True)
def no_pause(monkeypatch):
    monkeypatch.setattr(waiting, "pause", lambda seconds: None)


@pytest.fixture
def env(tmp_path):
    return {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_CONFIG_HOME": str(tmp_path / "cfg"),
            "QROSETTA_RESULTS_DIR": str(tmp_path / "res")}


@pytest.fixture
def server(app_server, monkeypatch):
    import services.job_manager as job_manager
    transport, fleet = app_server
    dispatch = fleet.dispatch

    async def with_texts(*args, **kwargs):
        out = await dispatch(*args, **kwargs)
        for r in out:
            r["transpiled_qasm"] = CIRQ_TEXT if r["simulator"] == "cirq" else BELL
        return out

    monkeypatch.setattr(job_manager, "dispatch_to_runners", with_texts)
    return transport


@pytest.fixture
def job(server, env, tmp_path, capsys):
    path = tmp_path / "bell.qasm"
    path.write_text(BELL)
    assert main(["run", str(path), "--crate", "--json"], env=env, transport_factory=server) == 0
    entry = json.loads(capsys.readouterr().out)["data"]["jobs"][0]
    return entry


def cli(argv, env, transport, capsys):
    code = main(argv + ["--json"], env=env, transport_factory=transport)
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    return code, doc


def _expire(job_id):
    import services.job_manager as job_manager
    job_manager.ACTIVE_JOBS.pop(job_id)


def test_show_circuits_from_the_server_then_the_saved_file(server, env, job, capsys):
    code, doc = cli(["show", "circuits"], env, server, capsys)
    assert code == 0, doc
    data = doc["data"]
    assert data["source"] == "the server's job" and data["report_source"] == "server_job"
    panes = {p["id"]: p for p in data["circuits"][0]["panes"]}
    assert panes["input"]["text"] == BELL
    assert panes["executed:cirq"]["text"] == CIRQ_TEXT and panes["executed:qiskit"]["text"] == BELL
    assert any(k.startswith("dispatched:") for k in panes)
    saved = os.path.join(job["dir"], circuits.TEXTS_FILE)
    assert json.load(open(saved))["circuits"] == data["circuits"]
    sums = open(os.path.join(job["dir"], results.SUMS_FILE)).read()
    assert f"  {circuits.TEXTS_FILE}\n" in sums
    code, doc = cli(["show", "circuits"], env, server, capsys)
    assert doc["data"]["source"] == f"saved {circuits.TEXTS_FILE}"

    main(["show", "circuits", "--pane", "cirq"], env=env, transport_factory=server)
    out, err = capsys.readouterr()
    assert out == CIRQ_TEXT and "(job " in err


def test_show_diff(server, env, job, capsys):
    code, doc = cli(["show", "diff", "executed:qiskit", "cirq"], env, server, capsys)
    assert code == 0 and not doc["data"]["identical"]
    assert doc["data"]["diff"].splitlines()[:2] == ["--- executed:qiskit", "+++ executed:cirq"]
    assert "+// cirq" in doc["data"]["diff"]
    code, doc = cli(["show", "diff", "executed:qiskit", "cirq", "--ignore", "comments,whitespace"], env, server, capsys)
    assert doc["data"]["identical"] and doc["data"]["ignore"] == ["comments", "whitespace"]
    code, doc = cli(["show", "diff", "executed:cirq"], env, server, capsys)
    assert doc["data"]["a"].startswith("dispatched:") and doc["data"]["b"] == "executed:cirq"
    code, doc = cli(["show", "diff", "nonesuch"], env, server, capsys)
    assert code == Exit.USAGE and doc["error"]["reason"] == "pane_unknown"
    code, doc = cli(["show", "diff", "a", "b", "c"], env, server, capsys)
    assert code == Exit.USAGE


def test_views_artifacts_and_figures(server, env, job, tmp_path, capsys):
    code, doc = cli(["show", "views"], env, server, capsys)
    assert code == 0 and [v["id"] for v in doc["data"]["views"]][:2] == ["agreement_distribution", "agreement"]
    code, doc = cli(["export", "views"], env, server, capsys)
    path = doc["data"]["path"]
    assert path == os.path.join(env["QROSETTA_RESULTS_DIR"], figures.VIEWS_FILE)
    assert json.load(open(path))["views"]
    code, doc = cli(["show", "artifacts"], env, server, capsys)
    ids = [a["id"] for a in doc["data"]["artifacts"]]
    assert "fidelity_heatmap" in ids and "agreement" in ids

    code, doc = cli(["export", "figure", "fidelity_heatmap"], env, server, capsys)
    assert code == 0, doc
    figure = doc["data"]["path"]
    assert figure == os.path.join(job["dir"], "fidelity_heatmap.svg") and doc["data"]["report_source"] == "server_job"
    assert open(figure, "rb").read().lstrip().startswith((b"<?xml", b"<svg"))
    assert "  fidelity_heatmap.svg\n" in open(os.path.join(job["dir"], results.SUMS_FILE)).read()
    code, doc = cli(["export", "figure", "agreement", "-o", str(tmp_path / "a.csv")], env, server, capsys)
    assert doc["data"]["format"] == "csv" and open(tmp_path / "a.csv").read().startswith("Pair,Agreement")
    code, doc = cli(["export", "figure", "fidelity_heatmap", "--param", "title=false"], env, server, capsys)
    assert doc["data"]["path"].endswith("fidelity_heatmap_title-false.svg")
    code, doc = cli(["export", "figure", "fidelity_heatmap", "--param", "nonesuch=1"], env, server, capsys)
    assert code == Exit.REFUSED
    code, doc = cli(["export", "figure", "nonesuch"], env, server, capsys)
    assert code == Exit.NOT_FOUND
    code = main(["export", "figure", "agreement", "-o", "-"], env=env, transport_factory=server)
    assert code == Exit.USAGE


def test_after_the_job_expires(server, env, job, tmp_path, capsys):
    _expire(job["job_id"])
    code, doc = cli(["show", "circuits"], env, server, capsys)
    assert code == 0, doc
    assert doc["data"]["source"] == "saved ro-crate.zip" and doc["data"]["report_source"] == "server_job"
    panes = {p["id"]: p for p in doc["data"]["circuits"][0]["panes"]}
    assert panes["input"]["text"] == BELL and panes["executed:cirq"]["text"] == CIRQ_TEXT
    assert panes["dispatched:cirq"]["kind"] == "dispatched"
    code, doc = cli(["show", "diff", "cirq"], env, server, capsys)
    assert doc["data"]["a"] == "dispatched:cirq"
    code, doc = cli(["export", "figure", "agreement", "--format", "csv", "-o", str(tmp_path / "late.csv")],
                    env, server, capsys)
    assert code == 0 and doc["data"]["report_source"] == "client_supplied"
    code, doc = cli(["show", "artifacts"], env, server, capsys)
    assert code == 0 and doc["data"]["source"].startswith("client-supplied")
