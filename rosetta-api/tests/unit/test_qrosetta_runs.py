"""qrosetta run, wait, jobs, show summary, export and selftest against a scripted server (no
server dependencies): the results layout and STATUS, exit codes by outcome role, --set and
--request through POST /plan, Ctrl-C, sequential multi-job plans, and no measurement setting
from the config or the environment."""

import json
import os
import signal

import pytest

from tests.unit._qrosetta_scripted import ROLES, Scripted, _json, summary

from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.client import outcomes, refs, results, runplan, waiting  # noqa: E402
from qrosetta_cli.client.transport import Response  # noqa: E402
from qrosetta_cli.errors import CliError, Exit  # noqa: E402

from tests.unit.test_qrosetta_contracts import validate_envelope  # noqa: E402

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'


@pytest.fixture(autouse=True)
def no_pause(monkeypatch):
    monkeypatch.setattr(waiting, "pause", lambda seconds: None)


@pytest.fixture
def env(tmp_path):
    return {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_CONFIG_HOME": str(tmp_path / "cfg"),
            "XDG_RUNTIME_DIR": str(tmp_path / "run"), "QROSETTA_RESULTS_DIR": str(tmp_path / "res")}


@pytest.fixture
def circuit(tmp_path):
    path = tmp_path / "bell.qasm"
    path.write_text(QASM)
    return str(path)


def run(argv, env, server):
    return main(argv, env=env, transport_factory=server)


def envelope(capsys):
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    return doc


def invocations(env):
    root = env["QROSETTA_RESULTS_DIR"]
    return sorted(os.path.join(root, d) for d in os.listdir(root) if d != "latest")


def test_single_run_layout_status_last_and_latest(env, circuit, capsys):
    server = Scripted()
    assert run(["run", circuit, "--json"], env, server) == 0
    doc = envelope(capsys)
    (inv,) = invocations(env)
    assert os.path.basename(inv).endswith("-bell") and os.path.isabs(inv)
    assert os.path.realpath(os.path.join(env["QROSETTA_RESULTS_DIR"], "latest")) == inv
    (job,) = doc["data"]["jobs"]
    assert job["dir"] == os.path.join(inv, f"statevector-{job['job_id'][:8]}") and os.path.isabs(job["dir"])
    files = sorted(os.listdir(job["dir"]))
    assert files == ["SHA256SUMS", "STATUS", "job.json", "report.json", "request.json", "summary.json"]
    assert results.read_status(job["dir"]) == "complete" and job["save_status"] == "complete"
    sums = open(os.path.join(job["dir"], "SHA256SUMS")).read().splitlines()
    assert [line.split("  ")[1] for line in sums] == ["job.json", "report.json", "request.json", "summary.json",
                                                      "../plan.json"]
    plan = json.load(open(os.path.join(inv, "plan.json")))
    assert plan["schema"] == "qrosetta.cli/plan@1" and plan["job_dirs"] == [os.path.basename(job["dir"])]
    assert plan["results_dir"] == inv and plan["server"]["platform_version"] == "2.0.0"
    request = json.load(open(os.path.join(job["dir"], "request.json")))
    assert request["payload"] == server.jobs[job["job_id"]]["payload"]
    assert request["sources"]["qasm_string"] == "circuit"
    assert request["sources"]["apply_preprocessing"] == "server_default"
    assert request["sources"]["n_shots"] == "server_default" and request["server_defaults"]["timing_repeats"] == 1
    assert doc["outcome"] == {"rule_version": "divergence-test.1", "fail_on": [], "matched": []}
    assert job["summary"] == summary(agrees=3)
    assert "Authorization" not in json.dumps(request)


def test_status_is_written_last(env, circuit, monkeypatch):
    seen = []
    original = results.write_status

    def spy(job_dir, token):
        seen.append(sorted(os.listdir(job_dir)))
        original(job_dir, token)

    monkeypatch.setattr(results, "write_status", spy)
    assert run(["run", circuit], env, Scripted()) == 0
    assert seen and "STATUS" not in seen[0] and "SHA256SUMS" in seen[0] and "job.json" in seen[0]


