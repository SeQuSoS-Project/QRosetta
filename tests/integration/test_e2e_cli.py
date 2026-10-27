"""End-to-end smoke test of the qrosetta client commands against a running stack: `run` of
QFT-4 in both modes on a few runners, `show summary` from the saved files and from the server,
and `export crate`. The CLI gets its own empty config, state and runtime directories, so no
stored token or setting of this machine is used.

    python -m pytest tests/integration/test_e2e_cli.py
"""

import ipaddress
import json
import os
import subprocess
import sys
import urllib.parse
import zipfile
from pathlib import Path

import pytest

from live_stack import BASE_URL, selected_runners

REPO = Path(__file__).resolve().parents[2]
RUNNERS = selected_runners(["qiskit", "qulacs", "cirq"])
SEED = 20261028
DIFFERENCE = "difference"
AGREEMENT = "agreement"
CLI_TIMEOUT_SEC = 900


def _loopback_bind() -> str:
    """host:port of BASE_URL when it is this machine, else ''."""
    parts = urllib.parse.urlsplit(BASE_URL)
    host = parts.hostname or ""
    try:
        loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    if not loopback:
        return ""
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return f"127.0.0.1:{port}"


@pytest.fixture(scope="module")
def cli(tmp_path_factory):
    """Runs ./qrosetta with private directories; a stack on this machine is the local server
    (so saves are gated, as for a user), any other address is passed with --server."""
    home = tmp_path_factory.mktemp("qrosetta-cli")
    for name in ("config", "state", "runtime"):
        (home / name).mkdir(mode=0o700)
    config = home / "config.toml"
    bind = _loopback_bind()
    config.write_text(f'[lifecycle]\nbind = "{bind}"\n' if bind else "")
    env = {k: v for k, v in os.environ.items() if not k.startswith("QROSETTA_")}
    env.update(
        XDG_CONFIG_HOME=str(home / "config"),
        XDG_STATE_HOME=str(home / "state"),
        XDG_RUNTIME_DIR=str(home / "runtime"),
        QROSETTA_CONFIG=str(config),
    )
    server = [] if bind else ["--server", BASE_URL]

    def run(*args):
        proc = subprocess.run(
            [sys.executable, str(REPO / "qrosetta"), *args, *server, "--json"],
            capture_output=True,
            text=True,
            env=env,
            cwd=home,
            timeout=CLI_TIMEOUT_SEC,
        )
        print(proc.stderr[-2000:])
        envelope = json.loads(proc.stdout) if proc.stdout.strip() else {}
        return proc.returncode, envelope

    return {"run": run, "home": home}


def _by_role(summary: dict) -> dict:
    roles = summary["outcome_roles"]
    totals = {}
    for name, count in summary["outcomes"].items():
        totals[roles.get(name)] = totals.get(roles.get(name), 0) + count
    return totals


def test_run_show_summary_export_crate(cli):
    results = cli["home"] / "results"
    code, envelope = cli["run"](
        "run",
        "algorithm:qft:4",
        "-m",
        "statevector,measured",
        "-b",
        ",".join(RUNNERS),
        "--seed",
        str(SEED),
        "--name",
        "e2e-cli",
        "--results-dir",
        str(results),
        "--fail-on",
        "differs,runs_without_output",
        "--wait-timeout",
        "10m",
    )
    assert code == 0 and envelope.get("ok") is True, envelope.get("error")
    jobs = {job["mode"]: job for job in envelope["data"]["jobs"]}
    assert sorted(jobs) == ["measured", "statevector"]
    pairs = len(RUNNERS) * (len(RUNNERS) - 1) // 2
    for mode, job in jobs.items():
        assert job["status"] == "completed", (mode, job)
        assert job["save_status"] == "complete", (mode, job)
        assert sorted(job["backends"]) == sorted(RUNNERS)
        for name in ("request", "job", "report", "summary"):
            assert (Path(job["dir"]) / job["files"][name]).is_file(), (mode, name)
        roles = _by_role(job["summary"])
        assert roles.get(DIFFERENCE, 0) == 0 and roles.get(AGREEMENT, 0) == pairs, (mode, roles)

    measured = jobs["measured"]["job_id"]
    code, saved = cli["run"]("show", "summary", "--result", f"job:{measured}", "--results-dir", str(results))
    assert code == 0 and saved["ok"] is True, saved.get("error")
    saved_file = Path(jobs["measured"]["dir"]) / jobs["measured"]["files"]["summary"]
    saved_file.rename(saved_file.with_name("summary.saved.json"))
    code, served = cli["run"]("show", "summary", "--result", f"job:{measured}", "--results-dir", str(results))
    assert code == 0 and served["ok"] is True, served.get("error")
    assert saved["data"]["jobs"][0]["source"] == "saved summary.json"
    assert served["data"]["jobs"][0]["source"] == "the server's job"
    assert saved["data"]["jobs"][0]["summary"]["outcomes"] == served["data"]["jobs"][0]["summary"]["outcomes"]

    statevector = jobs["statevector"]["job_id"]
    crate = cli["home"] / "statevector-crate.zip"
    code, exported = cli["run"](
        "export", "crate", "--result", f"job:{statevector}", "--results-dir", str(results), "-o", str(crate)
    )
    assert code == 0 and exported["ok"] is True, exported.get("error")
    assert exported["data"]["report_source"] == "server_job"
    with zipfile.ZipFile(crate) as archive:
        names = {name.split("/", 1)[1] for name in archive.namelist() if "/" in name}
        metadata = json.loads(
            next(archive.read(n) for n in archive.namelist() if n.endswith("/ro-crate-metadata.json"))
        )
    assert {"ro-crate-metadata.json", "README.txt", "circuit.qasm", "results.json"} <= names
    assert {f"dispatched_circuits/{r}.qasm" for r in RUNNERS} <= names
    assert {f"transpiled_circuits/{r}.qasm" for r in RUNNERS} <= names
    assert "@graph" in metadata
