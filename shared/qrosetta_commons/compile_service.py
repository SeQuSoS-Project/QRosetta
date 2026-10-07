"""Compile-only services: ``POST /compile`` turns a dispatched OpenQASM 2.0 circuit into the
output circuit of one compiler pipeline. Nothing is simulated or timed; a result is the
output text, the passes that produced it, its gate metrics, the SDK versions and the native
components (programs built from source rather than installed with pip)."""

import hashlib
import os
import sys
from pathlib import Path

from qrosetta_commons.compile_errors import CompileRefused, OutputRejected
from qrosetta_commons.cpu import apply_cpu_affinity
from qrosetta_commons.helpers import (
    GATE_METRICS_FROM_QASM, IMAGE_GIT_SHA, MAX_QUBITS_COMPILE, ExecutionSlots, _stamp_code_sha,
    check_qubits_limit, count_qasm_gates_and_depth, count_qasm_gates_by_name,
    get_num_qubits_from_qasm, get_sdk_versions, run_cli_job,
)

COMPILE_MAX_QUBITS = MAX_QUBITS_COMPILE

_PROBE_HEADER = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[3];\n'
SELF_TEST_PROBES = {
    "pauli_then_rotation": "x q[0];\nrx(0.7) q[0];\ns q[1];\nry(0.4) q[1];\nh q[2];\n",
    "controlled_rotations": "h q[0];\ncu3(0.3,0.2,0.1) q[0],q[1];\ncu1(0.25*pi) q[1],q[2];\ncrz(0.6) q[0],q[2];\n",
    "swap_and_toffoli": "h q[0];\nswap q[0],q[2];\nccx q[0],q[1],q[2];\nt q[1];\n",
    "entangle_far_qubits": "h q[0];\ncx q[0],q[2];\nrz(1.1) q[2];\ncx q[2],q[1];\nh q[1];\n",
    "classical_register_declared": "creg c[3];\nh q[0];\ncx q[0],q[1];\nry(0.3) q[2];\n",
}
TRANSLATION_PROBES = {
    "multi_controlled_before_fresh_qubit": "qreg b[2];\nh q[0];\nh q[1];\nh q[2];\nc3x q[0],q[1],q[2],b[0];\nh b[1];\n",
}


_NATIVE_COMPONENTS: list = []
BUILD_FILES_DIR = Path(os.getenv("QROSETTA_BUILD_FILES_DIR", "/usr/local/share/qrosetta-build"))


def _build_file_hashes() -> dict:
    """sha256 of each file the image copied into BUILD_FILES_DIR (its Dockerfile, lock file
    and any patches, build sources or generated data); empty when the directory is absent."""
    if not BUILD_FILES_DIR.is_dir():
        return {}
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(BUILD_FILES_DIR.iterdir()) if path.is_file()}


BUILD_FILES = _build_file_hashes()


def declare_native_component(name: str, version: str, source_url: str, source_sha256: str,
                             **details) -> None:
    """Record a program the image builds from source (name, version, the source archive and
    its sha256, and further string or list-of-string details such as patches)."""
    entry = {"name": name, "version": version, "source_url": source_url,
             "source_sha256": source_sha256}
    for key, value in details.items():
        entry[key] = list(value) if isinstance(value, (list, tuple)) else str(value)
    _NATIVE_COMPONENTS.append(entry)


def native_components() -> list:
    return [dict(entry) for entry in _NATIVE_COMPONENTS]


def compiler_versions() -> dict:
    """What this compiler image reports about itself: pip SDK versions, native components,
    build-file hashes and the image commit."""
    return {"sdk_versions": get_sdk_versions(), "native_components": native_components(),
            "build_files": dict(BUILD_FILES), "image_git_sha": IMAGE_GIT_SHA}