def test_crate_on_request_and_the_local_note_without_gated_saves(env, circuit, capsys):
    assert run(["run", circuit], env, Scripted()) == 0
    out, err = capsys.readouterr()
    assert "no gated saves" in err and "export crate --result job:" in out
    assert run(["run", circuit, "--crate"], env, Scripted()) == 0
    job_dir = [d for d in results.job_dirs(invocations(env)[-1])][0]
    assert os.path.isfile(os.path.join(job_dir, "ro-crate.zip"))
    assert json.load(open(os.path.join(job_dir, "job.json")))["concurrent_with_other_jobs"] is False


def test_remote_server_saves_report_and_summary_and_records_concurrency(env, circuit, capsys):
    server = Scripted(local=False)
    server.config["exclusive"]["shared_running"] = 2
    assert run(["run", circuit, "--crate", "--server", "https://q.example.org"], env, server) == 0
    job_dir = results.job_dirs(invocations(env)[0])[0]
    record = json.load(open(os.path.join(job_dir, "job.json")))
    assert record["concurrent_with_other_jobs"] is True
    assert "no gated saves" not in capsys.readouterr().err


def test_gated_saves_defer_the_crate_and_wait_finishes_it(env, circuit, capsys, monkeypatch):
    server = Scripted(features={"gated_saves": 1})
    gate = {"busy": True}
    original = server.request

    def request(method, path, query=None, body=None, headers=None, timeout=None):
        if method == "POST" and path.startswith("/jobs/") and path.endswith("/export"):
            server.log.append((method, path, query))
            if query == {"gated": "true"} and gate["busy"]:
                return _json(409, {"detail": "gate_busy"}, {"retry-after": "5"})
            return Response(200, {"content-type": "application/zip"}, b"PK")
        return original(method, path, query, body, headers, timeout)

    server.request = request
    ticks = iter(range(0, 100_000, 10))
    monkeypatch.setattr(waiting, "clock", lambda: next(ticks))
    assert run(["run", circuit], env, server) == 0
    job_dir = results.job_dirs(invocations(env)[0])[0]
    assert results.read_status(job_dir) == "crate-deferred"
    out = capsys.readouterr().out
    assert "Crate: deferred until the server is idle" in out and "qrosetta wait job:" in out
    assert any(q == {"gated": "true"} for m, p, q in server.log if p.endswith("/report"))
    assert not os.path.exists(os.path.join(job_dir, "ro-crate.zip"))
    gate["busy"] = False
    assert run(["wait"], env, server) == 0
    assert results.read_status(job_dir) == "complete"
    record = json.load(open(os.path.join(job_dir, "job.json")))
    assert record["crate_deferred_since"] and record["crate_deferred_sec"] is not None
    assert record["concurrent_with_other_jobs"] is False
    assert os.path.isfile(os.path.join(job_dir, "ro-crate.zip"))


@pytest.mark.parametrize("counts, fail_on, code", [
    ({"differs": 1}, "differs", Exit.DISAGREEMENT),
    ({"differs_by_only": 1}, "differs-by-only", Exit.DISAGREEMENT),
    ({"inconclusive": 2}, "inconclusive", Exit.NOT_ESTABLISHED),
    ({"not_comparable": 1}, "not_comparable", Exit.NOT_ESTABLISHED),
    ({"no_comparison": 1}, "no_comparison", Exit.NOT_ESTABLISHED),
    ({"runs_without_output": 1}, "runs_without_output", Exit.RUNS_WITHOUT_OUTPUT),
    ({"differs": 1, "inconclusive": 1, "runs_without_output": 1}, "any", Exit.DISAGREEMENT),
    ({"inconclusive": 1, "runs_without_output": 1}, "inconclusive,runs_without_output", Exit.NOT_ESTABLISHED),
    ({"differs": 1}, "inconclusive", Exit.OK),
    ({"differs": 4}, "none", Exit.OK),
])
def test_exit_codes_follow_the_outcome_role(env, circuit, capsys, counts, fail_on, code):
    server = Scripted(summaries={"statevector": summary(**counts)})
    assert run(["run", circuit, "--fail-on", fail_on, "--json"], env, server) == code
    doc = envelope(capsys)
    expected = [n for n in outcomes.parse([fail_on]) if n != "any"]
    if fail_on == "any":
        expected = [n for n, r in ROLES.items() if r != "agreement"]
    assert doc["outcome"]["fail_on"] == expected and doc["outcome"]["rule_version"] == "divergence-test.1"
    assert sorted(doc["outcome"]["matched"]) == sorted(n for n in expected if counts.get(n))


