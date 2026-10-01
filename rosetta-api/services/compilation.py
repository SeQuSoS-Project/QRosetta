"""Compile-only services for a run: check the requested compilers, compile the circuit the
API prepares for statevector runners, and record each output in the report.

Compilers run after the job's simulators have finished, through the same dispatch (queue
and timeouts) as a shared, non-exclusive run, so a compile never overlaps a timed run of its
own job and an exclusive job of another client still waits for it. Their results are kept
apart from raw_results: they are circuit text, never simulated or compared.
"""

from fastapi import HTTPException

from config import settings
from qrosetta_commons.helpers import get_logger
from services.circuit_resolver import StatevectorIncompatible, prepare_statevector_dispatch
from services.dispatcher import dispatch_to_runners
from services.run_registry import EXCLUSIVE

logger = get_logger("rosetta-compilation")

COMPILER_SERVICES = settings.get_compiler_services()

COMPILE_INPUT_DERIVATION = (
    "The submitted circuit as the API prepares it for statevector runners: terminal "
    "measurements removed, then the run's API preprocessing (see api_preprocessing_applied).")

_COPIED_FIELDS = ("optimization_level", "transpiled_qasm", "passes_applied", "gate_count",
                  "circuit_depth", "gate_counts", "multi_qubit_gate_count", "gate_metrics_basis", "sdk_versions", "dispatch_status",
                  "error", "queue_wait_sec", "gate_wait_sec", "runner_image", "image_git_sha",
                  "runtime_environment", "dispatched_at", "completed_at")


def enabled_compilers() -> dict:
    return {cid: svc for cid, svc in COMPILER_SERVICES.items() if svc.get("enabled", True)}


def validate_compilers(compilers: dict) -> None:
    """400 for an unknown or disabled compiler id, or a level the compiler does not offer."""
    available = enabled_compilers()
    for cid, levels in (compilers or {}).items():
        if cid not in available:
            raise HTTPException(status_code=400, detail=(
                f"Unknown or disabled compiler {cid!r}; available: {', '.join(sorted(available)) or 'none'}."))
        offered = available[cid]["optimization_levels"]
        missing = [lvl for lvl in levels if lvl not in offered]
        if missing:
            raise HTTPException(status_code=400, detail=(
                f"Compiler {cid!r} has no optimization level {missing[0]}; it offers {sorted(offered)}."))


def _compiler_id(key: str) -> str:
    return key.split("~", 1)[0]


def _name(cid: str):
    return COMPILER_SERVICES.get(cid, {}).get("name")


def compile_key(cid: str, level) -> str:
    """Report key of one compile: ``<id>~opt<level>~run1``, so the level is always in it."""
    return f"{cid}~opt{level}~run1"


def _record(result: dict) -> dict:
    cid = _compiler_id(str(result.get("simulator")))
    record = {"compiler": compile_key(cid, result.get("optimization_level")), "compiler_id": cid,
              "compiler_name": _name(cid)}
    record.update({field: result[field] for field in _COPIED_FIELDS if field in result})
    if "runner_code_sha256" in result:
        record["compiler_code_sha256"] = result["runner_code_sha256"]
    if isinstance(record.get("error"), str):
        record["error"] = (record["error"].replace("the runner process", "the compiler process")
                           .replace("The runner process", "The compiler process"))
    return record


def _unrun(compilers: dict, status: str, reason: str) -> list:
    return [{"compiler": compile_key(cid, lvl), "compiler_id": cid, "compiler_name": _name(cid),
             "optimization_level": lvl, "dispatch_status": status, "error": reason}
            for cid, levels in compilers.items() for lvl in levels]


def queue_compile_statuses(runner_statuses: dict, compilers: dict) -> None:
    """Mark every requested compile as queued in the live status map, under the keys the
    dispatch reports (``<id>`` for one level, ``<id>~opt<L>~run1`` for several)."""
    if runner_statuses is None:
        return
    for cid, levels in (compilers or {}).items():
        keys = [cid] if len(levels) == 1 else [f"{cid}~opt{lvl}~run1" for lvl in levels]
        for key in keys:
            runner_statuses[key] = "queued"


async def compile_circuit(qasm_string: str, apply_preprocessing: bool, compilers: dict,
                          timeout_seconds: int, runner_statuses: dict = None) -> dict:
    """``{"compile_input", "compiled_circuits"}`` for the report, or ``{}`` when no compiler
    was requested. A circuit with mid-circuit measurement, reset or classical control is not
    compiled, and every requested compile is recorded with dispatch_status "skipped" and
    the reason; a dispatch that fails is recorded as "error" for each compile, so the run's
    simulator results are kept either way."""
    if not compilers:
        return {}
    try:
        prepared = prepare_statevector_dispatch(qasm_string, apply_preprocessing)
    except StatevectorIncompatible:
        return {"compilers_requested": {cid: list(levels) for cid, levels in compilers.items()},
                "compile_input": None, "compiled_circuits": _unrun(compilers, "skipped", (
            "Not compiled: compile-only services take the unitary part of a circuit, and this "
            "circuit has a mid-circuit measurement, reset or classical control."))}
    except Exception as exc:
        logger.error("Preparing the compile input failed", exc_info=True)
        return {"compilers_requested": {cid: list(levels) for cid, levels in compilers.items()},
                "compile_input": None, "compiled_circuits": _unrun(
            compilers, "error", f"Not compiled: the compile input could not be prepared ({type(exc).__name__}).")}
    urls = {cid: f"{COMPILER_SERVICES[cid]['base_url']}/compile" for cid in compilers}
    payload = {"circuit_data": prepared["qasm"], "optimization_level": 0,
               "runner_config": {cid: list(levels) for cid, levels in compilers.items()}}
    compile_input = {"qasm": prepared["qasm"],
                     "api_preprocessing_applied": list(prepared["api_preprocessing_applied"]),
                     "derivation": COMPILE_INPUT_DERIVATION}
    token = EXCLUSIVE.set(False)
    try:
        results = await dispatch_to_runners(urls, payload, timeout_seconds, runner_statuses)
    except Exception as exc:
        logger.error("Compile dispatch failed", exc_info=True)
        return {"compilers_requested": {cid: list(levels) for cid, levels in compilers.items()},
                "compile_input": compile_input, "compiled_circuits": _unrun(
            compilers, "error", f"Not compiled: the compile dispatch failed ({type(exc).__name__}).")}
    finally:
        EXCLUSIVE.reset(token)
    return {"compilers_requested": {cid: list(levels) for cid, levels in compilers.items()},
            "compile_input": compile_input,
            "compiled_circuits": [_record(r) for r in results if isinstance(r, dict)]}
