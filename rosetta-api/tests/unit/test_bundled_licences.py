"""A crate or experiment bundle that carries a bundled MQT Bench or QASMBench circuit carries that suite's
licence text, and the circuit's File entity names it; circuits a user wrote get none; the recorded
origins agree with THIRD_PARTY_NOTICES.md and the suites' SOURCE.md."""

import asyncio
import io
import json
import zipfile

import pytest

from services.bundled_licences import BUNDLED, bundled_source, licence_files
from services.exporter import ExportContext, build_ro_crate
from tests.unit._qrosetta_fake import REPO

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'


def _task(name, request):
    return {"task_name": name, "input_qasm": QASM, "task_request": request,
            "raw_results": [{"simulator": "qiskit", "execution_time_sec": 0.1}]}


def _crate(tasks):
    ctx = ExportContext(qasm_string="", results={"mode": "statevector", "benchmark_summary": tasks},
                        mode="statevector", runner_services={}, include_statevectors=False,
                        report_source="server_job")
    zf = zipfile.ZipFile(io.BytesIO(build_ro_crate(ctx)))
    top = zf.namelist()[0].split("/", 1)[0]
    files = {n[len(top) + 1:]: zf.read(n) for n in zf.namelist()}
    meta = json.loads(files["ro-crate-metadata.json"])
    return files, {e["@id"]: e for e in meta["@graph"]}


@pytest.mark.parametrize("request_,expected", [
    ({"source": "qasmbench", "algorithm": "adder_n4", "literal_qasm": False}, "qasmbench"),
    ({"source": "mqt", "algorithm": "dj", "qubits": 4, "literal_qasm": False}, "mqt"),
    ({"source": "qasm", "literal_qasm": True}, None),
    ({"source": "qasmbench", "literal_qasm": True}, None),
    ({"source": "preset", "algorithm": "ghz"}, None),
    (None, None), ("qasmbench", None),
])
def test_bundled_source_names_only_bundled_circuits(request_, expected):
    assert bundled_source(request_) == expected


def test_a_crate_carries_the_licence_of_each_bundled_suite_it_contains():
    files, graph = _crate([
        _task("adder (4q) [QASMBench]", {"source": "qasmbench", "algorithm": "adder_n4", "literal_qasm": False}),
        _task("dj (4q) [MQT Bench]", {"source": "mqt", "algorithm": "dj", "qubits": 4, "literal_qasm": False}),
        _task("mine (2q)", {"source": "qasm", "literal_qasm": True}),
    ])
    for source in ("qasmbench", "mqt"):
        path = BUNDLED[source]["path"]
        assert files[path] == BUNDLED[source]["source_file"].read_bytes()
        assert {"@id": path} in graph["./"]["hasPart"]
        assert graph[path]["sha256"] and graph[path]["contentSize"] == str(len(files[path]))
    qasmbench = graph["circuits/adder-4q-qasmbench.qasm"]
    assert qasmbench["license"] == {"@id": BUNDLED["qasmbench"]["path"]}
    assert "357b942396d5c2b7cbc1c229c585a6ef5ccaebac" in qasmbench["description"]
    assert graph["circuits/dj-4q-mqt-bench.qasm"]["license"] == {"@id": BUNDLED["mqt"]["path"]}
    assert "license" not in graph["circuits/mine-2q.qasm"]
    assert graph["./"]["license"] == {"@id": "#license"}


def test_a_crate_without_bundled_circuits_has_no_licence_files():
    files, graph = _crate([_task("mine (2q)", {"source": "qasm", "literal_qasm": True})])
    assert not any(p.startswith("licenses/") for p in files)
    assert not any(str(i).startswith("licenses/") for i in graph)


def test_licence_files_are_written_once_per_suite():
    assert list(licence_files(["qasmbench", None, "qasmbench", "preset"])) == [BUNDLED["qasmbench"]["path"]]
    assert licence_files([]) == {}


def test_recorded_origins_agree_with_the_notices_and_the_suites_source_files():
    notices = (REPO / "THIRD_PARTY_NOTICES.md").read_text()
    assert "357b942396d5c2b7cbc1c229c585a6ef5ccaebac" in BUNDLED["qasmbench"]["origin"]
    assert "357b942396d5c2b7cbc1c229c585a6ef5ccaebac" in notices
    assert "357b942396d5c2b7cbc1c229c585a6ef5ccaebac" in (
        REPO / "rosetta-api/benchmarks/qasmbench/SOURCE.md").read_text()
    assert "mqt.bench 1.1.9" in BUNDLED["mqt"]["origin"] and "`mqt.bench` 1.1.9" in notices
    assert "`mqt.bench` 1.1.9" in (REPO / "rosetta-api/benchmarks/mqtbench/SOURCE.md").read_text()
    assert BUNDLED["mqt"]["source_file"].read_text().startswith("MIT License")
    assert "Battelle Memorial Institute" in BUNDLED["qasmbench"]["source_file"].read_text()


def test_an_experiment_bundle_carries_the_licence_of_its_bundled_circuits(monkeypatch):
    pytest.importorskip("pytket")
    pytest.importorskip("kubernetes")
    import services.experiment as exp
    from schemas import ExperimentCircuit, ExperimentPayload
    from services.job_manager import ACTIVE_JOBS

    async def fake_run_batch_tasks(payload, runner_statuses, progress=None, batch_seed=None,
                                   task_offset=0, store=None):
        summary = [{"task_name": t.name or t.algorithm, "raw_results": [{"simulator": "qiskit"}]}
                   for t in payload.tasks]
        if store is not None:
            summary = [await store(i, r) for i, r in enumerate(summary)]
        return summary, batch_seed

    monkeypatch.setattr(exp, "run_batch_tasks", fake_run_batch_tasks)
    payload = ExperimentPayload(circuits=[ExperimentCircuit(source="qasmbench", algorithm="adder_n4", qubits=4),
                                          ExperimentCircuit(source="qasm", qasm_string=QASM, name="mine", qubits=2)],
                                mode="statevector", preprocessing_modes=[True], label="lic")
    ACTIVE_JOBS["lic-job"] = {"status": "pending", "target": payload.execution_target}
    asyncio.run(exp.worker_experiment("lic-job", payload))
    job = ACTIVE_JOBS["lic-job"]
    assert job["status"] == "completed", job
    with zipfile.ZipFile(job["bundle_path"]) as zf:
        names = {n.split("/", 1)[1]: n for n in zf.namelist()}
        assert zf.read(names[BUNDLED["qasmbench"]["path"]]) == BUNDLED["qasmbench"]["source_file"].read_bytes()
        assert BUNDLED["mqt"]["path"] not in names
        assert "licenses/" in zf.read(names["README.txt"]).decode()
    ACTIVE_JOBS.pop("lic-job", None)