def test_default_fail_on_is_none(env, circuit):
    server = Scripted(summaries={"statevector": summary(differs=3, runs_without_output=1)})
    assert run(["run", circuit], env, server) == 0


@pytest.mark.parametrize("final, code", [("failed", Exit.JOB_FAILED), ("cancelled", Exit.JOB_CANCELLED)])
def test_job_failed_and_cancelled(env, circuit, final, code):
    assert run(["run", circuit, "--fail-on", "differs"], env, Scripted(final=final)) == code
    job_dir = results.job_dirs(invocations(env)[0])[0]
    if final == "failed":
        assert results.read_status(job_dir) == "job-failed"


def test_wait_timeout_is_exit_7_with_the_job_running(env, circuit, capsys, monkeypatch):
    ticks = iter(range(0, 10_000, 30))
    monkeypatch.setattr(waiting, "clock", lambda: next(ticks))
    assert run(["run", circuit, "--wait-timeout", "1m", "--json"], env, Scripted(polls=100)) == Exit.WAIT_TIMEOUT
    doc = envelope(capsys)
    assert doc["error"] is None and doc["data"]["jobs"][0]["status"] == "running"
    assert results.read_status(doc["data"]["jobs"][0]["dir"]) is None


@pytest.mark.parametrize("names, code", [("no_such_outcome", Exit.INCOMPATIBLE), ("agrees", Exit.USAGE),
                                         ("none,differs", Exit.USAGE)])
def test_fail_on_names_are_checked_before_anything_runs(env, circuit, names, code):
    server = Scripted()
    assert run(["run", circuit, "--fail-on", names], env, server) == code
    assert "/plan" not in server.paths()


def test_fail_on_needs_a_server_that_publishes_outcomes(env, circuit):
    server = Scripted()
    del server.config["summary_outcomes"]
    assert run(["run", circuit, "--fail-on", "differs"], env, server) == Exit.INCOMPATIBLE
    assert run(["run", circuit], env, server) == 0


def test_outcome_priority():
    config = {"summary_outcomes": {"roles": ROLES}}
    names = outcomes.resolve(["any"], config)
    assert outcomes.evaluate(names, summary(inconclusive=1, runs_without_output=2), config)[0] == Exit.NOT_ESTABLISHED
    assert outcomes.evaluate(names, summary(runs_without_output=2), config)[0] == Exit.RUNS_WITHOUT_OUTPUT
    assert outcomes.evaluate(names, summary(agrees=3), config) == (Exit.OK, [])


def test_set_goes_through_plan_with_source_set(env, circuit):
    server = Scripted()
    server.fields.append("future_field")
    assert run(["run", circuit, "--set", "future_field={\"a\": 1}", "--shots", "5", "-m", "measured"], env,
               server) == 0
    (req,) = server.plans
    assert req["settings"]["future_field"] == {"value": {"a": 1}, "source": "set"}
    assert req["settings"]["n_shots"] == {"value": 5, "source": "flag"}
    request = json.load(open(os.path.join(results.job_dirs(invocations(env)[0])[0], "request.json")))
    assert request["sources"]["future_field"] == "set" and request["sources"]["n_shots"] == "flag"


@pytest.mark.parametrize("argv, code", [
    (["--set", "n_shots=5"], Exit.USAGE),
    (["--set", "apply_preprocessing=false"], Exit.USAGE),
    (["--set", "future_field=1", "--set", "future_field=2"], Exit.USAGE),
    (["--set", "unknown_to_server=1"], Exit.INCOMPATIBLE),
])
def test_set_refusals(env, circuit, argv, code):
    server = Scripted()
    server.fields.append("future_field")
    assert run(["run", circuit, *argv], env, server) == code
    assert "/plan" not in server.paths()


