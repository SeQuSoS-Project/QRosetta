#!/usr/bin/env python3
"""Pre-generate MQTBench (algorithm-level) circuits as static QASM files.

Run this ONCE, offline, in a THROWAWAY environment — do not pollute the project venv.
mqt.bench 1.1.9 eagerly imports its qiskit_application_* benchmarks, which use the
old qiskit 1.x API (qiskit.primitives.Sampler, removed in qiskit 2.x), so qiskit must
be pinned < 2.0.0 in the generation env:

    python3 -m venv /tmp/mqtgen
    /tmp/mqtgen/bin/pip install "mqt.bench==1.1.9" "qiskit<2.0.0"
    /tmp/mqtgen/bin/python scripts/generate_mqtbench.py

It writes one .qasm file per (algorithm, qubits) into rosetta-api/benchmarks/mqtbench/
and you commit the result. The production API then reads these files directly and needs
NO quantum SDKs (no mqt.bench / qiskit / pytket-qiskit / qiskit-ibm-runtime / pyscf).

Algorithm level is high-level (not decomposed), so circuits stay small. Only circuits
that pass the platform's runtime limits are kept, so the bundle mirrors exactly what
the runners can actually execute.
"""

import argparse
import os
import sys

# Keep in sync with rosetta-api/config.py (MAX_QUBITS_MEASURED / MAX_QASM_SIZE /
# MAX_QASM_GATES). A circuit outside these would be rejected by the API anyway.
MAX_QUBITS = 24
MAX_QASM_SIZE = 1_000_000
MAX_QASM_GATES = 10_000

# Algorithm-level benchmarks worth bundling. Edit freely; names must be valid
# mqt.bench benchmark_name values.
DEFAULT_ALGORITHMS = [
    "ghz", "wstate", "dj", "qft", "qftentangled",
    "qpeexact", "qpeinexact", "grover-noancilla", "grover-v-chain",
    "su2random", "realamprandom", "twolocalrandom",
]

# Excluded on purpose: "graphstate", "vqe", "qaoa". mqt.bench 1.1.9 builds these with
# numpy-typed gate parameters that qiskit.qasm2.dumps cannot serialize (raises
# "TypeError: only 0-dimensional arrays can be converted to Python scalars"). They can
# only be exported by transpiling to a basis first, which would alter the advertised
# algorithm-level circuit, so we leave them out rather than misrepresent the provenance.

OUT_DIR = os.path.realpath(
    os.path.join(os.path.dirname(__file__), "..", "rosetta-api", "benchmarks", "mqtbench")
)


def _install_import_shims() -> None:
    """mqt.bench 1.1.9 eagerly imports modules written for the qiskit 1.x API. Best
    effort: shim the names removed in qiskit 2.x so the import chain survives. This is
    only enough if your env is otherwise qiskit-1.x-compatible — the reliable route is
    a throwaway env with `qiskit<2.0.0` (see the module docstring)."""
    # mqt.bench -> pytket-qiskit -> qiskit_ibm_runtime, which removed RuntimeJob.
    try:
        import qiskit_ibm_runtime
        if not hasattr(qiskit_ibm_runtime, "RuntimeJob"):
            qiskit_ibm_runtime.RuntimeJob = type("RuntimeJob", (), {})
    except ImportError:
        dummy = type("dummy", (), {"RuntimeJob": type("RuntimeJob", (), {})})
        sys.modules["qiskit_ibm_runtime"] = dummy
        sys.modules["qiskit_ibm_runtime.models"] = dummy
        sys.modules["qiskit_ibm_runtime.models.backend_configuration"] = dummy

    # qiskit.primitives.Sampler / Estimator were removed in qiskit 2.x but are imported
    # at module top by mqt.bench's qiskit_application_* benchmarks.
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
                # Many algorithms only support certain sizes — that's expected. But if
                # EVERY call fails, it's an API/version mismatch — capture the first
                # real error (with traceback) so we can see it instead of guessing.
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
