"""Concurrent pytket round-trips keep each circuit's own gate definitions."""

import threading

from services.circuit_resolver import prepare_statevector_dispatch

_HEADER = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
_X_CIRCUIT = _HEADER + "gate g a { x a; }\nqreg q[2];\n" + "g q[0];\n" * 400 + "g q[1];\n"
_H_CIRCUIT = _HEADER + "gate g a { h a; }\nqreg q[2];\n" + "g q[1];\n" * 301


def _run_in_threads(jobs, repeats=10):
    failures = []

    def worker(fn, check):
        for _ in range(repeats):
            try:
                out = fn()
            except Exception as exc:
                failures.append(repr(exc))
                continue
            if not check(out):
                failures.append(out[:200])

    threads = [threading.Thread(target=worker, args=job) for job in jobs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return failures


def test_round_trips_in_parallel_threads_keep_their_own_gate_definitions():
    failures = _run_in_threads([
        (lambda: prepare_statevector_dispatch(_X_CIRCUIT, True)["qasm"],
         lambda out: "x q[1];" in out and "h q[" not in out),
        (lambda: prepare_statevector_dispatch(_H_CIRCUIT, True)["qasm"],
         lambda out: "h q[1];" in out and "x q[" not in out),
    ])
    assert failures == []