def test_a_flag_the_server_does_not_list_is_exit_12(env, circuit, capsys):
    server = Scripted()
    server.fields.remove("timing_repeats")
    assert run(["run", circuit, "--repeats", "3"], env, server) == Exit.INCOMPATIBLE
    assert "--repeats" in capsys.readouterr().err


def test_flags_become_settings_and_nothing_else(env, circuit, tmp_path):
    cfg = tmp_path / "cfg" / "qrosetta"
    cfg.mkdir(parents=True)
    (cfg / "config.toml").write_text('[results]\ndir = "%s"\n' % (tmp_path / "res"))
    noisy = dict(env, QROSETTA_SHOTS="7", QROSETTA_N_SHOTS="7", QROSETTA_SEED="1", QROSETTA_TIMEOUT="5")
    server = Scripted()
    assert run(["run", circuit, "-m", "measured"], noisy, server) == 0
    assert server.plans[0]["settings"] == {}
    server = Scripted()
    assert run(["run", circuit, "-m", "measured", "--shots", "100", "--seed", "4", "--timeout", "2m", "--repeats", "2",
                "--exclusive", "-O", "1", "-O", "qiskit=0,0,2", "-b", "qiskit,cirq", "--threshold",
                "js_threshold=0.02", "--order", "cirq=2"], env, server) == 0
    got = {k: v["value"] for k, v in server.plans[0]["settings"].items()}
    assert got == {"n_shots": 100, "seed": 4, "timeout_seconds": 120, "timing_repeats": 2, "exclusive": True,
                   "optimization_level": 1, "runner_config": {"qiskit": [0, 0, 2]},
                   "target_simulators": ["qiskit", "cirq"], "thresholds": {"js_threshold": 0.02},
                   "runner_phases": {"cirq": 2}}
    assert {v["source"] for v in server.plans[0]["settings"].values()} == {"flag"}


def test_backend_typos_get_a_suggestion(env, circuit, capsys):
    assert run(["run", circuit, "-b", "qiskti"], env, Scripted()) == Exit.USAGE
    assert "did you mean qiskit?" in capsys.readouterr().err


def test_two_modes_run_one_after_another_each_saved_first(env, circuit):
    server = Scripted(polls=2)
    assert run(["run", circuit, "-m", "statevector,measured", "--shots", "100"], env, server) == 0
    posts = [i for i, (m, p, _) in enumerate(server.log) if m == "POST" and p in ("/compare", "/compare_measured")]
    first_save = max(i for i, (m, p, _) in enumerate(server.log) if p.endswith("/summary") and i < posts[1])
    assert len(posts) == 2 and server.log[posts[0]][1] == "/compare" and first_save < posts[1]
    (inv,) = invocations(env)
    dirs = results.job_dirs(inv)
    assert [os.path.basename(d).split("-")[0] for d in dirs] == ["statevector", "measured"]
    assert all(results.read_status(d) == "complete" for d in dirs)


def test_detach_is_single_job_only_and_wait_saves(env, circuit, capsys):
    server = Scripted()
    assert run(["run", circuit, "-m", "statevector,measured", "--detach"], env, server) == Exit.USAGE
    assert not any(p in ("/compare", "/compare_measured") for p in server.paths("POST"))
    assert run(["run", circuit, "--detach", "--crate"], env, server) == 0
    job_dir = results.job_dirs(invocations(env)[0])[0]
    assert results.read_status(job_dir) is None
    assert not os.path.lexists(os.path.join(env["QROSETTA_RESULTS_DIR"], "latest"))
    out = capsys.readouterr().out
    assert "qrosetta wait job:" in out
    assert run(["jobs", "--json"], env, server) == 0
    doc = envelope(capsys)
    assert doc["data"]["jobs"][0]["save_status"] is None and doc["data"]["jobs"][0]["server_status"] == "done"
    assert run(["wait", "--json"], env, server) == 0
    doc = envelope(capsys)
    assert doc["data"]["jobs"][0]["save_status"] == "complete"
    assert os.path.isfile(os.path.join(job_dir, "ro-crate.zip"))
    assert os.path.realpath(os.path.join(env["QROSETTA_RESULTS_DIR"], "latest")) == invocations(env)[0]


