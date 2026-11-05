"""The local server's finished-job settings: [lifecycle] jobs_kept, job_storage and
job_retention in the config file, overridden by QROSETTA_JOB_MAX_KEPT, QROSETTA_JOB_SPILL_MAX_MIB
and QROSETTA_JOB_TTL_SEC, passed to compose by start and status, shown by start, status, doctor
and config show."""
import json
import re

import pytest
import yaml

from tests.unit._qrosetta_fake import REPO, FakeServer
from tests.unit.test_qrosetta_cli import _created, cli
from tests.unit.test_qrosetta_doctor import FakeHost, _by_id, _doctor

from qrosetta_cli import config as cfgmod, jobstore  # noqa: E402
from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.errors import CliError, Exit  # noqa: E402
from qrosetta_cli.stack import doctor  # noqa: E402

@pytest.fixture
def env(tmp_path):
    return {"QROSETTA_PROJECT": "qr", "PATH": "/usr/bin", "HOME": str(tmp_path / "home"),
            "XDG_RUNTIME_DIR": str(tmp_path / "run"), "XDG_STATE_HOME": str(tmp_path / "state"),
            "XDG_CONFIG_HOME": str(tmp_path / "config"), "XDG_CACHE_HOME": str(tmp_path / "cache")}


@pytest.fixture
def project(tmp_path):
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    return tmp_path


DEFAULT_LINE = ("Finished jobs: kept up to 24 h, at most 200, in up to 4.0 GiB of job storage "
                "(change: qrosetta config path → [lifecycle] jobs_kept, job_storage, job_retention)")


@pytest.mark.parametrize("value, mib", [(4096, 4096), ("4096", 4096), ("4096MiB", 4096), ("4GiB", 4096),
                                        ("8 gib", 8192), ("1.5GiB", 1536), (" 512 MiB ", 512)])
def test_job_storage_sizes(value, mib):
    assert jobstore.parse_job_storage(value) == mib


@pytest.mark.parametrize("value", [0, -1, "0GiB", "4TB", "4 G", "lots", "", True, 4.5, ["4GiB"]])
def test_job_storage_nonsense_is_refused(value):
    with pytest.raises(ValueError):
        jobstore.parse_job_storage(value)


@pytest.mark.parametrize("value, sec", [(3600, 3600), ("86400", 86400), ("90s", 90), ("30m", 1800),
                                        ("24h", 86400), ("2 H", 7200), (60, 60)])
def test_job_retention_times(value, sec):
    assert jobstore.parse_job_retention(value) == sec


@pytest.mark.parametrize("value", [59, "30s", "0h", "1d", "24 hours", "-1h", "", False, 1.5])
def test_job_retention_nonsense_or_under_a_minute_is_refused(value):
    with pytest.raises(ValueError):
        jobstore.parse_job_retention(value)


@pytest.mark.parametrize("value", [0, -3, "x", "", True, 2.0, "1e3"])
def test_jobs_kept_nonsense_is_refused(value):
    with pytest.raises(ValueError):
        jobstore.parse_jobs_kept(value)


def test_defaults_are_the_compose_defaults_and_the_api_count_default():
    compose = yaml.safe_load((REPO / "docker-compose.yml").read_text())
    api_env = compose["services"]["api"]["environment"]
    for key, (var, default, _) in jobstore.SETTINGS.items():
        assert f"{var}=${{{var}:-{default}}}" in api_env, key
    config_py = (REPO / "rosetta-api" / "config.py").read_text()
    assert re.search(r'JOB_MAX_KEPT: int = Field\(default=200, validation_alias="QROSETTA_JOB_MAX_KEPT"\)', config_py)


def _cfg(tmp_path, text):
    path = tmp_path / "c.toml"
    path.write_text(text)
    return cfgmod.load(str(path), {})


