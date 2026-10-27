"""Specimens: which image each backend ran from, the report roll-up, the runner image the
report names, and the crate's runner lock files admitted only by a matching hash."""
import hashlib
import io
import json
import zipfile
from types import SimpleNamespace

import pytest

import services.exporter as exporter
from services import specimens
from services.exporter import build_export_context, build_ro_crate, crate_name, runner_lock_files

SERVICES = {"qiskit": {"base_url": "http://pytket-qiskit-runner:8000"},
            "cirq": {"base_url": "http://pytket-cirq-runner:8000"}}
LOCK = b"qiskit==1.2.4\n"
LOCK_SHA = hashlib.sha256(LOCK).hexdigest()


def _ran(sim, source="built_locally", release="", sha="abc1234", **extra):
    return {"simulator": sim, "image_git_sha": sha, "sdk_versions": {},
            "image_identity": {"source": source, "release": release or None, "git_sha": sha,
                               "container": {"engine": "podman"}},
            **extra}


def test_runner_image_prefers_the_job_image_then_the_self_report():
    k8s = "registry/pytket-qiskit-runner@sha256:" + "a" * 64
    assert specimens.runner_image_record(k8s, _ran("qiskit")) == (k8s, "dispatch")
    local = "not recorded (HTTP dispatch to a Compose service exposes no image id)"
    assert specimens.runner_image_record(local, _ran("qiskit")) == (local, "not recorded")
    apptainer = _ran("qiskit")
    apptainer["image_identity"]["container"] = {"engine": "apptainer", "image": "/s/q.sif",
                                                "image_sha256": "f" * 64}
    assert specimens.runner_image_record(local, apptainer) == ("/s/q.sif@" + "f" * 64,
                                                               "runner_self_report")


@pytest.mark.parametrize("results,statement", [
    ([_ran("qiskit", "release", "1.2.0"), _ran("cirq", "release", "1.2.0")], "all_published"),
    ([_ran("qiskit", "release", "1.2.0"), _ran("cirq", "release", "1.3.0")], "mixed"),
    ([_ran("qiskit"), _ran("cirq")], "all_built_locally"),
    ([_ran("qiskit", "release", "1.2.0"), _ran("cirq")], "mixed"),
    ([_ran("qiskit", "not recorded"), {"simulator": "cirq", "image_git_sha": "x", "sdk_versions": {}}],
     "unknown"),
    ([_ran("qiskit"), {"simulator": "cirq", "image_git_sha": "x"}], "mixed"),
    ([{"simulator": "qiskit", "error": "UNAVAILABLE", "dispatch_status": "offline"}], "none_ran"),
])
def test_statement(results, statement):
    report = {"raw_results": results}
    specimens.annotate(report)
    assert report["specimens"]["statement"] == statement
    assert report["specimens"]["meaning"] == specimens.STATEMENTS[statement]


def test_roll_up_details_commits_and_results_that_did_not_run():
    report = {"raw_results": [_ran("qiskit", sha="abc1234-dirty"), _ran("cirq", sha="def5678"),
                              {"simulator": "qulacs", "error": "TIMEOUT", "dispatch_status": "timeout"},
                              {"simulator": "quest", "never_started": True, **_ran("quest")}],
              "compiled_circuits": [{"compiler": "staq~opt1~run1", **_ran("staq")}]}
    specimens.annotate(report)
    rec = report["specimens"]
    assert set(rec["backends"]) == {"qiskit", "cirq", "staq~opt1~run1"}
    assert rec["no_result"] == ["qulacs", "quest"]
    assert rec["image_git_shas"] == ["abc1234", "abc1234-dirty", "def5678"]
    assert any("different commits" in n for n in rec["notes"])
    assert any("Source not identifiable for qiskit" in n for n in rec["notes"])
    assert report["raw_results"][0]["specimen"]["kind"] == "built_locally"
    assert "specimen" not in report["raw_results"][2]


