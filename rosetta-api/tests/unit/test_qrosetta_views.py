"""qrosetta show circuits, show diff, show views, export views and export figure against a scripted
server (no server dependencies): --save circuits and the offline read of the saved file, the
panes of a saved playlist crate, pane names, the diff's ignore rules, figure file names and
formats, and the fallback to the saved report once the job has expired."""

import json
import os
import zipfile

import pytest

from tests.unit._qrosetta_scripted import Scripted, _json

from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.client import circuits, figures, waiting  # noqa: E402
from qrosetta_cli.client.transport import Response  # noqa: E402
from qrosetta_cli.errors import CliError, Exit  # noqa: E402
from tests.unit.test_qrosetta_contracts import validate_envelope  # noqa: E402

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'
OTHER = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh  q[0]; // spaced\ncx q[0],q[1];\n'
PANES = [{"id": "input", "kind": "input", "key": None, "group": None, "text": QASM},
         {"id": "dispatched:default", "kind": "dispatched", "key": None, "group": "default", "text": QASM},
         {"id": "executed:qiskit", "kind": "executed", "key": "qiskit", "group": "default", "text": QASM,
          "gate_count": 2, "dispatch_status": "ok"},
         {"id": "executed:cirq", "kind": "executed", "key": "cirq", "group": "default", "text": OTHER},
         {"id": "compiled:staq~opt1~run1", "kind": "compiled", "key": "staq~opt1~run1", "group": None, "text": None,
          "refusal_kind": "input"}]


@pytest.fixture(autouse=True)
def no_pause(monkeypatch):
    monkeypatch.setattr(waiting, "pause", lambda seconds: None)


@pytest.fixture
def env(tmp_path):
    return {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_CONFIG_HOME": str(tmp_path / "cfg"),
            "XDG_RUNTIME_DIR": str(tmp_path / "run"), "QROSETTA_RESULTS_DIR": str(tmp_path / "res")}


@pytest.fixture
def circuit(tmp_path):
    path = tmp_path / "bell.qasm"
    path.write_text(QASM)
    return str(path)


def cli(argv, env, server, capsys):
    code = main(argv + ["--json"], env=env, transport_factory=server)
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    return code, doc


class TextsServer(Scripted):
    def request(self, method, path, query=None, body=None, headers=None, timeout=None):
        if path.endswith("/circuit-texts") and path.split("/")[2] in self.jobs:
            self.log.append((method, path, query))
            return _json(200, {"job_id": path.split("/")[2], "report_source": "server_job",
                               "circuits": [{"task": None, "task_name": None, "panes": PANES}]})
        return super().request(method, path, query, body, headers, timeout)


def _job_dir(doc):
    return doc["data"]["jobs"][0]["dir"]


def test_save_circuits_and_read_them_offline(env, circuit, capsys):
    server = TextsServer(features={"circuit_texts": 1})
    code, doc = cli(["run", circuit, "--save", "report,summary,circuits"], env, server, capsys)
    assert code == 0 and os.path.isfile(os.path.join(_job_dir(doc), circuits.TEXTS_FILE))
    before = len(server.log)
    code, doc = cli(["show", "circuits"], env, server, capsys)
    assert code == 0 and doc["data"]["source"] == f"saved {circuits.TEXTS_FILE}"
    assert not any(p.endswith("/circuit-texts") for _, p, _ in server.log[before:])
    code, doc = cli(["show", "diff"], env, server, capsys)
    assert (doc["data"]["a"], doc["data"]["b"]) == ("input", "dispatched:default") and doc["data"]["identical"]
    code, doc = cli(["show", "diff", "qiskit", "cirq", "--ignore", "comments,whitespace"], env, server, capsys)
    assert doc["data"]["identical"]
    code, doc = cli(["show", "diff", "qiskit", "cirq", "--ignore", "case"], env, server, capsys)
    assert code == Exit.USAGE and doc["error"]["reason"] == "ignore_unknown"
    code, doc = cli(["show", "diff", "staq~opt1~run1"], env, server, capsys)
    assert code == Exit.NOT_FOUND and doc["error"]["reason"] == "pane_without_text"


def test_show_circuits_from_the_server_needs_the_feature(env, circuit, capsys):
    server = TextsServer()
    cli(["run", circuit], env, server, capsys)
    code, doc = cli(["show", "circuits"], env, server, capsys)
    assert code == Exit.INCOMPATIBLE and doc["error"]["reason"] == "feature_missing"
    server = TextsServer(features={"circuit_texts": 1})
    cli(["run", circuit], env, server, capsys)
    code, doc = cli(["show", "circuits"], env, server, capsys)
    assert code == 0 and doc["data"]["source"] == "the server's job"


