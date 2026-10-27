"""Evaluation of self-test jobs: correct backends pass, and the self-test FAILs when every
backend agrees on the same wrong state or the same wrong counts key (the §3.4 cases where
pairwise agreement could not see the error), on plan deviations and on vessel problems."""
import asyncio
import copy
import re

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from qrosetta_commons.helpers import THREAD_ENV_VARS, encode_statevector
from services.selftest import reference
from services.selftest.circuits import CIRCUITS, circuit_text
from services.selftest.evaluate import NotSelftestJob, evaluate_report, evaluate_task
from services.selftest.plan import N_SHOTS, SEED, THRESHOLDS

BACKENDS = ("qiskit", "cirq", "qsim-cirq")


def _registered(key, field, part):
    """The runner registry's ``field`` of ``key`` for ``part`` (statevector or measured)."""
    from config import settings
    return settings.get_runner_services()[key][field][part]
SV = [n for n, p, *_ in CIRCUITS if p == "statevector"]
MEASURED = [n for n, p, *_ in CIRCUITS if p == "measured"]


def _environment(**cpu):
    return {"cpu_environment": {"cpu_quota_cores": 1.0, "memory_limit_mib": 1024.0,
                                "cpu_model": "Intel(R) Xeon(R)", **cpu},
            "thread_env": {name: "1" for name in THREAD_ENV_VARS}, "memory_method": "vmhwm"}


def _sv_result(key, state_lsb, ordering=None, encode_as=None):
    ordering = ordering or _registered(key, "qubit_ordering", "statevector")
    precision = _registered(key, "precision", "statevector")
    state = reference.to_msb(state_lsb) if (encode_as or ordering) == "msb" else np.asarray(state_lsb)
    if precision == "complex64":
        state = state.astype(np.complex64)
    return {"simulator": key, "dispatch_status": "ok", "qubit_ordering": ordering,
            "precision": precision, "statevector": encode_statevector(np.asarray(state, dtype=complex)),
            "optimization_level": 0, **_environment()}


def _task(name, results, **fields):
    task = {"input_qasm": circuit_text(name), "task_name": f"{name} (3q)",
            "optimization_level": 0, "apply_preprocessing": True, "timing_repeats": 1,
            "runner_config": {}, "agreement_thresholds": dict(THRESHOLDS),
            "resolved_runners": {"requested": sorted({r["simulator"] for r in results})},
            "raw_results": results}
    if name.startswith("m_"):
        task.update(n_shots=N_SHOTS, seed=SEED)
    task.update(fields)
    return task


def _sv_report(state_of=None, result=_sv_result, circuit="sv_distinct_amplitudes"):
    """Every backend returns the reference state, except ``state_of(text)`` for ``circuit``."""
    tasks = []
    for name in SV:
        text = circuit_text(name)
        state = state_of(text) if state_of is not None and name == circuit else reference.statevector(text)
        tasks.append(_task(name, [result(k, state) for k in BACKENDS]))
    return {"mode": "statevector", "benchmark_summary": tasks}


