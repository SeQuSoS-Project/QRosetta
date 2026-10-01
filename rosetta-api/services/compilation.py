"""Compile-only services for a run: check the requested compilers, compile the circuit the
API prepares for statevector runners, and record each output in the report.

Compilers run after the job's simulators have finished, through the same dispatch (gate,
queue and timeouts), so a compile never overlaps a timed run of its own job. Their results
are kept apart from raw_results: they are circuit text, never simulated or compared.
"""

from fastapi import HTTPException

from config import settings
from services.circuit_resolver import StatevectorIncompatible, prepare_statevector_dispatch
from services.dispatcher import dispatch_to_runners

COMPILER_SERVICES = settings.get_compiler_services()

COMPILE_INPUT_DERIVATION = (
    "The submitted circuit as the API prepares it for statevector runners: terminal "
    "measurements removed, then the run's API preprocessing (see api_preprocessing_applied).")

_COPIED_FIELDS = ("optimization_level", "transpiled_qasm", "passes_applied", "gate_count",
                  "circuit_depth", "gate_metrics_basis", "sdk_versions", "dispatch_status",
                  "error", "queue_wait_sec", "runner_image", "dispatched_at", "completed_at")


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


def _record(result: dict) -> dict:
    cid = _compiler_id(str(result.get("simulator")))
    record = {"compiler": result.get("simulator"), "compiler_id": cid, "compiler_name": _name(cid)}
    record.update({field: result[field] for field in _COPIED_FIELDS if field in result})
    if "runner_code_sha256" in result:
        record["compiler_code_sha256"] = result["runner_code_sha256"]
    return record


def _skipped(compilers: dict, reason: str) -> list:
    return [{"compiler": cid if len(levels) == 1 else f"{cid}~opt{lvl}~run1", "compiler_id": cid,
             "compiler_name": _name(cid), "optimization_level": lvl, "dispatch_status": "skipped",
             "error": reason}
            for cid, levels in compilers.items() for lvl in levels]


async def compile_circuit(qasm_string: str, apply_preprocessing: bool, compilers: dict,
                          timeout_seconds: int) -> dict:
    """``{"compile_input", "compiled_circuits"}`` for the report, or ``{}`` when no compiler
    was requested. A circuit statevector runners cannot take (mid-circuit measurement,
    reset, classical control) is not compiled; every requested compile is then recorded
    with dispatch_status "skipped" and the reason."""
    if not compilers:
        return {}
    try:
        prepared = prepare_statevector_dispatch(qasm_string, apply_preprocessing)
    except StatevectorIncompatible as exc:
        return {"compile_input": None,
                "compiled_circuits": _skipped(compilers, f"Not compiled: {exc}")}
    urls = {cid: f"{COMPILER_SERVICES[cid]['base_url']}/compile" for cid in compilers}
    payload = {"circuit_data": prepared["qasm"], "optimization_level": 0,
               "runner_config": {cid: list(levels) for cid, levels in compilers.items()}}
    results = await dispatch_to_runners(urls, payload, timeout_seconds)
    return {
        "compile_input": {"qasm": prepared["qasm"],
                          "api_preprocessing_applied": list(prepared["api_preprocessing_applied"]),
                          "derivation": COMPILE_INPUT_DERIVATION},
        "compiled_circuits": [_record(r) for r in results if isinstance(r, dict)],
    }
