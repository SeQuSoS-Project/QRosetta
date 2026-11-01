"""The requalification harness (scripts/requalify/): registry lookup, the candidate Dockerfile
rewrite judged by the reproducible-build rules, wheel tags, the corpus, and the comparator's
exclusions. Stdlib and pytest only; no container engine."""

import base64
import importlib.util
import json
import struct
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts" / "requalify"))

import candidate  # noqa: E402
import compare  # noqa: E402
import corpus  # noqa: E402
import driver  # noqa: E402
import engine  # noqa: E402
import registry  # noqa: E402
import report  # noqa: E402
import requalify  # noqa: E402
import timing  # noqa: E402

sys.path.remove(str(REPO / "scripts" / "requalify"))

_spec = importlib.util.spec_from_file_location("reproducible_builds_rules",
                                               Path(__file__).with_name("test_reproducible_builds.py"))
rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rules)

NEW_BASE = "python:3.12-slim@sha256:12316debbfb86890f6b2d825820612741ba527ad5a44e3902759141d572bfe8f"
SERVICES = registry.services()


def test_registry_lists_every_service_directory():
    dirs = {p.parent.relative_to(REPO).as_posix()
            for d in ("runners", "compilers") for p in (REPO / d).glob("*/Dockerfile")}
    assert {s["dir"] for s in SERVICES.values()} == dirs
    assert SERVICES["qulacs"] == {"kind": "runner", "dir": "runners/pytket-qulacs-runner", "levels": [0, 1, 2],
                                  "enabled": True}
    assert SERVICES["cirq-transformers"]["dir"] == "compilers/cirq-compiler"
    assert all(s["levels"] for s in SERVICES.values())


def test_sdk_packages_are_read_from_main():
    text = (REPO / "runners" / "pytket-qulacs-runner" / "main.py").read_text()
    assert registry.sdk_packages(text) == ["pytket", "pytket-qulacs", "qulacs"]
    assert registry.sdk_packages('declare_sdk_packages(\n    "a",\n    "b-c",\n)') == ["a", "b-c"]


@pytest.mark.parametrize("service", sorted(s for s in SERVICES if SERVICES[s]["dir"]))
def test_candidate_dockerfile_meets_the_reproducible_build_rules(service, tmp_path):
    path = REPO / SERVICES[service]["dir"] / "Dockerfile"
    text = path.read_text()
    if "DEBIAN_SNAPSHOT" in text:
        with pytest.raises(ValueError):
            candidate.rewrite_dockerfile(text, NEW_BASE, rules.snapshot_default())
        return
    new, changes, manual = candidate.rewrite_dockerfile(text, NEW_BASE, rules.snapshot_default())
    assert candidate.python_bases(new) == [NEW_BASE] * len(candidate.python_bases(text))
    out = tmp_path / "Dockerfile"
    out.write_text(new)
    problems = rules.problems_of(out, rules.snapshot_default())
    left = [p for p in problems if not any(m in p for m in manual)]
    assert not left, left
    assert any(c.startswith("FROM ") for c in changes)


_UNREQUALIFIED = """FROM python:3.11-slim@sha256:9358444059ed78e2975ada2c189f1c1a3144a5dab6f35bff8c981afb38946634 AS tool-build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential
RUN pip install --no-cache-dir -r /build/build-requirements.txt

FROM python:3.10-slim@sha256:4ba18b066cee17f2696cf9a2ba564d7d5eb05a91d6a949326780aa7c6912160d

RUN useradd -m appuser
WORKDIR /home/appuser/app
COPY runners/x-runner/requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

COPY shared /tmp/shared-src
RUN pip install /tmp/shared-src
COPY --from=tool-build /build/tool /usr/local/bin/tool
USER appuser
"""


