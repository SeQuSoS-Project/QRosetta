# FastAPI router endpoints for frontend.

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse
import os
from services.storage import get_latest_report_path
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
    """Returns enabled status, max optimization level, and per-level descriptions for every runner.
    Single source of truth: config.py."""
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
    """Returns server-side circuit limits so the frontend never hardcodes them."""
    return JSONResponse(content={
        "max_qubits_statevector": settings.MAX_QUBITS_STATEVECTOR,
        "max_qubits_measured": settings.MAX_QUBITS_MEASURED,
        "max_qasm_size": settings.MAX_QASM_SIZE,
        "max_qasm_gates": settings.MAX_QASM_GATES,
        "max_runs_per_runner": settings.MAX_RUNS_PER_RUNNER,
        "max_total_runs": settings.MAX_TOTAL_RUNS,
    })

@router.get("/download_latest_report")
def download_latest_report():
    report_path = get_latest_report_path()
    if not os.path.exists(report_path):
        return JSONResponse(content={"error": "No report available"}, status_code=404)
    return FileResponse(report_path, media_type="application/json", filename="full_quantum_report.json")
