"""Peak memory of the API's circuit preparation (preprocessing on) for every bundled circuit.

Usage (from rosetta-api/, in the API image or a venv with its requirements and ../shared):
    python ../scripts/harness_bench/prep_peaks.py raw.json [table.json]

Each bundled MQT Bench and QASMBench circuit is prepared by prepare_statevector_dispatch (up
to 18 qubits) and prepare_measured_dispatch with preprocessing on, each in a fresh spawned
process that first imports the modules the preparation worker imports. The parent reads the
child's resident memory every 20 ms and stops it above KILL_MIB (default 2048) or after
KILL_SEC (default 200). raw.json gets one record per circuit and mode. table.json, when
given, gets the circuits whose peak exceeded 512 MiB in either mode, in the format of
rosetta-api/benchmarks/preparation_peaks.json (without its description fields), with
``peak_mib_at_least`` for a circuit that was stopped at KILL_MIB.
Environment: WORKERS (parallel circuits, default 12), KILL_MIB, KILL_SEC.
"""
import importlib
import json
import multiprocessing
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import psutil

KILL_MIB = int(os.environ.get("KILL_MIB", "2048"))
KILL_SEC = float(os.environ.get("KILL_SEC", "200"))
WORKERS = int(os.environ.get("WORKERS", "12"))
TABLE_ABOVE_MIB = 512
_MIB = 2**20


def _child(conn, source, algorithm, qubits, mode):
    sys.path[:0] = [os.getcwd(), os.path.join(os.getcwd(), "..", "shared")]
    for name in ("services.circuit_resolver", "services.quirk_converter"):
        importlib.import_module(name)
    from services import circuit_resolver as cr
    qasm = cr.resolve_circuit_qasm(source, algorithm, qubits, None, mode=mode)
    conn.send(("start", None))
    func = cr.prepare_statevector_dispatch if mode == "statevector" else cr.prepare_measured_dispatch
    try:
        func(qasm, True)
        conn.send(("ok", None))
    except Exception as exc:
        conn.send(("error", f"{type(exc).__name__}: {str(exc)[:200]}"))


def measure(item):
    source, algorithm, qubits, mode = item
    ctx = multiprocessing.get_context("spawn")
    parent, child = ctx.Pipe()
    process = ctx.Process(target=_child, args=(child, source, algorithm, qubits, mode))
    process.start()
    watched = psutil.Process(process.pid)
    peak, start, status, detail = 0, None, None, None
    while True:
        if parent.poll(0.02):
            kind, value = parent.recv()
            if kind == "start":
                start = time.monotonic()
                continue
            status, detail = kind, value
            break
        try:
            rss = watched.memory_info().rss
        except psutil.Error:
            status = "died"
            break
        if start is not None:
            peak = max(peak, rss)
            if rss > KILL_MIB * _MIB:
                status = "over_kill_mib"
                break
            if time.monotonic() - start > KILL_SEC:
                status = "over_kill_sec"
                break
        if not process.is_alive():
            status = "died"
            break
    elapsed = time.monotonic() - start if start else None
    process.kill()
    process.join()
    return {"source": source, "algorithm": algorithm, "qubits": qubits, "mode": mode,
            "status": status, "detail": detail, "peak_mib": round(peak / _MIB, 1),
            "seconds": round(elapsed, 2) if elapsed else None}


def bundled_circuits():
    sys.path[:0] = [os.getcwd(), os.path.join(os.getcwd(), "..", "shared")]
    from services import benchmark_library as bl
    out = [("mqt", algo, q) for algo, sizes in bl.list_mqt().items() for q in sizes]
    return out + [("qasmbench", name, 0) for name in bl.list_qasmbench()]


def table(records):
    by_circuit = {}
    for r in records:
        if r["status"] == "error":
            continue
        entry = by_circuit.setdefault((r["source"], r["algorithm"], r["qubits"]),
                                      {"peak": 0.0, "stopped": False})
        entry["peak"] = max(entry["peak"], r["peak_mib"])
        entry["stopped"] |= r["status"] == "over_kill_mib"
    rows = []
    for (source, algorithm, qubits), entry in sorted(by_circuit.items()):
        if entry["peak"] <= TABLE_ABOVE_MIB:
            continue
        row = {"source": source, "algorithm": algorithm, "qubits": qubits}
        row["peak_mib_at_least" if entry["stopped"] else "peak_mib"] = (
            KILL_MIB if entry["stopped"] else round(entry["peak"]))
        rows.append(row)
    return rows


if __name__ == "__main__":
    todo = [(s, a, q, mode) for s, a, q in bundled_circuits()
            for mode in ("statevector", "measured") if not (mode == "statevector" and q > 18)]
    records = []
    with ThreadPoolExecutor(WORKERS) as pool:
        for record in pool.map(measure, todo):
            records.append(record)
            print(json.dumps(record), flush=True)
    with open(sys.argv[1], "w") as fh:
        json.dump(records, fh, indent=1)
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w") as fh:
            json.dump({"circuits": table(records)}, fh, indent=1)