def test_ctrl_c_while_waiting_detaches(env, circuit, capsys, monkeypatch):
    def interrupt(seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(waiting, "pause", interrupt)
    server = Scripted()
    assert run(["run", circuit, "-m", "statevector,measured", "--json"], env, server) == Exit.SIGINT
    doc = json.loads(capsys.readouterr().out)
    assert doc["error"]["reason"] == "detached" and doc["error"]["hint"].startswith("qrosetta wait job:")
    assert "1 planned job not submitted" in doc["error"]["message"]
    assert [p for p in server.paths("POST") if p.startswith("/compare")] == ["/compare"]
    job_dir = results.job_dirs(invocations(env)[0])[0]
    assert results.read_status(job_dir) is None
    monkeypatch.setattr(waiting, "pause", lambda s: None)
    assert run(["wait", doc["error"]["hint"].split()[-1]], env, server) == 0
    assert results.read_status(job_dir) == "complete"


def test_sigterm_while_waiting_detaches_with_143(env, circuit, monkeypatch):
    def term(seconds):
        os.kill(os.getpid(), signal.SIGTERM)

    monkeypatch.setattr(waiting, "pause", term)
    assert run(["run", circuit], env, Scripted()) == Exit.SIGTERM
    assert signal.getsignal(signal.SIGTERM) is signal.SIG_DFL


def test_sigint_during_submit_waits_for_the_answer():
    with waiting.submitting() as state:
        signal.raise_signal(signal.SIGINT)
    assert state["interrupted"] is True
    with pytest.raises(CliError) as err:
        with waiting.submitting():
            signal.raise_signal(signal.SIGINT)
            signal.raise_signal(signal.SIGINT)
    assert err.value.code == Exit.SIGINT and err.value.reason == "submit_interrupted"


def test_dry_run_sends_nothing_and_prints_the_plan(env, circuit, capsys):
    server = Scripted()
    assert run(["run", circuit, "--dry-run", "--json"], env, server) == 0
    doc = envelope(capsys)
    assert doc["schema"] == "qrosetta.cli/plan@1" and doc["data"]["plan"]["runs"][0]["endpoint"] == "/compare"
    assert server.paths("POST") == ["/plan"] and not os.path.exists(env["QROSETTA_RESULTS_DIR"])


def test_plan_problems_and_the_local_size_check_are_exit_10(env, circuit, capsys):
    server = Scripted()
    server.routes["problems"] = [{"code": "playlist_too_long", "params": {"circuits": 300, "max": 200},
                                  "message": "x", "run_index": 0}]
    assert run(["run", circuit], env, server) == Exit.REFUSED
    assert "300 circuits; the server runs at most 200 per run" in capsys.readouterr().err
    server = Scripted()
    server.config["limits"]["max_request_bytes"] = 10
    assert run(["run", circuit], env, server) == Exit.REFUSED
    assert "the server accepts 10" in capsys.readouterr().err
    assert not any(p.startswith("/compare") for p in server.paths("POST"))


def test_replay_of_plan_json_sends_every_field_with_source_replay(env, circuit, capsys):
    server = Scripted()
    assert run(["run", circuit, "-m", "measured", "--shots", "4000"], env, server) == 0
    (inv,) = invocations(env)
    capsys.readouterr()
    assert run(["run", "--request", os.path.join(inv, "plan.json"), "--json"], env, server) == 0
    doc = envelope(capsys)
    replayed = server.plans[-1]
    got = {k: (v["value"], v["source"]) for k, v in replayed["settings"].items()}
    assert got["n_shots"] == (4000, "replay") and got["seed"] == (99, "replay")
    assert got["optimization_level"] == (1, "replay") and got["timing_repeats"] == (3, "replay")
    assert got["target_simulators"] == (["cirq", "qiskit"], "replay")
    assert replayed["preprocessing"] == "on" and replayed["circuits"] == server.plans[0]["circuits"]
    plan = json.load(open(os.path.join(doc["data"]["results_dir"], "plan.json")))
    assert plan["replay_of"] == os.path.join(inv, "plan.json") and plan["replay_force"] is False


def test_replay_of_request_json_and_the_api_level_check(env, circuit, capsys):
    server = Scripted()
    assert run(["run", circuit], env, server) == 0
    job_dir = results.job_dirs(invocations(env)[0])[0]
    assert run(["run", "--request", os.path.join(job_dir, "request.json")], env, server) == 0
    assert server.plans[-1]["source"] == "single" and server.plans[-1]["modes"] == ["statevector"]
    assert server.plans[-1]["settings"]["optimization_level"]["source"] == "replay"
    original = os.path.join(invocations(env)[0], "plan.json")
    doc = json.load(open(original))
    doc["api_level"] = 2
    doc["server"]["analysis_version"] = "divergence-old.1"
    json.dump(doc, open(original, "w"))
    capsys.readouterr()
    assert run(["run", "--request", original], env, server) == Exit.INCOMPATIBLE
    assert "--force" in capsys.readouterr().err
    assert run(["run", "--request", original, "--force"], env, server) == 0
    err = capsys.readouterr().err
    assert "divergence-old.1" in err and "divergence-test.1" in err
    latest = os.path.realpath(os.path.join(env["QROSETTA_RESULTS_DIR"], "latest"))
    plan = json.load(open(os.path.join(latest, "plan.json")))
    assert plan["replay_force"] is True and plan["replay_of"] == original
    assert os.path.basename(latest).endswith("-bell-3")


def test_show_summary_and_export_from_the_saved_files(env, circuit, capsys, tmp_path):
    server = Scripted()
    assert run(["run", circuit, "-m", "statevector,measured"], env, server) == 0
    capsys.readouterr()
    assert run(["show", "summary", "--json"], env, server) == 0
    doc = envelope(capsys)
    assert [j["source"] for j in doc["data"]["jobs"]] == ["saved summary.json"] * 2
    assert run(["export", "crate"], env, server) == Exit.USAGE
    assert "--job MODE" in capsys.readouterr().err
    out = tmp_path / "c.zip"
    assert run(["export", "crate", "--job", "measured", "-o", str(out), "--json"], env, server) == 0
    assert envelope(capsys)["data"]["path"] == str(out) and out.read_bytes().startswith(b"PK")
    server.jobs.clear()
    job_dir = results.job_dirs(invocations(env)[0])[0]
    assert run(["export", "crate", "--result", job_dir], env, server) == Exit.USAGE
    assert "--allow-supplied" in capsys.readouterr().err
    assert run(["export", "crate", "--result", job_dir, "--allow-supplied", "--json"], env, server) == 0
    doc = envelope(capsys)
    assert doc["data"]["report_source"] == "client_supplied"
    assert doc["data"]["path"].endswith("ro-crate.client-supplied.zip")
    os.unlink(os.path.join(job_dir, "summary.json"))
    assert run(["show", "summary", "--result", job_dir, "--json"], env, server) == 0
    assert envelope(capsys)["data"]["jobs"][0]["source"] == "POST /summary of the saved report.json"


def test_jobs_status_and_unknown_jobs(env, circuit, capsys):
    server = Scripted()
    assert run(["run", circuit], env, server) == 0
    job_id = next(iter(server.jobs))
    capsys.readouterr()
    assert run(["jobs", "status", f"job:{job_id[:8]}", "--json"], env, server) == 0
    doc = envelope(capsys)
    assert doc["data"]["job"]["job_id"] == job_id and "results" not in doc["data"]["job"]
    assert run(["jobs", "status", "job:0000000000000000000000000000000000"], env, server) == Exit.NOT_FOUND
    assert run(["jobs", "--offline", "--json"], env, server) == 0
    doc = envelope(capsys)
    assert doc["data"]["offline"] is True and doc["data"]["jobs"][0]["server_status"] is None
    assert doc["data"]["jobs"][0]["save_status"] == "complete"


def test_selftest_needs_the_feature(env, capsys):
    server = Scripted()
    assert run(["selftest"], env, server) == Exit.INCOMPATIBLE
    assert "offers no self-test" in capsys.readouterr().err
    assert not server.paths("POST")


def _selftest_server(evaluations):
    server = Scripted(features={"selftest": 1})
    server.routes[("GET", "/selftest")] = (200, {
        "schema": "qrosetta.selftest_plan@1", "selftest_version": "st-1", "expected_sha256": "e" * 64,
        "jobs": [{"part": part, "endpoint": "/run_batch_suite", "request": {"mode": part, "tasks": []},
                  "client_sets": {"target_simulators": "the backends under test"},
                  "evaluate": "GET /jobs/{job_id}/selftest-result"} for part in ("statevector", "measured")],
        "tested": "bit order, idle qubits", "not_tested": "documented upstream behaviour"})
    original = server.request

    def request(method, path, query=None, body=None, headers=None, timeout=None):
        if path.endswith("/selftest-result"):
            server.log.append((method, path, query))
            job = server.jobs[path.split("/")[2]]
            from tests.unit._qrosetta_scripted import _json
            return _json(200, evaluations[job["payload"]["mode"]])
        return original(method, path, query, body, headers, timeout)

    server.request = request
    return server


def _evaluation(part, status="PASS", env_rows=()):
    return {"schema": "qrosetta.selftest_result@1", "part": part, "status": status, "counts": {"PASS": 3},
            "backends": {}, "plan": [], "known_answer": [{"check": "statevector", "status": status,
                                                          "reason": "fidelity", "backend": "qiskit"}],
            "environment_checks": list(env_rows), "caveats": []}


def test_selftest_runs_the_plan_and_saves_crates(env, capsys):
    server = _selftest_server({"statevector": _evaluation("statevector"), "measured": _evaluation("measured")})
    assert run(["selftest", "--json"], env, server) == 0
    doc = envelope(capsys)
    assert doc["data"]["status"] == "PASS" and doc["data"]["backends_under_test"] == ["qiskit", "cirq", "qulacs"]
    posted = [server.jobs[j["job_id"]]["payload"] for j in doc["data"]["jobs"]]
    assert [p["target_simulators"] for p in posted] == [["qiskit", "cirq", "qulacs"]] * 2
    inv = doc["data"]["results_dir"]
    assert os.path.isfile(os.path.join(inv, "selftest.json"))
    for job in doc["data"]["jobs"]:
        assert {"ro-crate.zip", "selftest-result.json", "STATUS"} <= set(os.listdir(job["dir"]))
        assert results.read_status(job["dir"]) == "complete"
    assert run(["show", "summary"], env, server) == 0
    assert capsys.readouterr().out.startswith("Self-test: PASS")


def test_selftest_fail_is_exit_9_and_the_cpu_quota_rule(env, capsys, tmp_path):
    quota = {"check": "cpu_quota_cores", "status": "FAIL", "reason": "null", "backend": "qiskit"}
    server = _selftest_server({"statevector": _evaluation("statevector", env_rows=[dict(quota)]),
                               "measured": _evaluation("measured", "FAIL")})
    assert run(["selftest"], env, server) == Exit.SELFTEST_FAILED
    out = capsys.readouterr().out
    assert "FAIL        statevector (qiskit)" in out and "FAIL        cpu_quota_cores (qiskit)" in out
    cfg = tmp_path / "cfg" / "qrosetta"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "config.toml").write_text("[lifecycle]\ncpu_quota = false\n")
    server = _selftest_server({"statevector": _evaluation("statevector", env_rows=[dict(quota)]),
                               "measured": _evaluation("measured")})
    assert run(["selftest", "--json"], env, server) == 0
    doc = envelope(capsys)
    assert doc["data"]["cli_rules_applied"] == [{"rule": "cpu_quota_off", "backend": "qiskit"}]
    assert any("cpu_quota_cores" in w for w in doc["data"]["warnings"])


