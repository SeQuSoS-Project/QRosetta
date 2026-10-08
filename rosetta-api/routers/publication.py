"""On-demand rendering of one publication figure or table, from a report posted by the
browser or from the server's copy of a job."""

import asyncio
import io

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

import schemas
from services.security import limiter
from services.publication import ParameterError, render_artifact
from routers.errors import responses
from services.job_manager import job_report_or_error
from services.report_validation import reject_invalid_report
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-publication-api")

router = APIRouter()


async def _render_response(results: dict, artifact_id: str, fmt: str, scale: int, params: dict):
    """Render one artifact off the event loop and stream it; 404 for an unknown artifact,
    400 for a format or parameter it does not take."""
    mode = "measured" if "n_shots" in results else "statevector"
    try:
        data, mime, _ = await asyncio.to_thread(
            render_artifact, results, mode, artifact_id, fmt, scale, params, False)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown artifact: {artifact_id}")
    except ParameterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.error("Publication render failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Render failed")
    return StreamingResponse(
        io.BytesIO(data),
        media_type=mime,
        headers={"Content-Disposition": f'inline; filename="{artifact_id}.{fmt}"'},
    )


@router.post("/publication/render")
@limiter.limit("120/minute")
async def publication_render(request: Request, payload: schemas.PublicationRenderRequest):
    """Render a single publication figure (svg/png/pdf) or table with its view's ``params``
    from the report in the request body (subject to the 1 MB upload limit) and stream the
    bytes back. The report is measured when it has ``n_shots``. 400 for a format or
    parameter the artifact does not take."""
    if not payload.results:
        raise HTTPException(status_code=400, detail="No results provided")
    reject_invalid_report(payload.results)
    return await _render_response(payload.results, payload.artifact_id, payload.format,
                                  payload.scale, payload.params)


@router.post("/jobs/{job_id}/publication/render", responses=responses(400, 404, 409))
@limiter.limit("120/minute")
async def job_publication_render(request: Request, job_id: str,
                                 payload: schemas.PublicationJobRenderRequest):
    """Render a single publication figure or table from the server's copy of a finished
    job, kept for 30 minutes after it completes; ``task`` picks a circuit of a playlist job and
    ``circuit_name`` names the circuit in titles and captions in place of the copy's own.
    404 for an unknown or expired job, an unknown artifact or task; 409 for an unfinished
    job or one with no report."""
    report = await asyncio.to_thread(job_report_or_error, job_id, "render")
    tasks = report.get("benchmark_summary")
    if payload.task is not None:
        if not isinstance(tasks, list) or payload.task >= len(tasks):
            raise HTTPException(status_code=404, detail=f"This job has no circuit {payload.task}.")
        report = tasks[payload.task]
    elif isinstance(tasks, list):
        raise HTTPException(status_code=400, detail="This is a playlist job: give the circuit's index as task.")
    if payload.circuit_name:
        report = {**report, "circuit_name": payload.circuit_name}
    return await _render_response(report, payload.artifact_id, payload.format, payload.scale,
                                  payload.params)
