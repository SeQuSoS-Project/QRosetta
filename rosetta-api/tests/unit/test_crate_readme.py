"""README.txt in every RO-Crate: listed in ro-crate-metadata.json with its hash and size, written
from the crate's own metadata (report source, completeness, specimens, timing caveats, files,
software), the same for the same export, and its hash-check command works on the extracted
crate."""

import hashlib
import io
import json
import subprocess
import sys
import zipfile

import pytest

from schemas import ExportPayload
from services.export_readme import CHECK_COMMAND, LISTED_PER_FOLDER, README_PATH
from services.exporter import build_export_context, build_ro_crate

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\nh q[0];\ncx q[0],q[1];\n'


def _result(sim, **extra):
    return {"simulator": sim, "dispatch_status": "ok", "transpiled_qasm": QASM, "qubit_ordering": "lsb",
            "execution_time_sec": 0.1, "compilation_time_sec": 0.02, "simulation_time_sec": 0.08, **extra}


def _report(sims=("qiskit", "cirq")):
    return {"input_qasm": QASM, "git_sha": "abc1234", "platform_version": "9.8.7",
            "raw_results": [_result(s) for s in sims],
            "dispatched_circuits": [{"group": "default", "qasm": QASM, "runners": list(sims),
                                     "api_preprocessing_applied": []}],
            "divergence_report": {"simulators": list(sims), "pairwise_agreement": []}}


def _crate(report, route="server_job", ctx_hook=None):
    ctx = build_export_context(report, ExportPayload(), route)
    ctx.timestamp = "2026-10-27T10:00:00.000+00:00"
    if ctx_hook:
        ctx_hook(ctx)
    return zipfile.ZipFile(io.BytesIO(build_ro_crate(ctx)))


def _parts(zf):
    meta_name = next(n for n in zf.namelist() if n.endswith("/ro-crate-metadata.json"))
    top = meta_name.split("/", 1)[0]
    meta = json.loads(zf.read(meta_name))
    return top, meta, zf.read(f"{top}/{README_PATH}").decode("utf-8")


def _nodes(meta):
    return {e["@id"]: e for e in meta["@graph"]}


@pytest.mark.parametrize("route", ["server_job", "saved_run", "client_request"])
def test_every_crate_has_a_readme_listed_with_hash_and_size(route):
    zf = _crate(_report(), route)
    top, meta, readme = _parts(zf)
    nodes = _nodes(meta)
    entity = nodes[README_PATH]
    data = zf.read(f"{top}/{README_PATH}")
    assert entity["@type"] == "File" and entity["encodingFormat"] == "text/plain"
    assert entity["sha256"] == hashlib.sha256(data).hexdigest()
    assert entity["contentSize"] == str(len(data))
    assert nodes["./"]["hasPart"][0] == {"@id": README_PATH}
    assert zf.namelist()[1] == f"{top}/{README_PATH}"


def test_readme_states_what_the_metadata_states():
    _, meta, readme = _parts(_crate(_report()))
    nodes = _nodes(meta)
    flat = " ".join(readme.split())
    for node_id in ("#report-source", "#run-completeness", "#specimens", "#timing-caveats"):
        assert f": {nodes[node_id]['value']}" in flat
        assert " ".join(nodes[node_id]["description"].split()) in flat
    files = [e["@id"] for e in meta["@graph"] if e.get("@type") == "File"]
    for path in files:
        if "/" in path:
            folder, name = path.split("/", 1)
            assert f"{folder}/ (" in flat and name in flat
        else:
            assert path in readme
    assert "2 backend executions" in flat
    assert "Quantum Rosetta 9.8.7." in flat
    assert "Source commit abc1234:" in flat
    assert f"This file describes {_parts(_crate(_report()))[0]}/" in flat


def test_supplied_report_does_not_assert_the_version():
    _, meta, readme = _parts(_crate(_report(), "client_request"))
    flat = " ".join(readme.split())
    assert "Report source: client_supplied" in flat
    assert "9.8.7." not in flat.split("Software", 1)[1].split("Platform version as supplied")[0]
    assert "not asserted by this crate" in flat
    assert "Platform version as supplied in the report: 9.8.7." in flat


def test_the_same_export_gives_the_same_readme():
    assert _parts(_crate(_report()))[2] == _parts(_crate(_report()))[2]


def test_large_folders_are_counted_not_listed():
    sims = [f"qiskit~opt0~run{i}" for i in range(1, LISTED_PER_FOLDER + 3)]
    _, _, readme = _parts(_crate(_report(sims)))
    flat = " ".join(readme.split())
    assert f"transpiled_circuits/ ({len(sims)} files)" in flat
    assert "qiskit~opt0~run7.qasm" not in flat
    assert "Each file's own description is in ro-crate-metadata.json." in flat


def test_the_check_command_verifies_the_extracted_crate(tmp_path):
    zf = _crate(_report())
    zf.extractall(tmp_path)
    top, _, readme = _parts(zf)
    assert CHECK_COMMAND in readme
    args = CHECK_COMMAND.split(" ", 2)
    out = subprocess.run([sys.executable, args[1], args[2].strip('"')], cwd=tmp_path / top,
                         capture_output=True, text=True, check=True).stdout.split("\n")
    rows = [line for line in out if line]
    assert rows and all(line.endswith(" ok") for line in rows), rows
    assert any(line.startswith(f"{README_PATH} ") for line in rows)
    (tmp_path / top / "circuit.qasm").write_text("changed")
    out = subprocess.run([sys.executable, args[1], args[2].strip('"')], cwd=tmp_path / top,
                         capture_output=True, text=True, check=True).stdout
    assert "circuit.qasm DIFFERS" in out