def test_circuit_references():
    assert refs.parse("algorithm:ghz:3,seed=7").params == {"seed": 7}
    ref = refs.parse("mqt:qft:5")
    assert (ref.kind, ref.name, ref.qubits) == ("mqt", "qft", 5)
    assert refs.parse("example:bell_state_2q.qasm").name == "bell_state_2q"
    assert refs.parse("dir/circ.qasm").kind == "file" and refs.parse("-").kind == "stdin"
    for bad in ("nosuch:x", "algorithm:ghz", "algorithm:ghz:x", "algorithm:ghz:3,depth=2", "mqt:qft:3,seed=1"):
        with pytest.raises(CliError) as err:
            refs.parse(bad)
        assert err.value.code == Exit.USAGE
    assert "write ./nosuch:x for a file" in str(pytest.raises(CliError, refs.parse, "nosuch:x").value)


def test_playlists_keep_server_references(env, tmp_path, circuit):
    playlist = tmp_path / "suite.json"
    playlist.write_text(json.dumps([{"algorithm": "qft", "qubits": 4, "name": "qft"}]))
    server = Scripted()
    assert run(["run", "--playlist", str(playlist), "mqt:dj:3", circuit], env, server) == 0
    req = server.plans[0]
    assert req["source"] == "playlist"
    assert req["circuits"][0] == {"algorithm": "qft", "qubits": 4, "name": "qft"}
    assert req["circuits"][1] == {"source": "mqt", "algorithm": "dj", "qubits": 3, "name": "dj", "qasm_string": None}
    assert req["circuits"][2]["qasm_string"] == QASM