def compiled_result(*, compiler: str, qasm: str, passes_applied, optimization_level: int) -> dict:
    """``/compile`` success: the output circuit with gate metrics counted from its text."""
    gate_count, circuit_depth = count_qasm_gates_and_depth(qasm)
    gate_counts, multi_qubit_gate_count = count_qasm_gates_by_name(qasm)
    return {
        "compiler": compiler,
        "optimization_level": optimization_level,
        "transpiled_qasm": qasm,
        "passes_applied": list(passes_applied),
        "gate_count": gate_count,
        "circuit_depth": circuit_depth,
        "gate_counts": gate_counts,
        "multi_qubit_gate_count": multi_qubit_gate_count,
        "gate_metrics_basis": GATE_METRICS_FROM_QASM,
    }


def compiler_error(compiler: str, exc) -> dict:
    """``/compile`` failure. A CompileRefused or OutputRejected also sets ``refusal`` (its
    message) and ``refusal_kind`` (``input`` or ``output_check``)."""
    result = {"compiler": compiler, "error": f"{type(exc).__name__}: {exc}"}
    if isinstance(exc, (CompileRefused, OutputRejected)):
        result["refusal"] = str(exc)
        result["refusal_kind"] = "input" if isinstance(exc, CompileRefused) else "output_check"
    return result


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
        return _with_build_record(compiled_result(
            compiler=compiler, qasm=output, passes_applied=passes, optimization_level=level))
    except Exception as exc:
        return _with_build_record(compiler_error(compiler, exc))


def _with_build_record(result):
    if isinstance(result, dict):
        if _NATIVE_COMPONENTS:
            result["native_components"] = native_components()
        if BUILD_FILES:
            result["build_files"] = dict(BUILD_FILES)
    return result


def register_compiler_endpoint(app, process_compile, max_concurrent=None) -> None:
    """Register ``POST /compile`` and ``GET /capabilities`` (available, with
    ``compiler_versions()``). Compile requests share one ``ExecutionSlots`` queue of
    ``COMPILER_MAX_CONCURRENT`` slots (default 2; compiles are not timed) and each runs in a
    killable spawned process, as runner requests do, without the timing instrument."""
    from qrosetta_commons.models import CompilePayload

    if max_concurrent is None:
        max_concurrent = int(os.getenv("COMPILER_MAX_CONCURRENT", "2"))
    slots = ExecutionSlots(max_concurrent)

    @app.get("/capabilities")
    async def compiler_capabilities():
        return {"available": True, "reason": None, "device": None, **compiler_versions()}

    @app.post("/compile")
    async def compile_circuit(payload: CompilePayload):
        return await slots.run(process_compile, payload.model_dump(), measured=False)


def run_compiler_self_test(process_compile, levels, equivalent, out=None, extra_probes=None,
                           probes=None) -> int:
    """Compile every probe circuit (``probes``, default SELF_TEST_PROBES, plus
    ``extra_probes``) at every level and check that the output declares as many qubits as
    the input and passes ``equivalent(input_qasm, output_qasm)``. Prints ``PASS``/``FAIL``
    per case and returns the number of failures."""
    out = out or sys.stdout
    failed = 0
    for name, body in {**(SELF_TEST_PROBES if probes is None else probes), **(extra_probes or {})}.items():
        qasm = _PROBE_HEADER + body
        for level in levels:
            result = process_compile({"circuit_data": qasm, "optimization_level": level})
            if result.get("error"):
                reason = result["error"]
            elif get_num_qubits_from_qasm(result["transpiled_qasm"]) != get_num_qubits_from_qasm(qasm):
                reason = (f"output declares {get_num_qubits_from_qasm(result['transpiled_qasm'])} "
                          f"qubits, input {get_num_qubits_from_qasm(qasm)}")
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


def run_compiler_cli_main(app, process_compile, cli_name: str, levels=(), equivalent=None,
                          extra_probes=None, probes=None) -> None:
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
        sys.exit(1 if run_compiler_self_test(process_compile, levels, equivalent,
                                             extra_probes=extra_probes, probes=probes) else 0)
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
