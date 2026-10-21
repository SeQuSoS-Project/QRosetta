"""RO-Crate export routes: from a report in the request body, or from a job's server copy."""

from config import settings
import asyncio

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

import schemas
from routers.errors import responses
from services.security import limiter
from services.exporter import build_export_context, crate_name, export_skeleton_task, write_ro_crate
from services.publication.views import ParameterError
from services.report_validation import reject_invalid_report
from services.job_manager import finished_job_or_error, report_failed_before_dispatch
from services.job_store import JOB_NOT_FOUND, file_chunks, report_with_task_loader, written_file
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-export")

router = APIRouter()


def _crate_file(ctx):
    return ctx, written_file(lambda fh: write_ro_crate(ctx, fh))


def _job_crate_file(job_id: str, payload):
    """(context, crate file) of a finished job's server copy, its batch tasks read from disk
    one at a time; 404 when the job expires meanwhile."""
    job = finished_job_or_error(job_id, "export")
    try:
        report, load = report_with_task_loader(job, export_skeleton_task)
        return _crate_file(build_export_context(report, payload, "server_job", task_loader=load))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=JOB_NOT_FOUND)


async def _crate_response(build, *args) -> StreamingResponse:
    """Write the RO-Crate ZIP (``build(*args)`` -> (context, file)) off the event loop to a
    temporary file and stream it as an attachment."""
    try:
        ctx, fh = await asyncio.to_thread(build, *args)
    except HTTPException:
        raise
    except ParameterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.error("RO-Crate export failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Export failed")

    return StreamingResponse(
        file_chunks(fh),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{crate_name(ctx)}.zip"'},
    )


@router.post("/export", responses=responses(
    (400, "No report given, a runner key of the wrong form, or an export option the report cannot take."),
    (409, "The report's circuit never reached a runner (top-level error, no raw_results)."), 413, 422))
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
    return await _crate_response(
        _crate_file, build_export_context(payload.results, payload, "client_request"))


@router.post("/jobs/{job_id}/export", responses=responses(
    (400, "An export option the report cannot take (e.g. a publication view parameter)."), 404, 409, 422))
@limiter.limit(settings.RUN_RATE_LIMIT)
async def export_job_ro_crate(request: Request, job_id: str,
                              payload: schemas.ExportPayload | None = None):
    """Build an RO-Crate ZIP from the server's untruncated copy of a finished /compare,
    /compare_measured or /run_batch_suite job, including one whose runners all failed.
    With ``include_statevectors=true`` it carries every statevector the runners returned.
    The body is optional; every option has a default. 404 if the job id is unknown or
    expired; 409 if the job has not finished, failed before any runner ran, or is an
    experiment (use GET /experiments/{job_id}/bundle); 400 for an export option the report
    cannot take."""
    return await _crate_response(_job_crate_file, job_id, payload or schemas.ExportPayload())