def test_durations():
    assert runplan.parse_duration("90", "--x") == 90 and runplan.parse_duration("1h30m", "--x") == 5400
    assert runplan.parse_duration("2.5m", "--x") == 150
    with pytest.raises(CliError):
        runplan.parse_duration("ten", "--x")


@pytest.mark.parametrize("status, token", [(404, "partial: report.json expired-before-save"),
                                           (500, "partial: report.json download-failed")])
def test_a_failed_download_is_a_partial_save(env, circuit, status, token):
    server = Scripted()
    original = server.request

    def request(method, path, query=None, body=None, headers=None, timeout=None):
        if path.endswith("/report"):
            return _json(status, {"detail": "gone"})
        return original(method, path, query, body, headers, timeout)

    server.request = request
    assert run(["run", circuit], env, server) == 0
    inv = invocations(env)[0]
    job_dir = results.job_dirs(inv)[0]
    assert results.read_status(job_dir) == token
    assert not os.path.exists(os.path.join(job_dir, "report.json"))
    assert not any(n.endswith(".part") for n in os.listdir(job_dir))
    assert os.path.realpath(os.path.join(env["QROSETTA_RESULTS_DIR"], "latest")) == inv


def test_save_minimal_and_no_crate(env, circuit, capsys):
    server = Scripted()
    assert run(["run", circuit, "--save", "minimal", "--fail-on", "differs"], env, server) == 0
    job_dir = results.job_dirs(invocations(env)[0])[0]
    assert results.read_status(job_dir) == "complete: minimal"
    assert sorted(os.listdir(job_dir)) == ["SHA256SUMS", "STATUS", "job.json", "request.json"]
    assert any(p.endswith("/summary") for p in server.paths("GET"))
    assert run(["run", circuit, "--save", "report,bogus"], env, server) == Exit.USAGE
    assert run(["run", circuit, "--save", "circuits"], env, server) == Exit.INCOMPATIBLE


def test_an_experiment_saves_its_bundle(env, circuit):
    server = Scripted()
    assert run(["run", circuit, "--preprocessing", "both", "--crate"], env, server) == 0
    job_dir = results.job_dirs(invocations(env)[0])[0]
    assert os.path.basename(job_dir).startswith("experiment-statevector-")
    assert sorted(os.listdir(job_dir)) == ["SHA256SUMS", "STATUS", "bundle.zip", "job.json", "request.json"]
    assert results.read_status(job_dir) == "complete"


def test_replay_takes_no_run_settings(env, circuit):
    server = Scripted()
    assert run(["run", circuit], env, server) == 0
    plan = os.path.join(invocations(env)[0], "plan.json")
    assert run(["run", "--request", plan, "--shots", "10"], env, server) == Exit.USAGE
    assert run(["run", "--request", plan, circuit], env, server) == Exit.USAGE
    assert len(server.plans) == 1
