"""The circuit preparation worker: reuse, memory and time limits, crashes, and exceptions
that keep their type and message."""
import asyncio
import os
import re
import time

import pytest

pytest.importorskip("pytket")

import services.compilation as compilation  # noqa: E402
import services.job_manager as job_manager  # noqa: E402
from config import settings  # noqa: E402
from services import job_store, prep_worker  # noqa: E402
from services.circuit_resolver import prepare_measured_dispatch, prepare_statevector_dispatch  # noqa: E402
from services.quirk_converter import quirk_url  # noqa: E402
from tests.unit import prep_probes  # noqa: E402

HEAD = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
BELL = HEAD + "qreg q[2];\nh q[0];\ncx q[0],q[1];\n"



@pytest.fixture(autouse=True)
def fresh_worker(tmp_path, monkeypatch):
    monkeypatch.setattr(job_store, "SPILL_DIR", str(tmp_path / "spill"))
    yield
    prep_worker.stop()


def run(coro):
    return asyncio.run(coro)


def test_the_worker_is_reused_across_calls():
    first = run(prep_worker.call(prep_probes.pid))
    assert first != os.getpid()
    assert run(prep_worker.call(prep_probes.pid)) == first == prep_worker.worker_pid()


def test_a_preparation_over_the_memory_limit_is_stopped_and_the_worker_restarts(monkeypatch):
    monkeypatch.setattr(settings, "PREP_MAX_MIB", 400)
    before = run(prep_worker.call(prep_probes.pid))
    started = time.monotonic()
    with pytest.raises(prep_worker.PreparationLimitExceeded, match="more than 400 MiB") as info:
        run(prep_worker.call(prep_probes.allocate, 600, hint="Use less."))
    assert str(info.value).endswith("and was stopped. Use less.")
    assert time.monotonic() - started < 10
    assert prep_worker.worker_pid() is None
    after = run(prep_worker.call(prep_probes.pid))
    assert after != before


def test_an_oversized_job_preparation_fails_the_job_with_the_limit(monkeypatch):
    monkeypatch.setattr(settings, "PREP_MAX_MIB", 300)
    monkeypatch.setattr(job_manager, "prepare_statevector_dispatch",
                        prep_probes.oversized_statevector_preparation)
    job_manager.ACTIVE_JOBS["pw-big"] = job_manager.new_job()
    try:
        run(job_manager.worker_compare("pw-big", BELL, 0, {}, 60, ["qiskit"], "local"))
        job = job_manager.ACTIVE_JOBS["pw-big"]
        assert job["status"] == "failed"
        assert "used more than 300 MiB, the server's memory limit for circuit preparation" in job["error"]
        assert "apply_preprocessing=false" in job["error"]
    finally:
        job_manager.ACTIVE_JOBS.pop("pw-big", None)
    assert run(prep_worker.prepare(prepare_statevector_dispatch, BELL, True)) == \
        prepare_statevector_dispatch(BELL, True)


def test_a_compile_input_over_the_limit_is_recorded_with_the_reason(monkeypatch):
    monkeypatch.setattr(settings, "PREP_MAX_MIB", 300)
    monkeypatch.setattr(compilation, "prepare_statevector_dispatch",
                        prep_probes.oversized_statevector_preparation)
    out = run(compilation.compile_circuit(BELL, True, {"pyzx": [1]}, 60))
    assert out["compile_input"] is None
    reason = out["compiled_circuits"][0]["error"]
    assert reason.startswith("Not compiled: preparing this circuit used more than 300 MiB")


def test_a_preparation_over_the_time_limit_is_stopped(monkeypatch):
    run(prep_worker.call(prep_probes.pid))
    monkeypatch.setattr(settings, "PREP_TIMEOUT_SEC", 0.5)
    started = time.monotonic()
    with pytest.raises(prep_worker.PreparationLimitExceeded, match="longer than 0.5 s"):
        run(prep_worker.call(prep_probes.sleep, 30))
    assert time.monotonic() - started < 5
    assert run(prep_worker.call(prep_probes.sleep, 0)) == 0


@pytest.mark.parametrize("probe,args,expected", [
    (prep_probes.exit_with, (3,), "exit code 3"),
    (prep_probes.kill_self, (), "killed by SIGKILL"),
])
def test_a_worker_that_ends_during_a_call_fails_it_and_is_restarted(probe, args, expected):
    before = run(prep_worker.call(prep_probes.pid))
    with pytest.raises(prep_worker.PreparationWorkerFailed, match=expected):
        run(prep_worker.call(probe, *args))
    assert run(prep_worker.call(prep_probes.pid)) != before