def test_rewrite_keeps_every_other_line_and_names_what_it_left(tmp_path):
    new, changes, manual = candidate.rewrite_dockerfile(_UNREQUALIFIED, NEW_BASE, rules.snapshot_default())
    kept = [line for line in _UNREQUALIFIED.splitlines() if not line.startswith("FROM") and "pip install" not in line]
    new_lines = new.splitlines()
    assert all(line in new_lines for line in kept)
    assert new_lines.count(f"ARG DEBIAN_SNAPSHOT={rules.snapshot_default()}") == 2
    assert f"FROM {NEW_BASE} AS tool-build" in new_lines and f"FROM {NEW_BASE}" in new_lines
    assert "RUN pip install --no-cache-dir --require-hashes -r requirements.lock" in new_lines
    assert manual == ["pip install --no-cache-dir -r /build/build-requirements.txt"]
    assert len(changes) == 4
    out = tmp_path / "Dockerfile"
    out.write_text(new)
    assert [p for p in rules.problems_of(out, rules.snapshot_default()) if "build-requirements" not in p] == []


@pytest.mark.parametrize("filename,py,fits", [
    ("qulacs-0.6.5-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", (3, 12), True),
    ("qulacs-0.6.5-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl", (3, 13), False),
    ("psutil-6.0.0-cp36-abi3-manylinux_2_12_x86_64.manylinux2010_x86_64.whl", (3, 13), True),
    ("six-1.17.0-py2.py3-none-any.whl", (3, 12), True),
    ("numpy-1.26.4-cp312-cp312-musllinux_1_1_x86_64.whl", (3, 12), False),
    ("x-1-cp312-cp312-manylinux_2_42_x86_64.whl", (3, 12), False),
    ("x-1-cp312-cp312-manylinux_2_28_aarch64.whl", (3, 12), False),
    ("x-1-cp312-cp312-win_amd64.whl", (3, 12), False),
    ("torch-2.2.2+cpu-cp312-cp312-linux_x86_64.whl", (3, 12), True),
    ("torch-2.2.2+cpu-cp312-cp312-linux_aarch64.whl", (3, 12), False),
])
def test_wheel_fits(filename, py, fits):
    assert candidate.wheel_fits(filename, py, glibc=(2, 41)) is fits


def test_local_version_pins_are_looked_up_in_the_extra_index(tmp_path):
    lock = "--extra-index-url https://download.pytorch.org/whl/cpu\n\ntorch==2.2.2+cpu \\\n    --hash=sha256:0\n"
    assert candidate.extra_indexes(lock) == ["https://download.pytorch.org/whl/cpu"]
    pypi = candidate.PyPI(tmp_path, candidate.extra_indexes(lock))
    page = tmp_path / "simple__https_download_pytorch_org_whl_cpu__torch.html"
    page.write_text('<a href="/whl/cpu/torch-2.2.2%2Bcpu-cp312-cp312-linux_x86_64.whl#sha256=0">x</a>\n'
                    '<a href="/whl/cpu/torch-2.2.2+cpu-cp312-cp312-linux_x86_64.whl#sha256=0">x</a>\n'
                    '<a href="/whl/cpu/torch-2.2.20+cpu-cp313-cp313-linux_x86_64.whl#sha256=0">x</a>\n'
                    '<a href="/whl/cpu/torch-2.3.0+cpu-cp313-cp313-linux_x86_64.whl#sha256=0">x</a>\n')
    assert pypi.files("torch", "2.2.2+cpu") == ["torch-2.2.2+cpu-cp312-cp312-linux_x86_64.whl"]


def test_parse_lock_reads_hashed_and_plain_locks():
    hashed = "a-b==1.0 \\\n    --hash=sha256:" + "0" * 64 + "\n    # via x\nC_d[e]==2.0\n# comment==3\n"
    assert candidate.parse_lock(hashed) == {"a-b": ("a-b", "1.0"), "c-d": ("C_d", "2.0")}
    assert candidate.lock_moves({"a": ("a", "1"), "b": ("b", "1")}, {"a": ("a", "2"), "c": ("c", "1")}) == [
        {"name": "a", "old": "1", "new": "2"}, {"name": "b", "old": "1", "new": None},
        {"name": "c", "old": None, "new": "1"}]


class _FakePyPI:
    def __init__(self, files, releases):
        self._files, self._releases = files, releases

    def files(self, name, version):
        return self._files[(name, version)]

    def releases(self, name):
        return self._releases[name]


