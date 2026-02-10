from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse
import os
from services.report_manager import get_latest_report_path

router = APIRouter()

@router.get("/")
async def read_index():
    """Serves the main HTML page."""
    return FileResponse('static/index.html')

@router.get("/download_latest_report")
def download_latest_report():
    report_path = get_latest_report_path()
    if not os.path.exists(report_path):
        return JSONResponse(content={"error": "No report available"}, status_code=404)
    return FileResponse(report_path, media_type="application/json", filename="full_quantum_report.json")