def test_config_keys_load_and_nonsense_is_refused_naming_the_key(tmp_path):
    pytest.importorskip("tomllib")
    cfg = _cfg(tmp_path, '[lifecycle]\njobs_kept = 300\njob_storage = "8GiB"\njob_retention = "48h"\n')
    got = jobstore.resolve({}, cfg)
    assert got == {"jobs_kept": (300, "config lifecycle.jobs_kept"),
                   "job_storage": (8192, "config lifecycle.job_storage"),
                   "job_retention": (172800, "config lifecycle.job_retention")}
    for text, key in (('job_storage = "8 gigs"', "job_storage"), ("jobs_kept = 0", "jobs_kept"),
                      ('job_retention = "10s"', "job_retention"), ('jobs_kept = "many"', "jobs_kept")):
        with pytest.raises(CliError) as err:
            _cfg(tmp_path, f"[lifecycle]\n{text}\n")
        assert err.value.reason == "config_invalid" and f"'lifecycle.{key}'" in err.value.message
        assert err.value.hint.startswith("edit ")


def test_the_environment_wins_over_the_config_and_the_config_over_the_default(tmp_path):
    pytest.importorskip("tomllib")
    cfg = _cfg(tmp_path, '[lifecycle]\njob_storage = "8GiB"\njobs_kept = 300\n')
    got = jobstore.resolve({"QROSETTA_JOB_SPILL_MAX_MIB": "16GiB", "QROSETTA_JOB_MAX_KEPT": ""}, cfg)
    assert got["job_storage"] == (16384, "env QROSETTA_JOB_SPILL_MAX_MIB")
    assert got["jobs_kept"] == (300, "config lifecycle.jobs_kept")
    assert got["job_retention"] == (86400, "default")
    assert jobstore.compose_env(got) == {"QROSETTA_JOB_SPILL_MAX_MIB": "16384", "QROSETTA_JOB_MAX_KEPT": "300",
                                         "QROSETTA_JOB_TTL_SEC": "86400"}
    with pytest.raises(CliError) as err:
        jobstore.resolve({"QROSETTA_JOB_TTL_SEC": "soon"}, cfg)
    assert err.value.reason == "job_setting_invalid" and err.value.hint == "unset QROSETTA_JOB_TTL_SEC"
    assert "env QROSETTA_JOB_TTL_SEC" in err.value.message


def test_the_line_and_block():
    got = jobstore.resolve({}, None)
    assert jobstore.line(got) == DEFAULT_LINE
    assert jobstore.block(got) == {"jobs_kept": 200, "job_storage_mib": 4096, "job_retention_sec": 86400,
                                   "sources": {"jobs_kept": "default", "job_storage": "default",
                                               "job_retention": "default"}}
    other = jobstore.resolve({"QROSETTA_JOB_TTL_SEC": "90m", "QROSETTA_JOB_SPILL_MAX_MIB": "8GiB"}, None)
    assert jobstore.describe(other) == "Finished jobs: kept up to 90 min, at most 200, in up to 8.0 GiB of job storage"


def _api_up_env(fake):
    return next(e for c, e in reversed(fake.calls) if c[1:2] == ["compose"] and "up" in c)


def test_start_passes_the_settings_to_compose_and_a_change_recreates_the_api(project, env, capsys, monkeypatch):
    from tests.unit.test_qrosetta_contracts import validate_envelope
    fake = _created(project, env, monkeypatch)
    capsys.readouterr()
    assert cli(fake, project, env, ["start", "-d", "--json"], server=FakeServer(fresh=True)) == 0
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    assert doc["data"]["finished_jobs"]["jobs_kept"] == 200 and not fake.recreated
    config = project / "qr.toml"
    config.write_text('[lifecycle]\njobs_kept = 300\njob_storage = "8GiB"\n')
    assert cli(fake, project, dict(env, QROSETTA_CONFIG=str(config)), ["start", "-d"],
               server=FakeServer(fresh=True)) == 0
    err = capsys.readouterr().err
    assert fake.recreated == ["c-rosetta-api"]
    up = _api_up_env(fake)
    assert up["QROSETTA_JOB_MAX_KEPT"] == "300" and up["QROSETTA_JOB_SPILL_MAX_MIB"] == "8192"
    assert up["QROSETTA_JOB_TTL_SEC"] == "86400"
    assert "Finished jobs: kept up to 24 h, at most 300, in up to 8.0 GiB of job storage" in err
    fake.recreated.clear()
    assert cli(fake, project, dict(env, QROSETTA_CONFIG=str(config), QROSETTA_JOB_MAX_KEPT="250"),
               ["start", "-d"], server=FakeServer(fresh=True)) == 0
    assert fake.recreated == ["c-rosetta-api"] and _api_up_env(fake)["QROSETTA_JOB_MAX_KEPT"] == "250"