def test_wheel_check_stops_on_an_sdk_and_moves_other_pins_to_the_nearest_build():
    old_only = "{}-{}-cp310-cp310-manylinux_2_17_x86_64.whl"
    new = "{}-{}-cp312-cp312-manylinux_2_17_x86_64.whl"
    pypi = _FakePyPI(
        {("sdk", "1.0"): [old_only.format("sdk", "1.0")], ("dep", "1.0"): [old_only.format("dep", "1.0")]},
        {"dep": {"1.0": [], "1.1rc1": [{"filename": new.format("dep", "1.1rc1")}],
                 "1.2": [{"filename": new.format("dep", "1.2")}], "2.0": [{"filename": new.format("dep", "2.0")}]}})
    rows = candidate.wheel_check({"sdk": ("sdk", "1.0"), "dep": ("dep", "1.0")}, (3, 10), (3, 12), {"sdk"}, pypi)
    by_name = {r["name"]: r for r in rows}
    assert by_name["sdk"]["sdk"] and not by_name["sdk"]["new_wheel"] and by_name["sdk"]["nearest"] is None
    assert by_name["dep"]["nearest"] == "1.2"


def test_write_constraints_replaces_and_drops_pins(tmp_path):
    src = tmp_path / "svc"
    src.mkdir()
    (src / "requirements.txt").write_text("dep==1.0\nsdk==1.0\n")
    (src / "requirements.lock").write_text("# header\ndep==1.0\nsdk==1.0\nloose==3\n")
    candidate.write_constraints(tmp_path / "cand", src, {"dep": "1.2"}, ["loose"])
    assert (tmp_path / "cand" / "requirements.txt").read_text() == "dep==1.2\nsdk==1.0\n"
    assert (tmp_path / "cand" / "requirements.lock").read_text() == "# header\ndep==1.2\nsdk==1.0\n"


def test_bump_arguments_are_checked():
    assert requalify.parse_args(["qiskit", "--bump", "anyio==4.14.2"]).bump == ["anyio==4.14.2"]
    for argv in (["qiskit"], ["qiskit", "--bump", "anyio>=4"], ["qiskit", "--candidate", "x", "--bump", "a==1"]):
        with pytest.raises(SystemExit):
            requalify.parse_args(argv)


def test_a_bump_keeps_the_base_and_moves_only_named_pins(tmp_path, monkeypatch):
    svc_dir = tmp_path / "runners" / "x-runner"
    svc_dir.mkdir(parents=True)
    dockerfile = f"FROM {NEW_BASE}\nARG DEBIAN_SNAPSHOT=1\nRUN pip install --require-hashes -r requirements.lock\n"
    (svc_dir / "Dockerfile").write_text(dockerfile)
    (svc_dir / "main.py").write_text("")
    (svc_dir / "requirements.txt").write_text("fastapi==0.115.0\nsdk==1.0\n")
    (svc_dir / "requirements.lock").write_text("anyio==4.14.1 \\\n    --hash=sha256:00\nfastapi==0.115.0\nsdk==1.0\n")
    monkeypatch.setattr(requalify, "REPO", tmp_path)
    monkeypatch.setattr(requalify, "track_pull", lambda ref, state: None)
    monkeypatch.setattr(requalify, "base_facts", lambda base: ((3, 12), (2, 41)))
    monkeypatch.setattr(requalify.cand, "wheel_check", lambda *a, **k: [])
    monkeypatch.setattr(requalify.cand, "compile_lock", lambda cand_dir, base, env: None)
    record = requalify.prepare({"dir": "runners/x-runner"}, "x", None, tmp_path / "cand", [], tmp_path, {},
                               ["anyio==4.14.2", "fastapi==0.136.3", "absent==9"])
    assert record["new_base"] == NEW_BASE and record["bumped"] == {"anyio": "4.14.2", "fastapi": "0.136.3"}
    assert (tmp_path / "cand" / "Dockerfile").read_text() == dockerfile
    assert (tmp_path / "cand" / "requirements.txt").read_text() == "fastapi==0.136.3\nsdk==1.0\n"
    assert [m["name"] for m in record["lock_moves"]] == ["anyio", "fastapi"]


