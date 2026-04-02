from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse
import os
from services.report_manager import get_latest_report_path
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
    """Returns the enabled/disabled status of every runner. Single source of truth: config.py."""
    return JSONResponse(content=[
        {"id": name, "enabled": config.get("enabled", True)}
        for name, config in settings.get_runner_services().items()
    ])


@router.get("/download_latest_report")
def download_latest_report():
    report_path = get_latest_report_path()
    if not os.path.exists(report_path):
        return JSONResponse(content={"error": "No report available"}, status_code=404)
    return FileResponse(report_path, media_type="application/json", filename="full_quantum_report.json")