def test_status_prints_the_line_and_carries_the_values(project, env, capsys, monkeypatch):
    from tests.unit.test_qrosetta_contracts import validate_envelope
    fake = _created(project, env, monkeypatch)
    capsys.readouterr()
    assert cli(fake, project, env, ["status"]) == 0
    assert DEFAULT_LINE in capsys.readouterr().out.splitlines()
    assert cli(fake, project, dict(env, QROSETTA_JOB_TTL_SEC="2h"), ["status", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    assert doc["data"]["finished_jobs"]["job_retention_sec"] == 7200
    assert doc["data"]["finished_jobs"]["sources"]["job_retention"] == "env QROSETTA_JOB_TTL_SEC"
    rows = {r["id"]: r for r in doc["data"]["services"]}
    assert rows["api"]["config_current"] is False and rows["nginx"]["config_current"] is True


def test_doctor_reports_the_settings_and_warns_when_the_budget_exceeds_free_disk(env):
    rows = _by_id(_doctor(env, FakeHost(env, free=50 * doctor.GIB)))["jobs"]
    assert [(c.status, c.message) for c in rows] == [("INFO", DEFAULT_LINE)]
    rows = _by_id(_doctor(env, FakeHost(env, free=5 * doctor.GIB)))["jobs"]
    assert [c.status for c in rows] == ["INFO"]
    rows = _by_id(_doctor(dict(env, QROSETTA_JOB_SPILL_MAX_MIB="8GiB"), FakeHost(
        dict(env, QROSETTA_JOB_SPILL_MAX_MIB="8GiB"), free=8 * doctor.GIB)))["jobs"]
    assert [c.status for c in rows] == ["INFO", "WARN"]
    assert rows[1].message == ("job storage 8.0 GiB is more than the image store's free space less 1 GiB "
                               "(7.0 GiB)")
    bad = dict(env, QROSETTA_JOB_MAX_KEPT="lots")
    rep = _doctor(bad, FakeHost(bad))
    assert [c.status for c in _by_id(rep)["jobs"]] == ["FAIL"]
    disk = [c.id for c in rep.checks]
    assert disk.index("jobs") == max(i for i, c in enumerate(disk) if c == "disk") + 1


def test_config_show_lists_the_settings_with_their_source(env, capsys):
    assert main(["config", "show", "--json"], env=dict(env, QROSETTA_JOB_SPILL_MAX_MIB="8GiB")) == 0
    rows = {r["key"]: r for r in json.loads(capsys.readouterr().out)["data"]["settings"]}
    assert rows["lifecycle.job_storage"] == {"key": "lifecycle.job_storage", "value": "8192 MiB",
                                             "source": "env QROSETTA_JOB_SPILL_MAX_MIB"}
    assert rows["lifecycle.jobs_kept"]["value"] == 200 and rows["lifecycle.jobs_kept"]["source"] == "default"
    assert rows["lifecycle.job_retention"]["value"] == "86400 s"
    assert main(["config", "show"], env=dict(env, QROSETTA_JOB_MAX_KEPT="0")) == Exit.USAGE
