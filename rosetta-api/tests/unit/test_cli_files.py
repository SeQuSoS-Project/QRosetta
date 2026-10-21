"""Runner and compiler CLIs read a payload from a file and write the result to a file, for
batch systems: a payload above one argument's 128 KiB limit, a result apart from the log."""
import argparse
import json
from types import SimpleNamespace

import pytest

from qrosetta_commons import helpers


def _args(**kwargs):
    base = {"s3_job_id": None, "payload": None, "payload_file": None, "result_file": None}
    return SimpleNamespace(**{**base, **kwargs})


def test_payload_file_over_the_argument_limit_and_result_file(tmp_path, capsys):
    payload = {"circuit_data": "x" * 300_000}
    (tmp_path / "in.json").write_text(json.dumps(payload))
    seen = []
    helpers.run_cli_job(lambda p: seen.append(p) or {"ok": len(p["circuit_data"])},
                        _args(payload_file=str(tmp_path / "in.json"),
                              result_file=str(tmp_path / "out.json")), argparse.ArgumentParser())
    assert seen == [payload]
    assert json.loads((tmp_path / "out.json").read_text()) == {"ok": 300_000}
    assert not (tmp_path / "out.json.partial").exists()
    assert capsys.readouterr().out == ""


def test_payload_string_still_prints_the_result(capsys):
    helpers.run_cli_job(lambda p: {"echo": p}, _args(payload='{"a": 1}'), argparse.ArgumentParser())
    assert json.loads(capsys.readouterr().out) == {"echo": {"a": 1}}


@pytest.mark.parametrize("kwargs", [{}, {"payload": "{}", "payload_file": "x.json"}])
def test_exactly_one_payload_source_is_required(kwargs):
    with pytest.raises(SystemExit):
        helpers.run_cli_job(lambda p: p, _args(**kwargs), argparse.ArgumentParser())


def test_both_clis_accept_the_file_arguments():
    parser = argparse.ArgumentParser()
    helpers.add_file_arguments(parser)
    args = parser.parse_args(["--payload-file", "a.json", "--result-file", "b.json"])
    assert (args.payload_file, args.result_file) == ("a.json", "b.json")
    from pathlib import Path
    compile_service = Path(helpers.__file__).with_name("compile_service.py").read_text()
    assert "add_file_arguments(parser)" in compile_service


def test_batch_environment_records_slurm_and_image_fields(monkeypatch):
    for var in list(helpers._BATCH_ENV.values()):
        monkeypatch.delenv(var, raising=False)
    assert helpers.batch_environment() == {}
    monkeypatch.setenv("SLURM_JOB_ID", "123")
    monkeypatch.setenv("SLURMD_NODENAME", "c1001")
    monkeypatch.setenv("QROSETTA_IMAGE_SHA256", "ab" * 32)
    assert helpers.batch_environment() == {"slurm_job_id": "123", "slurm_node": "c1001",
                                            "container_image_sha256": "ab" * 32}


def test_results_carry_batch_environment_only_inside_a_batch_job(monkeypatch):
    for var in list(helpers._BATCH_ENV.values()):
        monkeypatch.delenv(var, raising=False)
    wrapped = helpers.with_sdk_versions(lambda payload: {"ok": True})
    assert "batch_environment" not in wrapped({})
    monkeypatch.setenv("SLURM_JOB_ID", "9")
    assert wrapped({})["batch_environment"] == {"slurm_job_id": "9"}


def test_launch_wrapper_passes_the_batch_variables_into_the_container():
    from pathlib import Path
    script = (Path(__file__).resolve().parents[3] / "scripts" / "roihu" / "run_runner.sh").read_text()
    for var in helpers._BATCH_ENV.values():
        if var != "APPTAINER_CONTAINER":
            assert var in script, var
