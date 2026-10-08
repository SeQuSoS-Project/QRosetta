"""RO-Crates of reports the server did not produce (client-supplied, uploaded, legacy saved
runs) state that in ro-crate-metadata.json and results.json, and carry no server lock files
or commit links for them; every crate file has a sha256 and size."""

import hashlib
import io
import json
import zipfile
from types import SimpleNamespace

import pytest

from config import settings
from services.exporter import build_export_context, build_ro_crate, crate_name

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\nh q[0];\ncx q[0],q[1];\n'


def _report(**extra):
    return {
        "input_qasm": QASM, "git_sha": "abcdef1", "platform_version": "9.9.9",
        "report_source": "server_job", "job_id": "genuine-job",
        "raw_results": [
            {"simulator": "qiskit", "statevector": [1, 0, 0, 0], "sdk_versions": {"qiskit": "9.9.9"},
             "transpiled_qasm": QASM},
            {"simulator": "cirq", "error": "boom"},
        ],
        "divergence_report": {"pairwise_agreement": [], "agreement_thresholds": {
            "fidelity_tolerance": 1e-5, "phase_tolerance": 1e-6, "norm_tolerance": 1e-4}},
        **extra,
    }


def _payload(**kw):
    base = dict(include_statevectors=False, author_name=None, author_affiliation=None,
                publication_artifacts=None, name=None, circuit_name=None)
    base.update(kw)
    return SimpleNamespace(**base)


def _crate(report, route, payload=None):
    ctx = build_export_context(report, payload or _payload(), route)
    zf = zipfile.ZipFile(io.BytesIO(build_ro_crate(ctx)))
    top = crate_name(ctx)
    files = {n[len(top) + 1:]: zf.read(n) for n in zf.namelist()}
    meta = json.loads(files["ro-crate-metadata.json"])
    return files, {e["@id"]: e for e in meta["@graph"]}


@pytest.fixture
def runner_lock(monkeypatch):
    import services.exporter as exporter
    monkeypatch.setattr(exporter, "_read_runner_lock", lambda name: b"qiskit==1.2.4\n")


@pytest.mark.parametrize("route,source", [("client_request", "client_supplied"),
                                          ("saved_run", "not_recorded")])
def test_an_untrusted_report_is_labelled_as_supplied(route, source, runner_lock):
    files, graph = _crate(_report(), route)
    assert graph["#report-source"]["value"] == source
    assert {"@id": "#report-source"} in graph["./"]["additionalProperty"]
    assert {"@id": "#report-source"} in graph["#agreement-analysis"]["additionalProperty"]
    for action in ("#run-qiskit", "#run-cirq"):
        assert "actionStatus" not in graph[action]
        assert "as supplied" in graph[action]["description"].lower()
    qiskit = graph["#qiskit"]
    assert "softwareVersion" not in qiskit and "softwareRequirements" not in qiskit and "url" not in qiskit
    assert "9.9.9" in qiskit["description"] and "not checked" in qiskit["description"]
    platform = graph["#quantum-rosetta"]
    assert "softwareVersion" not in platform
    assert platform["url"] == settings.REPOSITORY_URL
    assert "abcdef1" not in platform["url"]
    assert not any(p.startswith("runners/") for p in files)
    assert json.loads(files["results.json"])["report_source"] == source


def test_an_uploaded_saved_run_is_labelled_upload(runner_lock):
    files, graph = _crate(_report(saved_from="upload"), "saved_run")
    assert graph["#report-source"]["value"] == "upload"
    assert json.loads(files["results.json"])["report_source"] == "upload"


def test_the_servers_own_job_keeps_status_versions_locks_and_commit_links(runner_lock, monkeypatch):
    monkeypatch.setattr(settings, "REPOSITORY_URL", "https://example.org/repo")
    files, graph = _crate(_report(), "server_job")
    assert graph["#run-qiskit"]["actionStatus"] == "http://schema.org/CompletedActionStatus"
    assert graph["#run-cirq"]["actionStatus"] == "http://schema.org/FailedActionStatus"
    assert graph["#qiskit"]["softwareVersion"] == "qiskit 9.9.9"
    assert graph["#quantum-rosetta"]["url"] == "https://example.org/repo/commit/abcdef1"
    assert "resolve only when that commit has been published" in graph["#quantum-rosetta"]["description"]
    assert any(p.startswith("runners/") for p in files)
    assert json.loads(files["results.json"])["report_source"] == "server_job"


