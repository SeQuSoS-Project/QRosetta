#!/usr/bin/env python3
"""Pre-generate MQTBench algorithm-level circuits into rosetta-api/benchmarks/mqtbench/.

Writes one .qasm per (algorithm, qubits) within the API's size limits; commit the output.
mqt.bench 1.1.9 needs qiskit < 2.0, so run it in a separate environment:

    python3 -m venv /tmp/mqtgen
    /tmp/mqtgen/bin/pip install "mqt.bench==1.1.9" "qiskit<2.0.0"
    /tmp/mqtgen/bin/python scripts/generate_mqtbench.py
"""

import argparse
import os
import sys

# Mirrors MAX_QUBITS_MEASURED / MAX_QASM_SIZE / MAX_QASM_GATES in rosetta-api/config.py.
MAX_QUBITS = 24
MAX_QASM_SIZE = 1_000_000
MAX_QASM_GATES = 10_000

DEFAULT_ALGORITHMS = [
    "ghz", "wstate", "dj", "qft", "qftentangled",
    "qpeexact", "qpeinexact", "grover-noancilla", "grover-v-chain",
    "su2random", "realamprandom", "twolocalrandom",
]

# graphstate, vqe and qaoa are omitted: qasm2.dumps cannot serialize their numpy-typed
# parameters without transpiling them away from algorithm level.

OUT_DIR = os.path.realpath(
    os.path.join(os.path.dirname(__file__), "..", "rosetta-api", "benchmarks", "mqtbench")
)


def _install_import_shims() -> None:
    """Stub qiskit_ibm_runtime.RuntimeJob and the qiskit 1.x primitives that mqt.bench imports."""
    try:
        import qiskit_ibm_runtime
        if not hasattr(qiskit_ibm_runtime, "RuntimeJob"):
            qiskit_ibm_runtime.RuntimeJob = type("RuntimeJob", (), {})
    except ImportError:
        dummy = type("dummy", (), {"RuntimeJob": type("RuntimeJob", (), {})})
        sys.modules["qiskit_ibm_runtime"] = dummy
        sys.modules["qiskit_ibm_runtime.models"] = dummy
        sys.modules["qiskit_ibm_runtime.models.backend_configuration"] = dummy

    try:
        import qiskit.primitives as _prims
        for _name in ("Sampler", "Estimator", "BaseSampler", "BaseEstimator"):
            if not hasattr(_prims, _name):
                setattr(_prims, _name, type(_name, (), {}))
    except ImportError:
        pass


def _to_qasm(qc) -> str:
    if hasattr(qc, "qasm"):
        return qc.qasm()
    try:
        from qiskit import qasm2
        return qasm2.dumps(qc)
    except ImportError:
        from qiskit import qasm3
        return qasm3.dumps(qc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate static MQTBench QASM files.")
    parser.add_argument("--algorithms", nargs="*", default=DEFAULT_ALGORITHMS)
    parser.add_argument("--min-qubits", type=int, default=2)
    parser.add_argument("--max-qubits", type=int, default=MAX_QUBITS)
    args = parser.parse_args()

    _install_import_shims()
    try:
        import mqt.bench as _mqtbench
        from mqt.bench import get_benchmark
    except ImportError as e:
        print(f"ERROR importing mqt.bench: {e}\n"
              "Install in a throwaway env with qiskit pinned to 1.x:\n"
              '  pip install "mqt.bench==1.1.9" "qiskit<2.0.0"', file=sys.stderr)
        return 1

    print(f"mqt.bench version: {getattr(_mqtbench, '__version__', 'unknown')}")

    os.makedirs(OUT_DIR, exist_ok=True)
    written = skipped = failed = 0
    total_bytes = 0
    first_error = None

    for algo in args.algorithms:
        for q in range(args.min_qubits, min(args.max_qubits, MAX_QUBITS) + 1):
            try:
                qc = get_benchmark(benchmark_name=algo, level="alg", circuit_size=q)
                qasm = _to_qasm(qc)
            except Exception as e:
                # Unsupported sizes are expected; the first error is reported if all fail.
                if first_error is None:
                    import traceback
                    first_error = (algo, q, traceback.format_exc())
                failed += 1
                continue

            if len(qasm.encode("utf-8")) > MAX_QASM_SIZE or qasm.count(";") > MAX_QASM_GATES:
                skipped += 1
                continue

            path = os.path.join(OUT_DIR, f"{algo}_n{q}.qasm")
            with open(path, "w", encoding="utf-8") as f:
                f.write(qasm)
            written += 1
            total_bytes += len(qasm.encode("utf-8"))

    print(f"Wrote {written} circuits to {OUT_DIR}")
    print(f"  skipped (over size/gate limit): {skipped}")
    print(f"  unsupported (algo/size combo):  {failed}")
    print(f"  total size: {total_bytes / 1048576:.2f} MB")

    if written == 0 and first_error is not None:
        algo, q, tb = first_error
        print(f"\nEVERY call failed — likely an API/version mismatch. First error "
              f"(benchmark_name={algo!r}, circuit_size={q}):\n{tb}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