def test_combine_over_tasks_marks_a_backend_whose_image_varies():
    a, b = {"raw_results": [_ran("qiskit", sha="aaa1111")]}, {"raw_results": [_ran("qiskit", sha="bbb2222")]}
    specimens.annotate(a)
    specimens.annotate(b)
    rec = specimens.combine([a["specimens"], b["specimens"], None])
    assert rec["statement"] == "all_built_locally"
    assert len(rec["backends"]["qiskit"]["varies"]) == 2


@pytest.fixture
def lock_on_server(monkeypatch):
    monkeypatch.setattr(exporter, "_read_runner_lock", lambda name: LOCK if "qiskit" in name else None)


def test_lock_file_included_only_on_a_matching_hash(lock_on_server):
    files, notes = runner_lock_files([_ran("qiskit", build_files={"requirements.lock": LOCK_SHA})], SERVICES)
    assert files == {"runners/pytket-qiskit-runner/requirements.lock": LOCK} and notes == {}

    files, notes = runner_lock_files([_ran("qiskit", build_files={"requirements.lock": "0" * 64})], SERVICES)
    path = "runners/pytket-qiskit-runner/requirements.lock"
    assert files == {} and notes[path].startswith("not included: the image reports requirements.lock sha256 000")
    assert LOCK_SHA in notes[path] and "abc1234" in notes[path]

    files, notes = runner_lock_files([_ran("qiskit")], SERVICES)
    assert files == {} and notes[path] == exporter.LOCK_NOT_REPORTED

    mixed = [_ran("qiskit", build_files={"requirements.lock": LOCK_SHA}), _ran("qiskit")]
    assert runner_lock_files(mixed, SERVICES)[0] == {}

    files, notes = runner_lock_files([{"simulator": "qiskit", "error": "x", "dispatch_status": "offline"}], SERVICES)
    assert files == {} and notes[path] == exporter.LOCK_NO_RESULT

    files, notes = runner_lock_files([_ran("cirq", build_files={"requirements.lock": LOCK_SHA})], SERVICES)
    assert notes["runners/pytket-cirq-runner/requirements.lock"] == exporter.LOCK_NOT_ON_SERVER


def _payload():
    return SimpleNamespace(include_statevectors=False, author_name=None, author_affiliation=None,
                           publication_artifacts=None, name=None, circuit_name=None)


def _crate(report, route):
    ctx = build_export_context(report, _payload(), route)
    zf = zipfile.ZipFile(io.BytesIO(build_ro_crate(ctx)))
    top = crate_name(ctx)
    files = {n[len(top) + 1:]: zf.read(n) for n in zf.namelist()}
    graph = {e["@id"]: e for e in json.loads(files["ro-crate-metadata.json"])["@graph"]}
    return files, graph, json.loads(files["provenance.json"])


QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\nh q[0];\n'


def test_crate_states_specimens_and_why_a_lock_is_absent(lock_on_server):
    report = {"input_qasm": QASM, "raw_results": [
        _ran("qiskit", statevector=[1, 0], build_files={"requirements.lock": "0" * 64})]}
    specimens.annotate(report)
    files, graph, prov = _crate(report, "server_job")
    assert graph["#specimens"]["value"] == "all_built_locally"
    assert {"@id": "#specimens"} in graph["./"]["additionalProperty"]
    assert "qiskit: built_locally (commit abc1234)" in graph["#specimens"]["description"]
    assert "runners/pytket-qiskit-runner/requirements.lock" not in files
    assert "not included: the image reports requirements.lock sha256" in graph["#qiskit"]["description"]
    assert prov["specimens"]["statement"] == "all_built_locally"
    assert prov["runner_lock_files"]["runners/pytket-qiskit-runner/requirements.lock"].startswith("not included")
    assert prov["runner_configurations"]["qiskit"]["image_identity"]["source"] == "built_locally"


def test_crate_of_a_supplied_report_marks_specimens_as_supplied(lock_on_server):
    report = {"input_qasm": QASM, "raw_results": [_ran("qiskit", "release", "1.2.0", statevector=[1, 0])]}
    _, graph, prov = _crate(report, "client_request")
    assert graph["#specimens"]["value"] == "all_published"
    assert "As supplied in the report" in graph["#specimens"]["description"]
    assert "runner_lock_files" not in prov