def test_a_dirty_commit_gets_no_commit_link(monkeypatch):
    monkeypatch.setattr(settings, "REPOSITORY_URL", "https://example.org/repo")
    _, graph = _crate(_report(git_sha="abcdef1-dirty"), "server_job")
    assert graph["#quantum-rosetta"]["url"] == "https://example.org/repo"
    assert "names no published commit" in graph["#quantum-rosetta"]["description"]


def test_every_file_entity_has_its_sha256_and_size(runner_lock):
    files, graph = _crate(_report(), "server_job")
    file_entities = [e for e in graph.values() if e.get("@type") == "File"]
    assert {e["@id"] for e in file_entities} >= {"circuit.qasm", "results.json", "provenance.json",
                                                   "transpiled_circuits/qiskit.qasm"}
    for entity in file_entities:
        data = files[entity["@id"]]
        assert entity["sha256"] == hashlib.sha256(data).hexdigest()
        assert entity["contentSize"] == str(len(data))


def test_agreement_thresholds_are_parameters_of_the_analysis():
    measured = _report(n_shots=100, mode="measured")
    measured["divergence_report"]["agreement_thresholds"] = {
        "js_threshold": 0.01, "hellinger_threshold": 0.1, "stat_test_alpha": 0.05,
        "stat_test_target_power": 0.8, "stat_test_delta_tv": 0.05}
    _, graph = _crate(measured, "server_job")
    refs = {r["@id"] for r in graph["#agreement-analysis"]["object"]}
    for key, value in (("stat_test_alpha", 0.05), ("stat_test_target_power", 0.8),
                       ("stat_test_delta_tv", 0.05), ("js_threshold", 0.01)):
        assert f"#param-analysis-{key}" in refs
        assert graph[f"#param-analysis-{key}"]["value"] == value


def test_results_keep_one_statevector_length_field():
    report = _report()
    report["raw_results"].append({"simulator": "qulacs", "statevector_sha256": "ab" * 32,
                                  "statevector_len": 4})
    files, _ = _crate(report, "server_job")
    for r in json.loads(files["results.json"])["raw_results"]:
        assert "statevector_len" not in r
    assert json.loads(files["results.json"])["raw_results"][2]["statevector_length"] == 4


@pytest.mark.parametrize("name,expected", [("Café GHZ", "rosetta-export-cafe-ghz-"),
                                           ("\U0001F680\U0001F680", "rosetta-export-statevector-2q-")])
def test_crate_name_uses_the_requested_name_with_a_fallback(name, expected):
    ctx = build_export_context(_report(), _payload(name=name), "server_job")
    assert crate_name(ctx).startswith(expected)


def test_figures_in_a_crate_take_the_requested_circuit_name():
    report = _report(n_shots=100, mode="measured")
    report["raw_results"] = [{"simulator": "qiskit", "counts": {"00": 50, "11": 50}},
                             {"simulator": "cirq", "counts": {"00": 48, "11": 52}}]
    payload = _payload(circuit_name="Bell State (Simple) (2q)", publication_artifacts=SimpleNamespace(
        model_dump=lambda: {"items": [{"view": "counts", "params": {}, "formats": ["svg"]}]}))
    files, _ = _crate(report, "server_job", payload)
    svg = next(data for path, data in files.items() if path.endswith(".svg"))
    assert b"Bell State (Simple) (2q)" in svg and b"unnamed circuit" not in svg


class _Db:
    def add(self, row): pass
    def commit(self): pass
    def refresh(self, row): pass
    def rollback(self): pass


def test_an_uploaded_run_keeps_its_job_id_only_as_source_job_id(monkeypatch):
    from services.history import save_run
    stored = {}
    monkeypatch.setattr("services.history.save_run_report",
                        lambda user_id, run_id, payload: stored.update(payload) or "key")
    report = {"raw_results": [], "job_id": "job-123"}
    save_run(_Db(), 1, dict(report))
    assert "job_id" not in stored and stored["source_job_id"] == "job-123"
    stored.clear()
    save_run(_Db(), 1, dict(report), saved_from="server_job")
    assert stored["job_id"] == "job-123" and "source_job_id" not in stored