def test_corpus_is_fixed_and_covers_every_part():
    first = corpus.build("runner", [0, 1], 4, 6, 1)
    assert first == corpus.build("runner", [0, 1], 4, 6, 1)
    assert len({c["id"] for c in first}) == len(first)
    parts = {c["kind"] for c in first}
    assert parts == {"random_sv", "random_measured", "midcircuit_measured", "deep_sv", "deep_measured", "selftest_sv",
                     "selftest_measured"}
    measured = [c for c in first if c["endpoint"] == "run_measured"]
    assert {c["payload"]["seed"] for c in measured} <= set(corpus.SEEDS)
    assert {c["payload"]["n_shots"] for c in measured} <= set(corpus.SHOTS)
    assert {(c["level"], c["pre"]) for c in first} == {(0, True), (0, False), (1, True), (1, False)}
    compiled = corpus.build("compiler", [1, 2], 3, 0, 1)
    assert {c["endpoint"] for c in compiled} == {"compile"}
    assert not any("measure" in c["payload"]["circuit_data"] for c in compiled)
    assert all("apply_preprocessing" not in c["payload"] for c in compiled)


def test_timing_payloads_are_the_three_time_paths_circuits():
    payloads = corpus.timing_payloads(3)
    assert sorted(payloads) == sorted(f"{m}-{n}.json" for m in ("sv", "measured")
                                      for n in ("qft16", "4q_2200g", "16q_400g"))
    assert payloads["measured-qft16.json"]["payload"]["n_shots"] == 8200
    assert all(p["payload"]["timing_repeats"] == 3 for p in payloads.values())


def _vector(values):
    return base64.b64encode(b"".join(struct.pack("dd", v.real, v.imag) for v in values)).decode()


def test_comparator_ignores_measurements_and_separates_provenance():
    old = {"counts": {"0": 1}, "compilation_time_sec": 1.0, "simulation_time_samples": [1], "x_sec_median": 2,
           "process_peak_rss_mb": 3, "sdk_versions": {"a": "1"}, "runtime_environment": {"python": "3.10"}}
    new = {**old, "compilation_time_sec": 2.0, "simulation_time_samples": [5], "x_sec_median": 9,
           "process_peak_rss_mb": 4, "runtime_environment": {"python": "3.12"}}
    assert compare.compare_results(old, new) == ([], ["runtime_environment"])
    assert compare.compare_results(old, {**new, "counts": {"1": 1}}) == (["counts"], ["runtime_environment"])
    assert compare.compare_results(old, {**new, "sdk_versions": {"a": "2"}}) == (["sdk_versions"],
                                                                                ["runtime_environment"])
    assert "compilation_time_sec" in compare.exclusion_text()


def test_statevector_distance_and_known_jitter(tmp_path):
    a = [1 / 2 ** 0.5, 1 / 2 ** 0.5]
    b = [1 / 2 ** 0.5 + 1e-17, 1 / 2 ** 0.5]
    infidelity, delta = compare.statevector_distance(_vector(a), _vector(b), "complex128")
    assert abs(infidelity) < 1e-15 and delta < 1e-15
    cases = [{"id": "c1", "kind": "random_sv", "level": 0, "pre": True}]
    for label, vec in (("old", a), ("new", b)):
        d = tmp_path / label
        d.mkdir()
        sv = {"sha256": label, "bytes": 32}
        (d / "results.jsonl").write_text(json.dumps({"id": "c1", "result": {"statevector": sv,
                                                                             "precision": "complex128"}}) + "\n")
        (d / "vectors.jsonl").write_text(json.dumps({"id": "c1", "statevector": _vector(vec)}) + "\n")
    cirq = compare.compare_corpus(tmp_path / "old", tmp_path / "new", cases, "cirq")
    assert cirq["differences"][0]["class"] == "known_jitter"
    other = compare.compare_corpus(tmp_path / "old", tmp_path / "new", cases, "qulacs")
    assert other["differences"][0]["class"] == "output"
    assert other["by_kind"]["random_sv"] == {"cases": 1, "different": 1}


def test_report_states_the_result(tmp_path):
    ev = {"service": "qulacs", "svc": SERVICES["qulacs"], "git_sha": "abc", "started": "2026-10-28T00:00:00",
          "finished": "x", "prepare": {"stop": ["qulacs==1 (SDK) has no build for Python 3.13"]}}
    report.write(tmp_path / "r.md", ev)
    assert "STOPPED: qulacs==1 (SDK)" in (tmp_path / "r.md").read_text()


