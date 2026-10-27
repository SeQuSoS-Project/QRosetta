"""RO-Crate export routes: from a report in the request body, or from a job's server copy."""

import asyncio

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

import schemas
from routers.errors import file_response, responses
from services.security import run_rate_limit
from services.exporter import build_export_context, crate_name, export_skeleton_task, write_ro_crate
from services.publication.views import ParameterError
from services.report_validation import REPORT_SHAPE_ERRORS, reject_invalid_report, unreadable_report
from services import gated_saves
from services.job_manager import finished_job_or_error, report_failed_before_dispatch
from services.job_store import JOB_NOT_FOUND, file_chunks, report_with_task_loader, written_file
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-export")

router = APIRouter()


def _crate_file(ctx):
    return ctx, written_file(lambda fh: write_ro_crate(ctx, fh))


def _client_crate_file(results: dict, payload):
    """(context, crate file) of a report supplied in the request body."""
    return _crate_file(build_export_context(results, payload, "client_request"))


def _job_crate_file(job_id: str, payload):
    """(context, crate file) of a finished job's server copy, its batch tasks read from disk
    one at a time; 404 when the job expires meanwhile."""
    job = finished_job_or_error(job_id, "export")
    try:
        report, load = report_with_task_loader(job, export_skeleton_task)
        return _crate_file(build_export_context(report, payload, "server_job", task_loader=load))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=JOB_NOT_FOUND)


async def _crate_response(build, *args, supplied: bool = False, gated_job: dict = None) -> StreamingResponse:
    """Write the RO-Crate ZIP (``build(*args)`` -> (context, file)) off the event loop to a
    temporary file and stream it as an attachment. A report in the request body
    (``supplied``) that the builder cannot read is a 400. With ``gated_job`` the crate is
    built and sent under a gated save of that job (``services.gated_saves``)."""
    lease = None
    try:
        if gated_job is not None:
            lease, (ctx, fh) = await gated_saves.build_gated(gated_job, "crate", build, *args)
        else:
            ctx, fh = await asyncio.to_thread(build, *args)
    except HTTPException:
        raise
    except ParameterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        if supplied and isinstance(exc, REPORT_SHAPE_ERRORS):
            logger.warning("Could not export a supplied report", exc_info=True)
            raise unreadable_report(exc)
        logger.error("RO-Crate export failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Export failed")

    headers = {"Content-Disposition": f'attachment; filename="{crate_name(ctx)}.zip"'}
    if lease is not None:
        return StreamingResponse(media_type="application/zip", headers=headers, **lease.body(file_chunks(fh)))
    return StreamingResponse(file_chunks(fh), media_type="application/zip", headers=headers)


_CRATE = file_response("The RO-Crate ZIP, sent as an attachment.", "application/zip")


@router.post("/export", response_class=StreamingResponse, responses={**_CRATE, **responses(
    (400, "No report given, a runner key of the wrong form, an export option the report cannot "
          "take, or a field of the report that holds a value of the wrong type or shape."),
    (409, "The report's circuit never reached a runner (top-level error, no raw_results)."), 413, 422)})
@run_rate_limit
async def export_ro_crate(request: Request, payload: schemas.ExportRequest):
    """Build an RO-Crate ZIP from the report supplied in the request body (subject to the
    1 MB upload limit). No authentication; nothing is stored. 409 for a report whose
    circuit never reached a runner (top-level error, no raw_results)."""
    if not payload.results:
        raise HTTPException(status_code=400, detail="No results provided to export")
    if report_failed_before_dispatch(payload.results):
        raise HTTPException(status_code=409, detail=f"This run failed before dispatch and has no results to export: {payload.results['error']}")
    reject_invalid_report(payload.results)
    return await _crate_response(_client_crate_file, payload.results, payload, supplied=True)


@router.post("/jobs/{job_id}/export", response_class=StreamingResponse, responses={**_CRATE, **responses(
    (400, "An export option the report cannot take (e.g. a publication view parameter)."), 404,
    (409, "The job has not finished, failed before any runner ran, or is an experiment; or, with "
          "gated=true, gate_busy: a dispatch is in flight (sent with Retry-After)."), 422)})
@run_rate_limit
async def export_job_ro_crate(request: Request, job_id: str,
                              payload: schemas.ExportPayload | None = None, gated: bool = False):
    """Build an RO-Crate ZIP from the server's untruncated copy of a finished /compare,
    /compare_measured or /run_batch_suite job, including one whose runners all failed.
    With ``include_statevectors=true`` it carries every statevector the runners returned.
    The body is optional; every option has a default. 404 if the job id is unknown or
    expired; 409 if the job has not finished, failed before any runner ran, or is an
    experiment (use GET /experiments/{job_id}/bundle); 400 for an export option the report
    cannot take.

    ``gated=true`` builds and sends the crate only while no dispatch is in flight on this
    server, and dispatches submitted meanwhile wait until it has been sent (their
    ``gate_wait_sec``); while one is in flight it answers 409 with a detail starting
    ``gate_busy`` and Retry-After. The job records its save requests under ``saves``."""
    job = finished_job_or_error(job_id, "export")
    if not gated:
        gated_saves.note_ungated(job, "crate")
    return await _crate_response(_job_crate_file, job_id, payload or schemas.ExportPayload(),
                                 gated_job=job if gated else None)
