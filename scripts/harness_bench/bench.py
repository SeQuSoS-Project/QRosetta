"""Time fixed harness cases with the reference and the working-tree analysis in one process.

Usage: python bench.py <ref_package_dir> [repeats] [case,...]
Prints one JSON document: environment, and per case the reference and new samples (seconds),
medians and their ratio. Reference and new runs alternate so both see the same machine state.
"""
import gc
import json
import logging
import os
import platform
import statistics
import sys
import time

import numpy as np

logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.dirname(__file__))

from equivalence import load_reference  # noqa: E402
from services.analysis import divergence as new  # noqa: E402
from qrosetta_commons.helpers import encode_statevector  # noqa: E402


def statevector_results(n_qubits, k=14, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for b in range(k):
        sv = rng.normal(size=2 ** n_qubits) + 1j * rng.normal(size=2 ** n_qubits)
        out.append({"simulator": f"sim{b}", "statevector": encode_statevector(sv / np.linalg.norm(sv)),
                    "qubit_ordering": "lsb" if b % 2 else "msb"})
    return out


def counts_results(n_bits, shots, k=14, seed=0):
    rng = np.random.default_rng(seed)
    p = rng.dirichlet(np.full(2 ** n_bits, 0.5))
    out = []
    for b in range(k):
        sample = rng.multinomial(shots, p)
        out.append({"simulator": f"sim{b}",
                    "counts": {format(i, f"0{n_bits}b"): int(v) for i, v in enumerate(sample) if v},
                    "qubit_ordering": "lsb" if b % 2 else "msb", "runner_seed": b})
    return out


CASES = {
    "sv_report_6q_14b": lambda m: (lambda r=statevector_results(6): lambda: m.create_divergence_report(r))(),
    "sv_report_7q_14b": lambda m: (lambda r=statevector_results(7): lambda: m.create_divergence_report(r))(),
    "sv_report_12q_14b": lambda m: (lambda r=statevector_results(12): lambda: m.create_divergence_report(r))(),
    "counts_report_6b_14b_8200": lambda m: (lambda r=counts_results(6, 8200): lambda: m.create_counts_report(r, 8200))(),
    "counts_report_7b_14b_8200": lambda m: (lambda r=counts_results(7, 8200): lambda: m.create_counts_report(r, 8200))(),
    "counts_report_12b_14b_8200": lambda m: (lambda r=counts_results(12, 8200): lambda: m.create_counts_report(r, 8200))(),
}


def environment():
    cpu = ""
    try:
        with open("/proc/cpuinfo") as f:
            cpu = next(line.split(":", 1)[1].strip() for line in f if line.startswith("model name"))
    except (OSError, StopIteration):
        pass
    return {
        "git_sha": os.environ.get("QROSETTA_GIT_SHA"),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": __import__("scipy").__version__,
        "cpu_model": cpu,
        "affinity": sorted(os.sched_getaffinity(0)),
        "openblas_threads": os.environ.get("OPENBLAS_NUM_THREADS"),
    }


def time_once(fn):
    gc.collect()
    start = time.perf_counter()
    fn()
    return time.perf_counter() - start


def main():
    ref = load_reference(sys.argv[1])
    repeats = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    names = sys.argv[3].split(",") if len(sys.argv) > 3 else list(CASES)
    report = {"environment": environment(), "repeats": repeats, "cases": {}}
    for name in names:
        ref_fn, new_fn = CASES[name](ref), CASES[name](new)
        ref_fn(), new_fn()
        ref_samples, new_samples = [], []
        for _ in range(repeats):
            ref_samples.append(time_once(ref_fn))
            new_samples.append(time_once(new_fn))
        ref_median, new_median = statistics.median(ref_samples), statistics.median(new_samples)
        report["cases"][name] = {
            "reference_sec": ref_samples, "new_sec": new_samples,
            "reference_median_sec": ref_median, "new_median_sec": new_median,
            "speedup": ref_median / new_median if new_median else None,
        }
        print(f"{name}: ref {ref_median:.4f} s, new {new_median:.4f} s", file=sys.stderr, flush=True)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
