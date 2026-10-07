"""Qubit caps and the job-slot count come from one documented setting each: the API's
defaults equal the runners' and compilers', docker-compose passes the same variables to
every service, and only QROSETTA_K8S_MAX_CONCURRENT_JOBS sets the slot count."""

import re
from pathlib import Path

import config
from qrosetta_commons import compile_service, helpers

_COMPOSE = Path(__file__).resolve().parents[3] / "docker-compose.yml"


def _services() -> dict:
    blocks, name = {}, None
    for line in _COMPOSE.read_text().splitlines():
        m = re.match(r"^  ([a-z_]+):\s*$", line)
        if m:
            name = m.group(1)
        elif name:
            blocks.setdefault(name, []).append(line)
    return {k: "\n".join(v) for k, v in blocks.items()}


def test_shared_defaults_equal_the_api_settings():
    s = config.Settings()
    assert helpers.MAX_QUBITS_STATEVECTOR == s.MAX_QUBITS_STATEVECTOR
    assert helpers.MAX_QUBITS_MEASURED == s.MAX_QUBITS_MEASURED
    assert helpers.MAX_QUBITS_COMPILE == s.MAX_QUBITS_COMPILE


def test_compilers_enforce_the_compile_cap():
    assert compile_service.COMPILE_MAX_QUBITS == helpers.MAX_QUBITS_COMPILE


def test_compose_passes_each_cap_with_the_api_default():
    s = config.Settings()
    expected = {"MAX_QUBITS_STATEVECTOR": s.MAX_QUBITS_STATEVECTOR,
                "MAX_QUBITS_MEASURED": s.MAX_QUBITS_MEASURED,
                "MAX_QUBITS_COMPILE": s.MAX_QUBITS_COMPILE}
    services = _services()
    for name, block in services.items():
        if name.endswith("_runner"):
            needed = ("MAX_QUBITS_STATEVECTOR", "MAX_QUBITS_MEASURED")
        elif name.endswith("_compiler"):
            needed = ("MAX_QUBITS_COMPILE",)
        elif name == "api":
            needed = tuple(expected)
        else:
            continue
        for var in needed:
            assert f"- {var}=${{{var}:-{expected[var]}}}" in block, f"{name}: {var}"


def test_slot_count_reads_only_the_documented_variable(monkeypatch):
    monkeypatch.setenv("K8S_MAX_CONCURRENT_JOBS", "9")
    monkeypatch.delenv("QROSETTA_K8S_MAX_CONCURRENT_JOBS", raising=False)
    assert config.Settings().K8S_MAX_CONCURRENT_JOBS == 3
    monkeypatch.setenv("QROSETTA_K8S_MAX_CONCURRENT_JOBS", "5")
    assert config.Settings().K8S_MAX_CONCURRENT_JOBS == 5
    monkeypatch.setenv("QROSETTA_K8S_MAX_CONCURRENT_JOBS", "0")
    assert config.Settings().K8S_MAX_CONCURRENT_JOBS == 1
