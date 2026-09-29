"""Frontend routes: the index page, the runner registry, and client-facing limits."""

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse
from config import settings

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
    """Enabled status, max optimization level, and per-level descriptions for every runner."""
    result = []
    for name, config in settings.get_runner_services().items():
        opt_levels = config.get("optimization_levels", {})

        opt_levels_str = {str(k): v for k, v in opt_levels.items()}
        result.append({
            "id": name,
            "enabled": config.get("enabled", True),
            "max_level": max(opt_levels.keys()) if opt_levels else 0,
            "optimization_levels": opt_levels_str,
        })
    return JSONResponse(content=result)

@router.get("/config")
async def get_config():
    """Server-side circuit limits and execution mode."""
    return JSONResponse(content={
        "max_qubits_statevector": settings.MAX_QUBITS_STATEVECTOR,
        "max_qubits_measured": settings.MAX_QUBITS_MEASURED,
        "max_qasm_size": settings.MAX_QASM_SIZE,
        "max_qasm_gates": settings.MAX_QASM_GATES,
        "max_runs_per_runner": settings.MAX_RUNS_PER_RUNNER,
        "max_total_runs": settings.MAX_TOTAL_RUNS,
        "execution_mode": settings.EXECUTION_MODE,
    })