def test_a_worker_that_died_between_calls_is_replaced():
    pid = run(prep_worker.call(prep_probes.pid))
    os.kill(pid, 9)
    time.sleep(0.2)
    assert run(prep_worker.call(prep_probes.pid)) != pid


REFUSED = [
    HEAD + "gate sleep a { x a; }\nqreg q[1];\nsleep q[0];\n",
        HEAD + "gate yyphase(t) a,b { }\nqreg q[2];\nh q[0];\nyyphase(0.7) q[0],q[1];\n",
    HEAD + "opaque myop a;\nqreg q[1];\nmyop q[0];\n",
    HEAD + "qreg q[1];\ncreg c[1];\nmeasure q[0] -> c[0];\nh q[0];\n",
    HEAD + "gate g(t) a { rz(t^2) a; }\nqreg q[1];\ng(0.1) q[0];\n",
    HEAD + "qreg a[2];\nqreg b[3];\ncx a, b;\n",
    HEAD + "qreg q[1];\nh q[0]\nx q[0];\n",
]


def _outcome(call):
    try:
        return "returned", call()
    except Exception as exc:
        return type(exc), str(exc)


async def _outcome_async(coro):
    try:
        return "returned", await coro
    except Exception as exc:
        return type(exc), str(exc)


def _token_order_free(outcome):
    """The outcome with each run of Lark's '\t* TOKEN' lines sorted: Lark lists the expected
    tokens of a set, whose order depends on the process's hash seed."""
    kind, message = outcome
    if not isinstance(message, str):
        return outcome
    return kind, re.sub(r"(?:\t\* [^\n]*\n)+",
                        lambda m: "".join(sorted(m.group(0).splitlines(keepends=True))), message)


def test_token_order_is_the_only_difference_ignored():
    head = "Unexpected token Token('INAM', 'x') at line 5, column 1.\nExpected one of: \n"
    tail = "Previous tokens: [Token('IARG', 'q[0]')]\n"
    a = (ValueError, head + "\t* SEMICOLON\n\t* COMMA\n" + tail)
    b = (ValueError, head + "\t* COMMA\n\t* SEMICOLON\n" + tail)
    assert _token_order_free(a) == _token_order_free(b)
    assert _token_order_free(a) != _token_order_free((ValueError, head + "\t* COMMA\n" + tail))
    assert _token_order_free(a) != _token_order_free((TypeError, b[1]))
    assert _token_order_free(a) != _token_order_free((ValueError, b[1].replace("line 5", "line 6")))


@pytest.mark.parametrize("qasm", REFUSED)
@pytest.mark.parametrize("func", [prepare_statevector_dispatch, prepare_measured_dispatch])
def test_exceptions_keep_their_type_and_message(func, qasm):
    expected = _outcome(lambda: func(qasm, True))
    actual = run(_outcome_async(prep_worker.prepare(func, qasm, True)))
    assert _token_order_free(actual) == _token_order_free(expected)
    if func is prepare_statevector_dispatch:
        assert expected[0] != "returned"


def test_quirk_exceptions_keep_their_type_and_message():
    qasm = HEAD + "qreg q[1];\nreset q[0];\n"
    assert run(_outcome_async(prep_worker.call(quirk_url, qasm))) == _outcome(lambda: quirk_url(qasm))


def test_results_equal_the_direct_call():
    qasm = HEAD + "qreg a[2];\nqreg b[1];\ncreg c[3];\nh a;\ncx a[1],b[0];\nrz(2^0.5) b[0];\nbarrier a;\nmeasure a[0] -> c[0];\n"
    for func in (prepare_statevector_dispatch, prepare_measured_dispatch):
        for pp in (True, False):
            assert run(prep_worker.prepare(func, qasm, pp)) == func(qasm, pp)


def test_without_preprocessing_no_worker_is_started():
    run(prep_worker.prepare(prepare_measured_dispatch, BELL, False))
    assert prep_worker.worker_pid() is None


def test_a_quirk_drawing_over_the_limit_is_a_400(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    from routers import generation
    monkeypatch.setattr(settings, "PREP_MAX_MIB", 300)
    monkeypatch.setattr(generation, "quirk_url", prep_probes.oversized_quirk_drawing)
    r = TestClient(app).post("/visualize/quirk", json={"qasm_string": BELL})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == ("Cannot draw this circuit in Quirk: preparing this circuit used "
                                  "more than 300 MiB, the server's memory limit for circuit "
                                  "preparation, and was stopped.")
