"""Timing caveats derived from recorded fields, the endpoint the page asks for older reports,
run completeness, and the crate statements."""
import io
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import timing
from routers.errors import register_error_handlers
from services import report_provenance, timing_caveats as tc
from services.exporter import build_export_context, build_ro_crate, crate_name
from services.security import limiter
from tests.unit.frontend_harness import call_js, requires_node

_JS = Path(__file__).resolve().parents[2] / "static" / "js"


def _ok(sim="qiskit", **fields):
    base = {"simulator": sim, "execution_time_sec": 0.2, "simulation_time_sec": 0.1,
            "timing_samples": 3, "exclusive": True, "concurrent_runs": 1,
            "overlapping_runs": 0, "server_overlapping_runs": 0,
            "cpu_environment": {"cpu_quota_cores": 1.0, "cpu_max_mhz": {"0": 5300.0}},
            "simulation_cpus": [0], "runtime_environment": {"machine": "x86_64"}}
    return {**base, **fields}


def _codes(result):
    return [c["code"] for c in tc.result_caveats(result)]


def test_a_clean_exclusive_repeated_run_has_no_caveat():
    assert _codes(_ok()) == []


@pytest.mark.parametrize("fields,code,expected", [
    ({"simulation_throttled_sec": 0.001}, "throttled", True),
    ({"simulation_throttled_sec": 0.00099}, "throttled", False),
    ({"simulation_throttled_sec": 0.0}, "throttled", False),
    ({"simulation_throttled_sec": 0.01, "simulation_time_sec": None}, "throttled", True),
    ({"compilation_throttled_sec": 0.01, "compilation_time_sec": 0.5}, "compilation_throttled", True),
    ({"simulation_cgroup_cpu_time_sec": 0.106, "simulation_cpu_time_sec": 0.1}, "outside_process", False),
    ({"simulation_cgroup_cpu_time_sec": 0.06, "simulation_cpu_time_sec": 0.05}, "outside_process", True),
    ({"simulation_cgroup_cpu_time_sec": 0.0511, "simulation_cpu_time_sec": 0.046}, "outside_process", False),
    ({"simulation_cgroup_cpu_time_sec": 1.2, "simulation_cpu_time_sec": 1.1}, "outside_process", False),
    ({"simulation_time_samples": [0.1, 0.131, 0.11]}, "unstable_repeats", True),
    ({"simulation_time_samples": [0.1, 0.13, 0.11]}, "unstable_repeats", False),
    ({"simulation_time_samples": [0.1, 0.5]}, "unstable_repeats", False),
    ({"simulation_cpus": [0, 1], "cpu_environment": {"cpu_quota_cores": 1.0,
                                                     "cpu_max_mhz": {"0": 4000.0, "1": 5300.0}}},
     "mixed_cores", True),
    ({"simulation_cpus": [0, 1], "cpu_environment": {"cpu_quota_cores": 1.0,
                                                     "cpu_max_mhz": {"0": 4000.0, "1": 4400.0}}},
     "mixed_cores", False),
    ({"timing_samples": 1}, "single_timed_run", True),
    ({"timing_samples": None, "timing_repeats": 1}, "single_timed_run", True),
    ({"timing_samples": 0, "timing_repeats": 5, "simulation_time_samples": [0.1, 0.1]}, "single_timed_run", False),
    ({"exclusive": False, "concurrent_runs": 4}, "shared_dispatch", True),
    ({"exclusive": False, "concurrent_runs": 1}, "shared_dispatch", False),
    ({"overlapping_runs": 2}, "overlapping_runs", True),
    ({"server_overlapping_runs": 1}, "server_overlapping_runs", True),
    ({"cpu_environment": {"cpu_quota_cores": None}}, "no_cpu_quota", True),
    ({"cpu_environment": {}}, "no_cpu_quota", False),
    ({"image_identity": {"host_hypervisor_cpu_flag": True}}, "virtualised_host", True),
    ({"cpu_environment": {"cpu_quota_cores": 1.0, "cpu_model": "VirtualApple @ 2.50GHz"}}, "emulated_cpu", True),
    ({"runtime_environment": {"machine": "aarch64"}}, "non_x86_64", True),
    ({"image_identity": {"emulation": {"emulated": True, "image_arch": "x86_64", "host_arch": "aarch64"}}},
     "emulated_image", True),
    ({"image_identity": {"emulation": {"emulated": False, "image_arch": "x86_64", "host_arch": "x86_64"}}},
     "emulated_image", False),
    ({"image_identity": {"emulation": {"emulated": None, "image_arch": "x86_64", "host_arch": None}}},
     "emulated_image", False),
])
def test_per_result_rules(fields, code, expected):
    assert (code in _codes(_ok(**fields))) is expected