def test_timing_summary_uses_accepted_rounds_only():
    def result(comp, sim):
        return {"compilation_time_samples": comp, "simulation_time_samples": sim, "process_peak_rss_mb": 100.0,
                "simulation_cpus": [4], "simulation_throttled_samples": [0.0] * len(sim),
                "statevector": {"sha256": "a", "bytes": 16}}
    rounds = [
        {"accepted": True, "results": {"old": {"sv-x.json": result([0.001, 0.003], [0.010, 0.030])},
                                       "new": {"sv-x.json": result([0.002], [0.020])}}},
        {"accepted": False, "results": {"old": {"sv-x.json": result([9.0], [9.0])},
                                        "new": {"sv-x.json": result([9.0], [9.0])}}},
        {"accepted": True, "results": {"old": {"sv-x.json": {"error": "boom"}},
                                       "new": {"sv-x.json": result([0.004], [0.040])}}},
    ]
    summary = timing.summarise(rounds)["sv-x.json"]
    assert summary["old"]["compilation_ms"] == 2.0 and summary["old"]["simulation_ms"] == 20.0
    assert summary["old"]["total_ms"] == 22.0 and summary["old"]["errors"] == 1 and summary["old"]["samples"] == 2
    assert summary["new"]["total_ms"] == 33.0 and summary["new"]["cpus"] == [4]
    assert summary["new"]["distinct_outputs"] == 1


def test_import_check_names_the_module_that_fails(tmp_path, monkeypatch):
    app = tmp_path / "app"
    app.mkdir()
    (app / "main.py").write_text("import pkg_resources_gone_for_the_test\n")
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.delitem(sys.modules, "main", raising=False)
    assert "pytest" in driver.sdk_modules(["PyTest"])
    result = driver.import_check(["pytest"], app)
    assert result["pytest"] is None
    assert "ModuleNotFoundError: No module named 'pkg_resources_gone_for_the_test'" in result["main"]
    monkeypatch.delitem(sys.modules, "main", raising=False)


def test_import_regressions_are_the_imports_only_the_new_image_fails():
    old = {"main": None, "qrisp": None, "broken_everywhere": "ImportError: x"}
    assert compare.import_regressions(old, dict(old)) == {}
    assert compare.import_regressions(old, {**old, "main": "ModuleNotFoundError: pkg_resources"}) == {
        "main": "ModuleNotFoundError: pkg_resources"}
    assert compare.import_regressions(old, {"main": None}) == {"qrisp": "not attempted in the new image"}


def test_the_overlay_copies_every_candidate_file_but_the_prepare_record(tmp_path):
    for name in ("Dockerfile", "requirements.txt", "requirements.lock", "build-requirements.txt", "prepare.json"):
        (tmp_path / name).write_text(name)
    (tmp_path / "pypi-cache").mkdir()
    assert engine.overlay_names(tmp_path) == ["Dockerfile", "build-requirements.txt", "requirements.lock",
                                              "requirements.txt"]


def _exit_hard(payload):
    import os
    os._exit(payload["status"])


def _kill_self(payload):
    import os
    import signal
    os.kill(os.getpid(), signal.SIGKILL)


def _sleep(payload):
    import time
    time.sleep(payload["sec"])


def _raise(payload):
    raise RuntimeError("bad input")


def test_an_isolated_case_returns_its_result_or_a_harness_error():
    assert driver.isolated(lambda p: {"value": p["x"] * 2, "list": (1, 2)}, {"x": 3}) == {"value": 6, "list": [1, 2]}
    assert driver.isolated(_exit_hard, {"status": 3}) == {
        "harness_error": "case process exited with status 3 and no result"}
    assert driver.isolated(_kill_self, {}) == {"harness_error": "case process killed by signal 9"}
    assert driver.isolated(_sleep, {"sec": 30}, timeout=0.5) == {"harness_error": "case exceeded 0.5 s"}
    assert driver.isolated(_raise, {}) == {"harness_error": "RuntimeError: bad input"}
    assert driver.isolated(lambda p: object(), {})["harness_error"].startswith("TypeError:")


def test_device_options_reach_the_container_arguments():
    assert engine.device_args([]) == []
    assert engine.device_args(["nvidia.com/gpu=all"]) == ["--device", "nvidia.com/gpu=all"]
