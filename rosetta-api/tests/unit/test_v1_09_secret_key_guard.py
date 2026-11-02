"""V1-09: the API does not start without SECRET_KEY outside local mode, and local mode, whose key
is generated per process, runs one worker so every request is checked against the same key."""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[2]
ROOT = API.parent
PRINT_KEY = "import services.security as s; print(s.SECRET_KEY)"


def _import_security(**env):
    base = {k: v for k, v in os.environ.items() if k not in ("SECRET_KEY", "EXECUTION_MODE")}
    base["PYTHONPATH"] = os.pathsep.join([str(API), str(ROOT / "shared")])
    return subprocess.run([sys.executable, "-c", PRINT_KEY], cwd=API, env={**base, **env},
                          capture_output=True, text=True, timeout=120)


@pytest.mark.parametrize("mode", ["kubernetes", "slurm", "anything-not-local"])
def test_v1_09_the_api_refuses_to_start_without_secret_key_outside_local_mode(mode):
    proc = _import_security(EXECUTION_MODE=mode)
    assert proc.returncode != 0
    assert "SECRET_KEY is required" in proc.stderr
    proc = _import_security(EXECUTION_MODE=mode, SECRET_KEY="")
    assert proc.returncode != 0


def test_v1_09_a_set_key_is_used_and_local_mode_generates_one_per_process():
    proc = _import_security(EXECUTION_MODE="kubernetes", SECRET_KEY="k" * 48)
    assert proc.returncode == 0 and proc.stdout.strip() == "k" * 48
    first, second = (_import_security(EXECUTION_MODE="local") for _ in range(2))
    assert first.returncode == second.returncode == 0
    assert len(first.stdout.strip()) >= 64 and first.stdout.strip() != second.stdout.strip()


def _workers(command: str) -> int:
    match = re.search(r"(?:--workers|-w)[ =](\d+)", command)
    return int(match.group(1)) if match else 1


def test_v1_09_local_mode_runs_one_worker_with_the_ephemeral_key():
    dockerfiles = sorted(API.glob("Dockerfile*"))
    assert dockerfiles
    for path in dockerfiles:
        text = path.read_text()
        cmd = next(line for line in text.splitlines() if line.startswith("CMD"))
        assert "gunicorn" in cmd and _workers(cmd) == 1, path.name
        assert "WEB_CONCURRENCY" not in text and "GUNICORN_CMD_ARGS" not in text, path.name
    compose = (ROOT / "docker-compose.yml").read_text()
    api = re.search(r"^  api:\n(.*?)(?=^  \S)", compose, re.M | re.S).group(1)
    assert "SECRET_KEY" not in api, "compose gives the API a key; then more workers would be safe"
    assert not re.search(r"^\s+command:", api, re.M), "a compose command could change the worker count"
    assert "WEB_CONCURRENCY" not in api and "GUNICORN_CMD_ARGS" not in api


def test_a_set_key_shorter_than_32_bytes_is_refused_in_every_mode():
    for mode in ("local", "kubernetes"):
        proc = _import_security(EXECUTION_MODE=mode, SECRET_KEY="k" * 31)
        assert proc.returncode != 0 and "at least 32 bytes" in proc.stderr
    assert _import_security(EXECUTION_MODE="kubernetes", SECRET_KEY="k" * 32).returncode == 0


def test_s3_storage_needs_both_keys():
    base = {k: v for k, v in os.environ.items() if not k.startswith("S3_")}
    base["PYTHONPATH"] = os.pathsep.join([str(API), str(ROOT / "shared")])
    proc = subprocess.run([sys.executable, "-c", "import services.storage"], cwd=API, capture_output=True,
                          text=True, timeout=120, env={**base, "STORAGE_MODE": "s3"})
    assert proc.returncode != 0 and "S3_ACCESS_KEY and S3_SECRET_KEY are required" in proc.stderr
