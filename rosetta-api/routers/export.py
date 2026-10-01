"""RO-Crate export routes: from a report in the request body, or from a job's server copy."""

from config import settings
import asyncio
import io

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

import schemas
from routers.errors import responses
from services.security import limiter
from services.exporter import build_export_context, build_ro_crate
from services.report_validation import reject_invalid_report
from services.job_manager import job_report_or_error, report_failed_before_dispatch
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


@router.post("/export", responses=responses(400, 409, 413, 422))
@limiter.limit(settings.RUN_RATE_LIMIT)
async def export_ro_crate(request: Request, payload: schemas.ExportRequest):
    """Build an RO-Crate ZIP from the report supplied in the request body (subject to the
    1 MB upload limit). No authentication; nothing is stored. 409 for a report whose
    circuit never reached a runner (top-level error, no raw_results)."""
    if not payload.results:
        raise HTTPException(status_code=400, detail="No results provided to export")
    if report_failed_before_dispatch(payload.results):
        raise HTTPException(status_code=409, detail=f"This run failed before dispatch and has no results to export: {payload.results['error']}")
    reject_invalid_report(payload.results)
    return await _crate_response(payload.results, payload)


@router.post("/jobs/{job_id}/export", responses=responses(404, 409, 422))
@limiter.limit(settings.RUN_RATE_LIMIT)
async def export_job_ro_crate(request: Request, job_id: str, payload: schemas.ExportPayload):
    """Build an RO-Crate ZIP from the server's untruncated copy of a finished /compare,
    /compare_measured or /run_batch_suite job, including one whose runners all failed.
    With ``include_statevectors=true`` it carries every statevector the runners returned.
    404 if the job id is unknown or expired; 409 if the job has not finished, failed before
    any runner ran, or is an experiment (use GET /experiments/{job_id}/bundle)."""
    return await _crate_response(job_report_or_error(job_id, "export"), payload)