def _counts_of(name, ordering):
    text = circuit_text(name)
    if name == "m_ghz_3q":
        return {"000": N_SHOTS // 2, "111": N_SHOTS - N_SHOTS // 2}
    return {reference.deterministic_counts_key(text)[ordering]: N_SHOTS}


def _m_result(key, counts):
    return {"simulator": key, "dispatch_status": "ok",
            "qubit_ordering": _registered(key, "qubit_ordering", "measured"),
            "precision": _registered(key, "precision", "measured"), "counts": counts, "optimization_level": 0,
            **_environment()}


def _m_report(counts_of=_counts_of):
    tasks = [_task(name, [_m_result(k, counts_of(name, _registered(k, "qubit_ordering", "measured"))) for k in BACKENDS])
             for name in MEASURED]
    return {"mode": "measured", "seed": SEED, "benchmark_summary": tasks}


def evaluate(report):
    report = copy.deepcopy(report)
    return evaluate_report({**report, "benchmark_summary": [evaluate_task(t) for t in report["benchmark_summary"]]}, "job")


def _failed(result, check=None):
    return [r for r in result["plan"] + result["known_answer"] + result["environment_checks"]
            if r["status"] == "FAIL" and (check is None or r["check"] == check)]


def test_correct_backends_pass_in_both_orders_and_precisions():
    for report in (_sv_report(), _m_report()):
        result = evaluate(report)
        assert result["status"] == "PASS", _failed(result)
        assert set(result["backends"]) == set(BACKENDS)
    sv = evaluate(_sv_report())
    worst = max(r["infidelity"] for r in sv["known_answer"])
    assert worst < 1e-12
    skipped = {r["check"] for r in sv["environment_checks"] if r["status"] == "SKIP"}
    assert skipped == {"host_virtualisation", "host_emulation", "provenance"}
    for report in (_sv_report(), _m_report()):
        rows = [r for r in evaluate(report)["environment_checks"] if r["check"] in ("precision", "qubit_ordering")]
        assert len(rows) == 2 * len(BACKENDS) and all(r["status"] == "PASS" for r in rows), rows


def _lsb_permuted(state, permutation):
    n = int(np.log2(len(state)))
    return state.reshape([2] * n).transpose(permutation).reshape(-1)


def _gates_variant(text, edit):
    circuit = reference.parse_circuit(text)
    return reference.simulate_gates(circuit["n_qubits"], edit(list(circuit["gates"])))


def _flip_rz(gates):
    return [(g, (-p[0],), q) if g == "rz" else (g, p, q) for g, p, q in gates]


def _flip_first_cx(gates):
    i = next(i for i, g in enumerate(gates) if g[0] == "cx")
    gates[i] = (gates[i][0], gates[i][1], gates[i][2][::-1])
    return gates


WRONG_STATES = {
    "qubit permutation": lambda text: _lsb_permuted(reference.statevector(text), (1, 0, 2)),
    "bit reversal": lambda text: reference.to_msb(reference.statevector(text)),
    "rz sign flipped": lambda text: _gates_variant(text, _flip_rz),
    "cx control and target swapped": lambda text: _gates_variant(text, _flip_first_cx),
    "rz deleted (rx(1e308) read as rx(0))": lambda text: _gates_variant(text, lambda g: [x for x in g if x[0] != "rz"]),
    "cx deleted (gate read as a barrier)": lambda text: _gates_variant(text, lambda g: g[:3] + g[4:]),
}


def _pairs_agree(results) -> bool:
    pytest.importorskip("pytket")
    from services.aggregator import compile_comparison_reports
    from services.analysis.divergence.verdicts import pair_verdict
    divergence, _, _ = asyncio.run(compile_comparison_reports(copy.deepcopy(results), dict(THRESHOLDS)))
    pairs = divergence["pairwise_agreement"]
    return bool(pairs) and all(pair_verdict(p)["agrees"] for p in pairs)


@pytest.mark.parametrize("kind", sorted(WRONG_STATES))
def test_every_backend_agreeing_on_a_wrong_state_fails(kind):
    report = _sv_report(state_of=WRONG_STATES[kind])
    task = next(t for t in report["benchmark_summary"] if t["input_qasm"] == circuit_text("sv_distinct_amplitudes"))
    assert _pairs_agree(task["raw_results"]), "the pairwise analysis should see full agreement"
    result = evaluate(report)
    assert result["status"] == "FAIL"
    failed = {(r["backend"], r["circuit"]) for r in _failed(result, "statevector")}
    assert failed == {(k, "sv_distinct_amplitudes") for k in BACKENDS}
    for row in _failed(result, "statevector"):
        assert row["infidelity"] > 1e-2


def test_every_backend_declaring_the_wrong_order_fails_on_one_hot():
    def mislabelled(key, state):
        declared = _registered(key, "qubit_ordering", "statevector")
        return _sv_result(key, state, ordering=declared, encode_as="lsb" if declared == "msb" else "msb")
    result = evaluate(_sv_report(result=mislabelled))
    failed = {(r["backend"], r["circuit"]) for r in _failed(result, "statevector")}
    assert {(k, "sv_one_hot_idle") for k in BACKENDS} <= failed


def test_every_backend_returning_all_zeros_or_dropping_idle_qubits_fails():
    zeros = evaluate(_sv_report(state_of=lambda text: reference.statevector(text) * 0 + np.eye(8)[0]))
    assert {r["backend"] for r in _failed(zeros, "statevector")} == set(BACKENDS)
    report = _sv_report()
    for task in report["benchmark_summary"]:
        if task["input_qasm"] == circuit_text("sv_one_hot_idle"):
            for r in task["raw_results"]:
                r["statevector"] = encode_statevector(np.array([0, 1], dtype=complex))
    dropped = evaluate(report)
    assert all("amplitudes, expected 8" in r["reason"] for r in _failed(dropped, "statevector"))


def _with(report, name, edit):
    report = copy.deepcopy(report)
    for task in report["benchmark_summary"]:
        if task.get("input_qasm") == circuit_text(name):
            for r in task["raw_results"]:
                edit(r)
    return report


WRONG_KEYS = {
    "keys bit-reversed": ("m_probe_clbit_order", lambda r: r.update(counts={"10" if r["qubit_ordering"] == "lsb" else "01": N_SHOTS})),
    "cregs in alphabetical order": ("m_probe_creg_declaration_order", lambda r: r.update(counts={"10" if r["qubit_ordering"] == "lsb" else "01": N_SHOTS})),
    "keys over qubits, not classical bits": ("m_probe_unmeasured_clbit_first_creg", lambda r: r.update(counts={"10" if r["qubit_ordering"] == "lsb" else "01": N_SHOTS})),
    "register spaces kept": ("m_probe_unmeasured_clbit_mid_creg", lambda r: r.update(counts={"101 0" if r["qubit_ordering"] == "lsb" else "0 101": N_SHOTS})),
    "shots lost": ("m_probe_one_hot", lambda r: r.update(counts={k: v - 1 for k, v in r["counts"].items()})),
    "GHZ all zeros (sampler cutoff)": ("m_ghz_3q", lambda r: r.update(counts={"000": N_SHOTS})),
    "GHZ biased 0.76/0.24": ("m_ghz_3q", lambda r: r.update(counts={"000": 6232, "111": N_SHOTS - 6232})),
    "GHZ outside support": ("m_ghz_3q", lambda r: r.update(counts={"000": 4000, "111": 4000, "011": 200})),
}


@pytest.mark.parametrize("kind", sorted(WRONG_KEYS))
def test_every_backend_agreeing_on_wrong_counts_fails(kind):
    name, edit = WRONG_KEYS[kind]
    result = evaluate(_with(_m_report(), name, edit))
    assert result["status"] == "FAIL"
    assert {(r["backend"], r["circuit"]) for r in _failed(result) if r["backend"]} == {(k, name) for k in BACKENDS}


def test_ghz_balance_inside_six_sigma_passes():
    edit = lambda r: r.update(counts={"000": 4100 + 250, "111": 4100 - 250})  # noqa: E731
    assert evaluate(_with(_m_report(), "m_ghz_3q", edit))["status"] == "PASS"


@pytest.mark.parametrize("field,value,check", [
    ("optimization_level", 1, "plan"), ("apply_preprocessing", False, "plan"),
    ("agreement_thresholds", {**THRESHOLDS, "fidelity_tolerance": 0.5}, "plan"),
])
def test_plan_deviations_fail(field, value, check):
    report = _sv_report()
    report["benchmark_summary"][1][field] = value
    assert _failed(evaluate(report), check)


def test_measured_seed_and_shots_deviations_fail():
    report = _m_report()
    report["seed"] = 1
    report["benchmark_summary"][0]["n_shots"] = 100
    reasons = " ".join(r["reason"] for r in _failed(evaluate(report), "plan"))
    assert "master seed" in reasons and "n_shots" in reasons


def test_missing_extra_and_failed_circuits_or_backends_fail():
    report = _sv_report()
    del report["benchmark_summary"][2]
    report["benchmark_summary"].append({**report["benchmark_summary"][0], "input_qasm": "OPENQASM 2.0;\nqreg q[1];\n",
                                        "task_name": "other"})
    reasons = " ".join(r["reason"] for r in _failed(evaluate(report), "plan"))
    assert "not run: sv_ghz_3q" in reasons and "'other'" in reasons

    report = _sv_report()
    task = report["benchmark_summary"][0]
    task["resolved_runners"]["requested"].append("qulacs")
    task["raw_results"][1] = {"simulator": "cirq", "dispatch_status": "timeout", "error": "TIMEOUT (120s)"}
    failed = {(r["backend"], r["reason"][:7]) for r in _failed(evaluate(report))}
    assert ("qulacs", "no resu") in failed and ("cirq", "timeout") in failed


def test_a_job_that_is_not_a_selftest_is_refused():
    with pytest.raises(NotSelftestJob):
        evaluate_report({"raw_results": []})
    with pytest.raises(NotSelftestJob):
        evaluate({"mode": "statevector", "benchmark_summary": [
            {"input_qasm": 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\nx q[0];\n', "raw_results": []}]})


def _env_report(**fields):
    report = _sv_report()
    for task in report["benchmark_summary"]:
        for r in task["raw_results"]:
            for key, value in fields.items():
                if key.startswith("cpu_"):
                    r["cpu_environment"][key[4:]] = value
                else:
                    r[key] = value
    return report


@pytest.mark.parametrize("fields,check,status", [
    ({"cpu_cpu_quota_cores": None}, "cpu_quota_cores", "FAIL"),
    ({"cpu_cpu_quota_cores": 0.5}, "cpu_quota_cores", "FAIL"),
    ({"thread_env": {name: None for name in THREAD_ENV_VARS}}, "thread_env", "FAIL"),
    ({"memory_method": "sampled_10ms"}, "memory_method", "WARN"),
    ({"cpu_memory_limit_mib": None}, "memory_limit_mib", "WARN"),
    ({"image_identity": {"source": "release", "git_sha": "abc1234", "host_hypervisor_cpu_flag": True}},
     "host_virtualisation", "WARN"),
    ({"image_identity": {"source": "release", "git_sha": "abc1234", "host_hypervisor_cpu_flag": False}},
     "host_virtualisation", "PASS"),
    ({"cpu_cpu_model": "VirtualApple @ 2.50GHz processor"}, "host_emulation", "FAIL"),
    ({"cpu_emulation": True}, "host_emulation", "FAIL"),
    ({"image_identity": {"source": "release", "git_sha": "abc1234"}}, "provenance", "PASS"),
    ({"image_identity": {"source": "built_locally", "git_sha": "abc1234"}}, "provenance", "WARN"),
    ({"image_source": "pulled-other", "image_git_sha": "abc1234"}, "provenance", "WARN"),
    ({"image_identity": {"source": "not recorded", "git_sha": "not recorded"}}, "provenance", "FAIL"),
    ({"image_identity": {"source": "built_locally", "git_sha": "abc1234-dirty"}}, "provenance", "FAIL"),
])
def test_environment_checks(fields, check, status):
    result = evaluate(_env_report(**fields))
    rows = [r for r in result["environment_checks"] if r["check"] == check]
    assert {r["status"] for r in rows} == {status}, rows
    assert result["status"] == ("PASS" if status == "PASS" else status)
    if check == "host_virtualisation" and status == "WARN":
        assert result["caveats"] and all(r["status"] == "PASS" for r in result["known_answer"])


def test_registry_order_and_precision_are_checked_per_mode(monkeypatch):
    from config import settings
    real = settings.get_runner_services()
    assert _registered("cirq", "precision", "statevector") != _registered("cirq", "precision", "measured")
    sv, measured = _sv_report(), _m_report()

    def registry(edit):
        out = copy.deepcopy(real)
        edit(out)
        return out
    monkeypatch.setattr(type(settings), "get_runner_services",
                        lambda self: registry(lambda r: r["qiskit"]["qubit_ordering"].update(statevector="msb")))
    result = evaluate(sv)
    assert {r["backend"] for r in _failed(result, "statevector")} == {"qiskit"}
    assert {r["backend"] for r in _failed(result, "qubit_ordering")} == {"qiskit"}
    assert evaluate(measured)["status"] == "PASS"
    monkeypatch.setattr(type(settings), "get_runner_services",
                        lambda self: registry(lambda r: r["cirq"]["precision"].update(measured="complex128")))
    assert {r["backend"] for r in _failed(evaluate(measured), "precision")} == {"cirq"}
    assert evaluate(sv)["status"] == "PASS"
    monkeypatch.setattr(type(settings), "get_runner_services",
                        lambda self: registry(lambda r: r["qsim-cirq"].update(precision={"statevector": None, "measured": None})))
    rows = [r for r in evaluate(sv)["environment_checks"] if r["check"] == "precision"]
    assert {r["backend"]: r["status"] for r in rows}["qsim-cirq"] == "SKIP"


@pytest.fixture
def route_client(monkeypatch, tmp_path):
    pytest.importorskip("pytket")
    import services.job_manager as job_manager
    from routers import selftest
    from routers.errors import register_error_handlers
    from services import job_store
    from services.security import limiter
    monkeypatch.setattr(job_store, "SPILL_DIR", str(tmp_path / "spill"))
    monkeypatch.setattr(limiter, "enabled", False)
    app = FastAPI()
    app.state.limiter = limiter
    register_error_handlers(app)
    app.include_router(selftest.router)
    yield TestClient(app), job_manager
    for job_id in [j for j in job_manager.ACTIVE_JOBS if str(j).startswith("st-")]:
        job_manager.ACTIVE_JOBS.pop(job_id, None)


def test_route_evaluates_a_finished_job(route_client):
    client, job_manager = route_client
    job_manager.ACTIVE_JOBS["st-sv"] = job_manager._completed_job("local", _sv_report(), {})
    job_manager.ACTIVE_JOBS["st-wrong"] = job_manager._completed_job(
        "local", _sv_report(state_of=WRONG_STATES["bit reversal"]), {})
    job_manager.ACTIVE_JOBS["st-single"] = job_manager._completed_job("local", {"raw_results": []}, {})
    body = client.get("/jobs/st-sv/selftest-result").json()
    assert body["status"] == "PASS" and body["report_source"] == "server_job" and body["part"] == "statevector"
    assert client.get("/jobs/st-wrong/selftest-result").json()["status"] == "FAIL"
    assert client.get("/jobs/st-single/selftest-result").status_code == 409
    assert client.get("/jobs/st-none/selftest-result").status_code == 404
    plan = client.get("/selftest").json()
    assert [j["part"] for j in plan["jobs"]] == ["statevector", "measured"]


def _decimal_pi(qasm):
    return re.sub(r"\(([-0-9.eE+]+)\*pi\)", lambda m: f"({float(m.group(1)) * np.pi!r})", qasm)


def _fake_runner(bit_reverse_cirq=False):
    async def dispatch(runner_urls, runner_payload=None, timeout_seconds=None, runner_statuses=None):
        qasm = _decimal_pi(runner_payload["circuit_data"])
        circuit = reference.parse_circuit(qasm)
        state = reference.simulate_gates(circuit["n_qubits"], circuit["gates"])
        out = []
        for key, url in runner_urls.items():
            ordering = _registered(key, "qubit_ordering", "statevector" if url.endswith("/run") else "measured")
            if url.endswith("/run"):
                wrong = bit_reverse_cirq and key == "cirq"
                out.append(_sv_result(key, state, encode_as="lsb" if wrong else None))
                continue
            rng = np.random.default_rng(runner_payload["seed"])
            draws = rng.choice(len(state), size=runner_payload["n_shots"], p=np.abs(state) ** 2)
            counts = {}
            for index in draws:
                bits = [0] * circuit["n_clbits"]
                for qubit, clbit in circuit["measures"]:
                    bits[clbit] = (int(index) >> qubit) & 1
                key_text = "".join(map(str, reversed(bits)))
                key_text = key_text if ordering == "lsb" else key_text[::-1]
                counts[key_text] = counts.get(key_text, 0) + 1
            out.append(_m_result(key, counts))
        return out
    return dispatch


@pytest.mark.parametrize("bit_reverse_cirq", [False, True])
def test_plan_runs_through_the_batch_route_and_evaluates(monkeypatch, tmp_path, bit_reverse_cirq):
    pytest.importorskip("pytket")
    import routers.benchmark as benchmark
    import services.job_manager as job_manager
    from routers import selftest
    from routers.errors import register_error_handlers
    from services import job_store, prep_worker
    from services.security import limiter

    async def available(_targets):
        return None
    monkeypatch.setattr(job_store, "SPILL_DIR", str(tmp_path / "spill"))
    monkeypatch.setattr(limiter, "enabled", False)
    monkeypatch.setattr(prep_worker, "IN_PROCESS", True)
    monkeypatch.setattr(benchmark, "require_available", available)
    monkeypatch.setattr(job_manager, "dispatch_to_runners", _fake_runner(bit_reverse_cirq))
    app = FastAPI()
    app.state.limiter = limiter
    register_error_handlers(app)
    app.include_router(benchmark.router)
    app.include_router(selftest.router)
    client = TestClient(app)
    statuses = {}
    for job in client.get("/selftest").json()["jobs"]:
        posted = client.post(job["endpoint"], json={**job["request"], "target_simulators": list(BACKENDS)})
        assert posted.status_code == 200, posted.text
        job_id = posted.json()["job_id"]
        body = client.get(f"/jobs/{job_id}/selftest-result").json()
        statuses[job["part"]] = body
        job_manager.ACTIVE_JOBS.pop(job_id, None)
    assert statuses["measured"]["status"] == "PASS", _failed(statuses["measured"])
    if bit_reverse_cirq:
        assert statuses["statevector"]["status"] == "FAIL"
        assert {r["backend"] for r in _failed(statuses["statevector"])} == {"cirq"}
    else:
        assert statuses["statevector"]["status"] == "PASS", _failed(statuses["statevector"])