def _playlist_crate(path):
    files = {"circuits/bell.qasm": QASM, "circuits/ghz.qasm": OTHER,
             "dispatched_circuits/bell/qiskit.qasm": QASM, "transpiled_circuits/bell/qiskit.qasm": QASM,
             "dispatched_circuits/ghz/qiskit.qasm": OTHER, "transpiled_circuits/ghz/qiskit.qasm": OTHER,
             "compile_inputs/ghz.qasm": OTHER, "compiled_circuits/ghz/staq~opt1~run1.qasm": QASM}
    meta = {"@graph": [{"@id": "./", "hasPart": [{"@id": "README.txt"}] + [{"@id": p} for p in files]},
                       {"@id": "#report-source", "value": "client_supplied"}]}
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("top/ro-crate-metadata.json", json.dumps(meta))
        for p, text in files.items():
            zf.writestr(f"top/{p}", text)


def test_crate_panes_of_a_playlist(tmp_path):
    path = tmp_path / "c.zip"
    _playlist_crate(path)
    texts = circuits.crate_texts(str(path))
    assert texts["report_source"] == "client_supplied"
    bell, ghz = texts["circuits"]
    assert (bell["task"], bell["task_name"], ghz["task"]) == (0, "bell", 1)
    assert [p["id"] for p in bell["panes"]] == ["input", "dispatched:qiskit", "executed:qiskit"]
    assert [p["id"] for p in ghz["panes"]] == ["input", "dispatched:qiskit", "executed:qiskit", "compile-input",
                                               "compiled:staq~opt1~run1"]
    assert circuits.source_pane(ghz["panes"][-1], ghz["panes"])["id"] == "compile-input"
    assert circuits.source_pane(ghz["panes"][2], ghz["panes"])["id"] == "dispatched:qiskit"
    assert circuits.find_pane(ghz["panes"], "qiskit")["id"] == "executed:qiskit"
    with pytest.raises(CliError) as err:
        circuits.select(texts, None, need_one=True)
    assert err.value.reason == "bad_task"
    assert circuits.select(texts, 1, need_one=True) == [ghz]


def test_ignore_rules():
    assert circuits.lines_of(OTHER, ["header", "comments", "whitespace"]) == ["qreg q[2];", "h q[0];", "cx q[0],q[1];"]
    assert circuits.lines_of(OTHER, []) == OTHER.splitlines()


def test_figure_names_and_formats(env, circuit, tmp_path, capsys):
    assert figures.file_name("counts_overview", {"layout": "panels", "top": 8}, "pdf") == \
        "counts_overview_layout-panels_top-8.pdf"
    assert figures.file_name("glossary", {}, "markdown") == "glossary.md"
    server = Scripted()
    cli(["run", circuit], env, server, capsys)
    code, doc = cli(["export", "figure", "agreement", "-o", "-"], env, server, capsys)
    assert code == Exit.USAGE and doc["error"]["reason"] == "format_missing"
    code, doc = cli(["show", "views"], env, server, capsys)
    assert code == Exit.INCOMPATIBLE
    code, doc = cli(["export", "views"], env, server, capsys)
    assert code == Exit.INCOMPATIBLE


def test_export_figure_and_the_expired_fallback(env, circuit, tmp_path, capsys):
    server = Scripted(features={"publication_views": 1})
    cli(["run", circuit], env, server, capsys)
    (job_id,) = server.jobs
    rendered = []

    def render(payload, query):
        rendered.append(payload)
        return Response(200, {"content-type": "text/csv"}, b"Pair,Agreement\n")

    views = {"views": [{"id": "agreement", "artifacts": [{"artifact_id": "agreement", "kind": "table",
                                                          "formats": ["latex", "csv"]}], "params": []}]}
    server.routes[("GET", "/publication/views")] = (200, views)
    server.routes[("POST", f"/jobs/{job_id}/publication/render")] = render
    code, doc = cli(["export", "figure", "agreement", "--param", "backends=[\"qiskit\"]"], env, server, capsys)
    assert code == 0, doc
    assert rendered[-1] == {"artifact_id": "agreement", "format": "latex", "scale": 1, "params": {"backends": ["qiskit"]}}
    assert doc["data"]["path"].endswith("agreement_backends-qiskit.tex")
    code, doc = cli(["export", "views", "-o", str(tmp_path / "v.json")], env, server, capsys)
    assert json.load(open(tmp_path / "v.json")) == views

    del server.routes[("POST", f"/jobs/{job_id}/publication/render")]
    del server.jobs[job_id]
    supplied = []

    def render_supplied(payload, query):
        supplied.append(payload)
        return Response(200, {"content-type": "text/csv"}, b"Pair,Agreement\n")

    server.routes[("POST", "/publication/render")] = render_supplied
    code, doc = cli(["export", "figure", "agreement", "-o", str(tmp_path / "late.csv")], env, server, capsys)
    assert code == 0 and doc["data"]["report_source"] == "client_supplied"
    report_path = os.path.join(os.path.dirname(doc["data"]["path"]), "late.csv")
    assert open(report_path).read() == "Pair,Agreement\n"
    assert supplied[0]["results"]["report"] is True and supplied[0]["format"] == "csv"
