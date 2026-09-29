"""RO-Crate export routes: from a report in the request body, or from a job's server copy."""

from config import settings
import asyncio
import io

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

import schemas
from services.security import limiter
from services.exporter import build_export_context, build_ro_crate
from services.job_manager import ACTIVE_JOBS
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-export")

router = APIRouter()


async def _crate_response(results: dict, payload) -> StreamingResponse:
    """Build the RO-Crate ZIP off the event loop and stream it as an attachment."""
    ctx = build_export_context(results, payload)
    try:
        zip_bytes = await asyncio.to_thread(build_ro_crate, ctx)
    except Exception:
        logger.error("RO-Crate export failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Export failed")

    ts_slug = ctx.timestamp.replace(":", "-").replace("+", "p")
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="rosetta-export-{ts_slug}.zip"'},
    )


@router.post("/export")
@limiter.limit(settings.RUN_RATE_LIMIT)
async def export_ro_crate(request: Request, payload: schemas.ExportRequest):
    """Build an RO-Crate ZIP from the report supplied in the request body (subject to the
    1 MB upload limit). No authentication; nothing is stored."""
    if not payload.results:
        raise HTTPException(status_code=400, detail="No results provided to export")
    return await _crate_response(payload.results, payload)


@router.post("/jobs/{job_id}/export")
@limiter.limit(settings.RUN_RATE_LIMIT)
async def export_job_ro_crate(request: Request, job_id: str, payload: schemas.ExportPayload):
    """Build an RO-Crate ZIP from the server's untruncated copy of a completed /compare,
    /compare_measured or /run_batch_suite job. With ``include_statevectors=true`` it carries
    every statevector the runners returned. 404 if the job id is unknown or expired, 409 if
    the job has not completed or has no server copy (e.g. an experiment job)."""
    job = ACTIVE_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "completed" or not job.get("full_results"):
        raise HTTPException(status_code=409, detail=f"No exportable report for this job (status: {job.get('status')})")
    return await _crate_response(job["full_results"], payload)
