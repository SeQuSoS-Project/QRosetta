"""The page's job link /#job=<id>: job_link.js reads the id (and nothing from other fragments,
such as share.html's token), the page opens it on load and on hashchange, and the link the
CLI prints after run, wait and selftest is one the page reads back to the same id."""

import re
from pathlib import Path

import pytest

from tests.unit._qrosetta_scripted import Scripted
from tests.unit.frontend_harness import NODE, call_js, requires_node

from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.client import waiting  # noqa: E402

JS = Path(__file__).resolve().parents[2] / "static" / "js"
JOB = "1a2b3c4d-5e6f-4a1b-9c2d-0123456789ab"
QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'


@requires_node
@pytest.mark.parametrize("hash_,expected", [
    (f"#job={JOB}", JOB),
    (f"#job={JOB.replace('-', '%2D')}", JOB),
    ("#job=abc", None),
    ("#job=../../etc", None),
    ("#job=%E0%A4%A", None),
    (f"#token-{JOB}", None),
    (JOB, None),
    ("", None),
    ("#job=", None),
])
def test_linked_job_id(hash_, expected):
    assert call_js(["job_link.js"], [("linkedJobId", [hash_])]) == [expected]


@requires_node
def test_kind_title_and_missing_text():
    calls = [("linkedJobKind", [None]),
             ("linkedJobKind", [{"status": "processing", "results": None, "progress": {"total": 3}}]),
             ("linkedJobKind", [{"results": {"experiment_summary": {}}}]),
             ("linkedJobKind", [{"results": {"benchmark_summary": []}}]),
             ("linkedJobKind", [{"results": {"raw_results": []}}]),
             ("linkedJobTitle", [{"results": {"run_name": "Bell"}}, JOB]),
             ("linkedJobTitle", [{"results": {"run_name": " ", "circuit_name": "ghz"}}, JOB]),
             ("linkedJobTitle", [None, JOB]),
             ("missingJobText", [JOB, "24 h"])]
    kinds = ["single", "batch", "experiment", "batch", "single"]
    out = call_js(["job_link.js"], calls)
    assert out[:5] == kinds
    assert out[5:8] == ["Bell", "ghz", "Job 1a2b3c4d"]
    assert "1a2b3c4d" in out[8] and "24 h" in out[8] and "qrosetta show summary --result job:1a2b3c4d" in out[8]


def test_the_page_opens_the_link_and_share_page_keeps_its_own_fragment():
    app = (JS / "app.js").read_text()
    assert "openLinkedJob();" in app and "addEventListener('hashchange'" in app
    assert "job_link.js" not in (JS / "share_main.js").read_text()
    workspace = (JS / "workspace.js").read_text()
    body = workspace[workspace.index("export async function openLinkedJob"):]
    body = body[:body.index("\n}\n")]
    assert "recordJob" not in body and "saveRunToHistory" not in body
    assert re.search(r"if \(job\.linked\) job\.kind = linkedJobKind", workspace)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(waiting, "pause", lambda seconds: None)
    return {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_CONFIG_HOME": str(tmp_path / "cfg"),
            "XDG_RUNTIME_DIR": str(tmp_path / "run"), "QROSETTA_RESULTS_DIR": str(tmp_path / "res")}


@pytest.mark.parametrize("features,printed", [({"job_link": 1}, True), ({}, False)])
def test_cli_prints_the_link_when_the_page_opens_it(env, tmp_path, capsys, features, printed):
    circuit = tmp_path / "bell.qasm"
    circuit.write_text(QASM)
    server = Scripted(features=features)
    assert main(["run", str(circuit)], env=env, transport_factory=server) == 0
    out = capsys.readouterr().out
    links = re.findall(r"^Open in the browser: (\S+)$", out, re.M)
    if not printed:
        assert links == []
        return
    (job_id,) = server.jobs
    assert links == [f"http://localhost:8080/#job={job_id}"]
    if NODE:
        assert call_js(["job_link.js"], [("linkedJobId", ["#" + links[0].split("#", 1)[1]])]) == [job_id]
