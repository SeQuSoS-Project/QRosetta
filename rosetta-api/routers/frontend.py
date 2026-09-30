"""Frontend routes: the index page, the runner registry, and client-facing limits."""

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse
from config import settings
from schemas import AgreementThresholds
from services.availability import runner_availability

router = APIRouter()

@router.get("/")
async def read_index():
    """Serves the main HTML page."""
    return FileResponse(
        'static/index.html',
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0"}
    )

@router.get("/runners")
async def get_runners():
    """Enabled status, availability, max optimization level, and per-level descriptions for
    every runner.

    ``available`` is False for a disabled runner (``unavailable_reason`` "disabled"), and
    for an enabled one that cannot run here: unreachable, or reporting no usable device
    via its GET /capabilities, or (Kubernetes, or a runner without that endpoint)
    ``requires_gpu`` on a deployment without QROSETTA_GPU_AVAILABLE. Probes are cached
    for 60 s. ``device`` is what the runner's /capabilities reported, else None.
    """
    services = settings.get_runner_services()
    availability = await runner_availability()
    result = []
    for name, config in services.items():
        opt_levels = config.get("optimization_levels", {})

        opt_levels_str = {str(k): v for k, v in opt_levels.items()}
        enabled = config.get("enabled", True)
        info = availability.get(name) or {"available": False, "reason": "disabled", "device": None}
        result.append({
            "id": name,
            "enabled": enabled,
            "available": bool(enabled and info["available"]),
            "unavailable_reason": None if (enabled and info["available"]) else (info["reason"] or "unavailable"),
            "device": info.get("device"),
            "requires_gpu": bool(config.get("requires_gpu", False)),
            "max_level": max(opt_levels.keys()) if opt_levels else 0,
            "optimization_levels": opt_levels_str,
        })
    return JSONResponse(content=result)

@router.get("/config")
async def get_config():
    """Server-side circuit limits, request bounds, agreement-threshold defaults and the
    execution mode.

    ``limits`` holds the bounds the run endpoints validate against: qubit caps per mode,
    ``timeout_min``/``timeout_max`` (seconds; larger requests are clamped to
    ``timeout_max``) and ``shots_min``/``shots_max``. The top-level qubit and size keys are
    kept for existing clients.
    """
    return JSONResponse(content={
        "max_qubits_statevector": settings.MAX_QUBITS_STATEVECTOR,
        "max_qubits_measured": settings.MAX_QUBITS_MEASURED,
        "max_qasm_size": settings.MAX_QASM_SIZE,
        "max_qasm_gates": settings.MAX_QASM_GATES,
        "max_runs_per_runner": settings.MAX_RUNS_PER_RUNNER,
        "max_total_runs": settings.MAX_TOTAL_RUNS,
        "execution_mode": settings.EXECUTION_MODE,
        "queue_max_wait_sec": settings.RUNNER_QUEUE_MAX_WAIT_SEC,
        "agreement_threshold_defaults": AgreementThresholds().model_dump(),
        "limits": {
            "max_qubits_statevector": settings.MAX_QUBITS_STATEVECTOR,
            "max_qubits_measured": settings.MAX_QUBITS_MEASURED,
            "timeout_min": settings.MIN_TIMEOUT_SEC,
            "timeout_max": settings.RUNNER_TIMEOUT_SEC,
            "shots_min": settings.MIN_SHOTS,
            "shots_max": settings.MAX_SHOTS,
        },
    })
