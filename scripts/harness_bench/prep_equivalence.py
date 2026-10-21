"""Compare circuit preparation in a thread of this process with preparation in the worker.

Usage (inside the API image, from rosetta-api/): python ../scripts/harness_bench/prep_equivalence.py [pattern]
Every bundled circuit (benchmarks/**/*.qasm, circuits/*.qasm), every algorithm template at
several sizes, and a set of circuits that preparation refuses is prepared by
prepare_statevector_dispatch and prepare_measured_dispatch with preprocessing on and off,
and drawn by quirk_url up to 16 qubits: once directly in a thread (the previous path) and
once through services.prep_worker. Results must be equal; a raised exception must have the
same type and message. A case the worker stops at its limit is listed and not compared. The
peak RSS of each direct preparation is printed (VmHWM after clear_refs). Exit status 1 on
any difference.
"""
import asyncio
import ctypes
import glob
import logging
import sys
import time

logging.disable(logging.CRITICAL)

from services import prep_worker  # noqa: E402
from services.circuit_library import generate_circuit, load_algorithms  # noqa: E402
from services.circuit_resolver import prepare_measured_dispatch, prepare_statevector_dispatch  # noqa: E402
from services.quirk_converter import quirk_url  # noqa: E402
from qrosetta_commons.helpers import get_num_qubits_from_qasm  # noqa: E402

HEAD = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
REFUSED = {
    "sleep_barrier": HEAD + "gate sleep a { x a; }\nqreg q[1];\nsleep q[0];\n",
    "yyphase_builtin": HEAD + "gate yyphase(t) a, b { rz(t) a; cx a, b; }\nqreg q[2];\nyyphase(0.3) q[0], q[1];\n",
    "yyphase_empty": HEAD + "gate yyphase(t) a,b { }\nqreg q[2];\nh q[0];\nyyphase(0.7) q[0],q[1];\n",
    "opaque": HEAD + "opaque myop a;\nqreg q[1];\nmyop q[0];\n",
    "mid_circuit": HEAD + "qreg q[1];\ncreg c[1];\nmeasure q[0] -> c[0];\nh q[0];\n",
    "reset": HEAD + "qreg q[1];\nreset q[0];\n",
    "if": HEAD + "qreg q[1];\ncreg c[1];\nif(c==1) x q[0];\n",
    "caret_in_body": HEAD + "gate g(t) a { rz(t^2) a; }\nqreg q[1];\ng(0.1) q[0];\n",
    "caret_top": HEAD + "qreg q[1];\nrz(2^0.5) q[0];\n",
    "unparsable": HEAD + "qreg q[1];\nh q[0]\nx q[0];\n",
    "unequal_broadcast": HEAD + "qreg a[2];\nqreg b[3];\ncx a, b;\n",
    "c3x_rename": HEAD + "qreg q[4];\nc3x q[0],q[1],q[2],q[3];\nccx q[0],q[1],q[2];\n",
    "empty_gate": HEAD + "gate nothing a { }\nqreg q[1];\nnothing q[0];\nh q[0];\n",
    "spaced_index": HEAD + "qreg q [2];\nh q [ 0 ];\ncx q[0], q [1];\n",
    "tiny_angle": HEAD + "qreg q[2];\nrz(1.3e-13) q[0];\nh q[1];\n",
}
TEMPLATE_SIZES = (1, 2, 3, 4, 5, 8, 12, 16, 20, 24)


def mib(field: str) -> float:
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith(field):
                return int(line.split()[1]) / 1024
    return 0.0


TRIM = ctypes.CDLL("libc.so.6").malloc_trim


def outcome_direct(func, *args):
    try:
        return ("ok", func(*args))
    except Exception as exc:
        return ("error", f"{type(exc).__module__}.{type(exc).__qualname__}", str(exc))


async def outcome_worker(func, *args):
    try:
        if func is quirk_url:
            return ("ok", await prep_worker.call(func, *args))
        return ("ok", await prep_worker.prepare(func, *args))
    except prep_worker.PreparationLimitExceeded as exc:
        return ("limit", str(exc))
    except Exception as exc:
        return ("error", f"{type(exc).__module__}.{type(exc).__qualname__}", str(exc))


def cases(pattern: str):
    for path in sorted(glob.glob("benchmarks/**/*.qasm", recursive=True)) + sorted(glob.glob("circuits/*.qasm")):
        if pattern in path:
            with open(path) as f:
                yield path, f.read()
    for algorithm in load_algorithms():
        for n in TEMPLATE_SIZES:
            name = f"template:{algorithm}:{n}"
            if pattern not in name:
                continue
            try:
                yield name, generate_circuit(algorithm, n)
            except Exception:
                continue
    for name, qasm in REFUSED.items():
        if pattern in f"refused:{name}":
            yield f"refused:{name}", qasm


async def main(pattern: str) -> int:
    compared = differences = limited = errors_matched = 0
    peaks = []
    for name, qasm in cases(pattern):
        calls = [(prepare_statevector_dispatch, pp) for pp in (True, False)]
        calls += [(prepare_measured_dispatch, pp) for pp in (True, False)]
        try:
            small = get_num_qubits_from_qasm(qasm) <= 16
        except Exception:
            small = True
        for func, pp in calls + ([(quirk_url, None)] if small else []):
            args = (qasm,) if pp is None else (qasm, pp)
            label = f"{name} {func.__name__} pp={pp}"
            t0 = time.perf_counter()
            new = await outcome_worker(func, *args)
            t_new = time.perf_counter() - t0
            if new[0] == "limit":
                limited += 1
                print(f"LIMIT {label}: {new[1][:80]} ({t_new:.1f} s)", flush=True)
                continue
            TRIM(0)
            with open("/proc/self/clear_refs", "w") as f:
                f.write("5")
            t0 = time.perf_counter()
            old = await asyncio.to_thread(outcome_direct, func, *args)
            t_old = time.perf_counter() - t0
            peak = mib("VmHWM")
            compared += 1
            if pp:
                peaks.append((peak, t_old, label))
            if old != new:
                differences += 1
                print(f"DIFF {label}\n  old={str(old)[:300]}\n  new={str(new)[:300]}", flush=True)
            elif old[0] == "error":
                errors_matched += 1
    peaks.sort(reverse=True)
    print("largest direct preparations (peak RSS MiB, s):")
    for peak, seconds, label in peaks[:15]:
        print(f"  {peak:7.0f}  {seconds:6.2f}  {label}")
    print(f"compared={compared} differences={differences} exceptions_matched={errors_matched} "
          f"stopped_at_limit={limited} limit={prep_worker.settings.PREP_MAX_MIB} MiB")
    prep_worker.stop()
    return 1 if differences else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "")))
