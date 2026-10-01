"""Compile-only services: ``POST /compile`` turns a dispatched OpenQASM 2.0 circuit into the
output circuit of one compiler pipeline. Nothing is simulated or timed; a result is the
output text, the passes that produced it, its gate metrics and the SDK versions."""

import sys

from qrosetta_commons.cpu import apply_cpu_affinity
from qrosetta_commons.helpers import (
    GATE_METRICS_FROM_QASM, MAX_QUBITS_MEASURED, ExecutionSlots, _stamp_code_sha,
    check_qubits_limit, count_qasm_gates_and_depth, run_cli_job,
)

COMPILE_MAX_QUBITS = MAX_QUBITS_MEASURED

_PROBE_HEADER = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[3];\n'
SELF_TEST_PROBES = {
    "pauli_then_rotation": "x q[0];\nrx(0.7) q[0];\ns q[1];\nry(0.4) q[1];\n",
    "controlled_rotations": "h q[0];\ncu3(0.3,0.2,0.1) q[0],q[1];\ncu1(0.25*pi) q[1],q[2];\ncrz(0.6) q[0],q[2];\n",
    "swap_and_toffoli": "h q[0];\nswap q[0],q[2];\nccx q[0],q[1],q[2];\nt q[1];\n",
    "entangle_far_qubits": "h q[0];\ncx q[0],q[2];\nrz(1.1) q[2];\ncx q[2],q[1];\nh q[1];\n",
}


def compiled_result(*, compiler: str, qasm: str, passes_applied, optimization_level: int) -> dict:
    """``/compile`` success: the output circuit with gate metrics counted from its text."""
    gate_count, circuit_depth = count_qasm_gates_and_depth(qasm)
    return {
        "compiler": compiler,
        "optimization_level": optimization_level,
        "transpiled_qasm": qasm,
        "passes_applied": list(passes_applied),
        "gate_count": gate_count,
        "circuit_depth": circuit_depth,
        "gate_metrics_basis": GATE_METRICS_FROM_QASM,
    }


def compiler_error(compiler: str, exc) -> dict:
    return {"compiler": compiler, "error": f"{type(exc).__name__}: {exc}"}


def run_compile_job(*, compiler: str, payload: dict, pipelines: dict) -> dict:
    """Check the qubit limit, then run ``pipelines[optimization_level](qasm)``, which returns
    ``(output_qasm, passes_applied)``. Any failure becomes ``compiler_error``."""
    try:
        qasm = payload["circuit_data"]
        check_qubits_limit(qasm, COMPILE_MAX_QUBITS)
        level = int(payload.get("optimization_level", 0))
        if level not in pipelines:
            raise ValueError(f"{compiler} has no optimization level {level}; "
                             f"it has {sorted(pipelines)}")
        output, passes = pipelines[level](qasm)
        return compiled_result(compiler=compiler, qasm=output, passes_applied=passes,
                               optimization_level=level)
    except Exception as exc:
        return compiler_error(compiler, exc)


def register_compiler_endpoint(app, process_compile, max_concurrent=None) -> None:
    """Register ``POST /compile``. Requests share one ``ExecutionSlots`` queue and each runs
    in a killable spawned process, as runner requests do, without the timing instrument."""
    from qrosetta_commons.models import CompilePayload

    slots = ExecutionSlots(max_concurrent)

    @app.post("/compile")
    async def compile_circuit(payload: CompilePayload):
        return await slots.run(process_compile, payload.model_dump(), measured=False)


def run_compiler_self_test(process_compile, levels, equivalent, out=None) -> int:
    """Compile every SELF_TEST_PROBES circuit at every level and check the output with
    ``equivalent(input_qasm, output_qasm)``. Prints ``PASS``/``FAIL`` per case and returns
    the number of failures."""
    out = out or sys.stdout
    failed = 0
    for name, body in SELF_TEST_PROBES.items():
        qasm = _PROBE_HEADER + body
        for level in levels:
            result = process_compile({"circuit_data": qasm, "optimization_level": level})
            if result.get("error"):
                reason = result["error"]
            else:
                try:
                    reason = None if equivalent(qasm, result["transpiled_qasm"]) else "output unitary differs from the input"
                except Exception as exc:
                    reason = f"check failed: {type(exc).__name__}: {exc}"
            if reason:
                failed += 1
                print(f"FAIL {name} level {level}: {reason}", file=out)
            else:
                print(f"PASS {name} level {level}", file=out)
    print(f"{failed} failure(s)", file=out)
    return failed


def run_compiler_cli_main(app, process_compile, cli_name: str, levels=(), equivalent=None) -> None:
    """Compiler entrypoint: with no args serve ``app``; with ``--endpoint compile`` run one
    job from ``--payload`` or ``--s3-job-id`` (the Kubernetes path); with ``--self-test``
    run ``run_compiler_self_test`` and exit non-zero on a failure."""
    if len(sys.argv) <= 1:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
        return

    import argparse
    parser = argparse.ArgumentParser(description=f"{cli_name} compiler CLI")
    parser.add_argument("--endpoint", choices=["compile"], default=None)
    parser.add_argument("--self-test", action="store_true",
                        help="Compile the probe circuits at every level and check each output")
    parser.add_argument("--payload", default=None, help="JSON payload string")
    parser.add_argument("--s3-job-id", default=None,
                        help="S3 job ID: upload the result to jobs/completed/<id>.json")
    args = parser.parse_args()
    if args.self_test:
        sys.exit(1 if run_compiler_self_test(process_compile, levels, equivalent) else 0)
    if args.endpoint is None:
        parser.error("--endpoint is required unless --self-test is given")

    def _process(payload_dict):
        apply_cpu_affinity()
        result = process_compile(payload_dict)
        if isinstance(result, dict):
            result["queue_wait_sec"] = 0.0
            _stamp_code_sha(result, process_compile)
        return result

    run_cli_job(_process, args, parser)