def test_each_caveat_names_its_fields_and_detail():
    caveats = {c["code"]: c for c in tc.result_caveats(_ok(
        simulation_time_samples=[0.1, 0.2, 0.15], simulation_cpus=[0, 1],
        cpu_environment={"cpu_quota_cores": 1.0, "cpu_max_mhz": {"0": 4000.0, "1": 5300.0}}))}
    assert caveats["unstable_repeats"]["detail"] == {"min_sec": 0.1, "max_sec": 0.2}
    assert caveats["mixed_cores"]["detail"] == {"classes_mhz": [[4000.0], [5300.0]]}
    assert caveats["mixed_cores"]["fields"] == ["simulation_cpus", "cpu_environment.cpu_max_mhz"]
    assert caveats["unstable_repeats"]["text"] == tc.TEXT["unstable_repeats"]


def test_report_level_rules():
    results = [_ok("a", timing_samples=1, server_overlapping_runs=2),
               _ok("b", timing_samples=3, cpu_environment={"cpu_quota_cores": 0.5,
                                                           "cpu_max_mhz": {"0": 4000.0}}),
               {"simulator": "c", "error": "boom", "timing_samples": 1}]
    report = {c["code"]: c for c in tc.summarize((r["simulator"], r) for r in results)}
    assert "single_timed_run" not in report
    assert "server_overlapping_runs" not in report
    assert report["cross_backend_core_speeds"]["detail"] == {"classes_mhz": [[4000.0], [5300.0]]}
    assert "cross_backend_cpu_quota" in report
    results[1]["exclusive"] = False
    results[1]["timing_samples"] = 1
    report = {c["code"]: c for c in tc.summarize((r["simulator"], r) for r in results)}
    assert report["single_timed_run"]["backends"] == ["a", "b"]
    assert report["server_overlapping_runs"]["backends"] == ["a"]


def test_annotate_and_combine():
    a = {"raw_results": [_ok("qiskit", overlapping_runs=1)]}
    b = {"raw_results": [_ok("cirq", overlapping_runs=2, timing_samples=1)]}
    tc.annotate(a)
    tc.annotate(b)
    assert a["timing_caveats_version"] == tc.TIMING_CAVEATS_VERSION
    assert [c["code"] for c in a["raw_results"][0]["timing_caveats"]] == ["overlapping_runs"]
    combined = {c["code"]: c for c in tc.combine([a["timing_caveats"], b["timing_caveats"], None])}
    assert combined["overlapping_runs"]["backends"] == ["qiskit", "cirq"]
    assert combined["single_timed_run"]["backends"] == ["cirq"]


def test_endpoint_derives_caveats_for_older_reports():
    app = FastAPI()
    app.state.limiter = limiter
    register_error_handlers(app)
    app.include_router(timing.router)
    client = TestClient(app)
    body = client.post("/timing-caveats", json={"raw_results": [
        _ok("a", simulation_throttled_sec=0.01), {"simulator": "b", "error": "x"}]}).json()
    assert [c["code"] for c in body["results"][0]] == ["throttled"]
    assert body["results"][1] == []
    assert [c["code"] for c in body["report"]] == ["throttled"]
    assert body["report"][0]["backends"] == ["a"]
    assert body["version"] == tc.TIMING_CAVEATS_VERSION
    junk = client.post("/timing-caveats", json={"raw_results": [{"simulation_time_samples": 3,
                                                                 "cpu_environment": "x",
                                                                 "simulation_cpus": {"a": 1}}]})
    assert junk.status_code == 200
    assert client.post("/timing-caveats", json={"raw_results": "x"}).status_code == 422


def test_run_completeness_statements():
    rec = report_provenance.run_completeness("completed", 3, 3, 2)
    assert report_provenance.completeness_statement({"run_completeness": rec}, True)[0] == "complete"
    rec = report_provenance.run_completeness("completed", 5, 3, 3)
    value, text = report_provenance.completeness_statement({"run_completeness": rec}, True)
    assert value == "partial" and "3 of 5 planned" in text
    rec = report_provenance.run_completeness("failed", 1, 1, 0, "All 1 task(s) failed")
    value, text = report_provenance.completeness_statement({"run_completeness": rec}, True)
    assert value == "failed" and "All 1 task(s) failed" in text
    assert report_provenance.completeness_statement({}, True)[0] == "not_recorded"
    value, text = report_provenance.completeness_statement({"run_completeness": rec}, False)
    assert value == "not_checked" and "expired" in text and "as supplied" in text


QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\nh q[0];\n'


def _crate(report, route):
    payload = SimpleNamespace(include_statevectors=False, author_name=None, author_affiliation=None,
                              publication_artifacts=None, name=None, circuit_name=None)
    ctx = build_export_context(report, payload, route)
    zf = zipfile.ZipFile(io.BytesIO(build_ro_crate(ctx)))
    top = crate_name(ctx)
    files = {n[len(top) + 1:]: zf.read(n) for n in zf.namelist()}
    graph = {e["@id"]: e for e in json.loads(files["ro-crate-metadata.json"])["@graph"]}
    return graph, json.loads(files["provenance.json"])


def test_crate_carries_caveats_and_completeness():
    report = {"input_qasm": QASM, "raw_results": [_ok("qiskit", statevector=[1, 0], overlapping_runs=1)],
              "run_completeness": report_provenance.run_completeness("completed", 1, 1, 1)}
    tc.annotate(report)
    graph, prov = _crate(report, "server_job")
    assert graph["#timing-caveats"]["value"] == "overlapping_runs"
    assert graph["#run-completeness"]["value"] == "complete"
    root = graph["./"]
    assert {"@id": "#timing-caveats"} in root["additionalProperty"]
    assert {"@id": "#run-completeness"} in root["additionalProperty"]
    assert "Run completeness" not in root["description"]
    assert prov["timing_caveats_derived_at_export"] is False
    assert prov["run_completeness_record"]["planned_tasks"] == 1


def test_crate_of_an_older_report_derives_caveats_and_says_completeness_is_not_recorded():
    graph, prov = _crate({"input_qasm": QASM, "raw_results": [_ok("qiskit", statevector=[1, 0],
                                                                  timing_samples=1)]}, "server_job")
    assert graph["#timing-caveats"]["value"] == "single_timed_run"
    assert "Derived at export" in graph["#timing-caveats"]["description"]
    assert graph["#run-completeness"]["value"] == "not_recorded"
    assert "Run completeness: not_recorded" in graph["./"]["description"]
    assert prov["timing_caveats_derived_at_export"] is True


def test_a_fallback_crate_says_completeness_was_not_checked():
    graph, _ = _crate({"input_qasm": QASM, "raw_results": [_ok("qiskit", statevector=[1, 0])]},
                      "client_request")
    assert graph["#run-completeness"]["value"] == "not_checked"
    assert "Run completeness: not_checked" in graph["./"]["description"]


def test_a_partial_playlist_crate_says_so():
    tasks = [{"task_name": "a", "input_qasm": QASM, "raw_results": [_ok("qiskit", statevector=[1, 0])]}]
    report = {"mode": "statevector", "benchmark_summary": tasks,
              "run_completeness": report_provenance.run_completeness("completed", 4, 1, 1)}
    graph, _ = _crate(report, "server_job")
    assert graph["#run-completeness"]["value"] == "partial"
    assert "1 of 4 planned" in graph["./"]["description"]


@requires_node
def test_the_page_shows_the_servers_tags_only():
    throttled = _ok(simulation_throttled_sec=0.05)
    tagged = {**throttled, "timing_caveats": tc.result_caveats(throttled)}
    untagged = {**throttled, "timing_caveats": []}
    unstable = _ok(simulation_time_samples=[0.1, 0.2, 0.15])
    unstable["timing_caveats"] = tc.result_caveats(unstable)
    out = call_js(["render_helpers.js"], [
        ("throttleText", [tagged]), ("throttleText", [untagged]), ("throttleText", [throttled]),
        ("unstableText", [unstable]), ("outsideProcessText", [tagged]),
    ])
    assert out[0].startswith("held by the CPU quota for 0.0500 s (50% of the simulation window)")
    assert out[1] is None and out[2] is None
    assert out[3].startswith("timed runs ranged from 0.1000 to 0.2000 s (2.00×)")
    assert out[4] is None


def test_the_page_has_no_copy_of_the_tag_rules():
    js = "\n".join((_JS / name).read_text() for name in ("render_helpers.js", "ranking_renderer.js"))
    for rule in ("THROTTLE_SHOWN_SHARE", "OUTSIDE_PROCESS_SHOWN_SEC", "UNSTABLE_SPREAD", "coreClasses(",
                 "simulationCoreSpeeds", "0.1 * cg", "* 1.1"):
        assert rule not in js, rule
