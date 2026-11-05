"""Publication figures and tables: list the artifacts a report offers, and render one, from
a report posted by the browser or from the server's copy of a job."""

import asyncio
import io
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

import schemas
from services.security import limiter, render_rate_limit
from services.publication import ParameterError, UnknownArtifact, list_artifacts, render_artifact
from services.publication.theme import MIME_TYPES, RendererBusy, render_lock_wait
from config import settings
from services.publication.view_listing import views_listing
from schemas.reports import PublicationViews
from routers.errors import file_response, responses
from services.job_manager import finished_job_or_error
from services.job_store import JOB_NOT_FOUND, report_or_task
from services.report_validation import REPORT_SHAPE_ERRORS, reject_invalid_report, unreadable_report
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-publication-api")

router = APIRouter()

_LIST_ROUTE = "GET /jobs/{job_id}/publication/artifacts or POST /publication/artifacts"


PublicationArtifact = schemas.PublicationArtifact
PublicationArtifactsRequest = schemas.PublicationArtifactsRequest


def _mode(results: dict) -> str:
    return "measured" if "n_shots" in results else "statevector"


def _catalog(results: dict) -> list:
    return list_artifacts(results, _mode(results))


async def _supplied_catalog(results: dict) -> list:
    """The catalog of a client-supplied report; 400 when a field it reads has the wrong
    type or shape."""
    try:
        return await asyncio.to_thread(_catalog, results)
    except REPORT_SHAPE_ERRORS as exc:
        logger.warning("Could not list the artifacts of a supplied report", exc_info=True)
        raise unreadable_report(exc)


RENDER_RETRY_AFTER_SEC = 10


def _render_waiting_briefly(*args):
    with render_lock_wait(settings.RENDER_LOCK_WAIT_SEC):
        return render_artifact(*args)


async def _render_response(results: dict, artifact_id: str, fmt: str, scale: int, params: dict,
                           supplied: bool):
    """Render one artifact off the event loop and stream it; 404 for an artifact this report
    does not offer (the detail lists those it does), 400 for a format or parameter it does
    not take, and, for a client-supplied report, for a field of the wrong type or shape; 503
    with Retry-After when the figure renderer stays busy for RENDER_LOCK_WAIT_SEC."""
    try:
        data, mime, _ = await asyncio.to_thread(
            _render_waiting_briefly, results, _mode(results), artifact_id, fmt, scale, params, False)
    except RendererBusy:
        raise HTTPException(status_code=503, headers={"Retry-After": str(RENDER_RETRY_AFTER_SEC)},
                            detail="The figure renderer is busy with other requests; try again shortly.")
    except UnknownArtifact:
        catalog = await (_supplied_catalog(results) if supplied else asyncio.to_thread(_catalog, results))
        ids = [a["id"] for a in catalog]
        raise HTTPException(status_code=404, detail=(
            f"Unknown artifact {artifact_id!r} for this report; it offers: {', '.join(ids) or 'none'}. "
            f"{_LIST_ROUTE} lists them with their formats."))
    except ParameterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        if supplied and isinstance(exc, REPORT_SHAPE_ERRORS):
            logger.warning("Could not render an artifact of a supplied report", exc_info=True)
            raise unreadable_report(exc)
        logger.error("Publication render failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Render failed")
    return StreamingResponse(
        io.BytesIO(data),
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{artifact_id}.{fmt}"'},
    )


def _job_circuit_report(job_id: str, task: Optional[int]) -> dict:
    """The server's report of one circuit of ``job_id``; ``task`` picks a playlist circuit."""
    job = finished_job_or_error(job_id, "render")
    try:
        report, n_tasks = report_or_task(job, task)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=JOB_NOT_FOUND)
    if task is not None and report is None:
        raise HTTPException(status_code=404, detail=f"This job has no circuit {task}.")
    if task is None and n_tasks is not None:
        raise HTTPException(status_code=400, detail="This is a playlist job: give the circuit's index as task.")
    return report


_RENDERED = file_response("The rendered figure or table, in the media type of its format.",
                          *sorted(set(MIME_TYPES.values())))
_UNKNOWN_ARTIFACT = (404, "An artifact this report does not offer; the detail lists the ids it does.")
_RENDER_BUSY = (503, "The figure renderer stayed busy for RENDER_LOCK_WAIT_SEC; try again after Retry-After seconds.")
_JOB_404 = (404, "Unknown or expired job id, a task index the playlist does not have, or an artifact the report does not offer (the detail lists the ids it does).")
_JOB_400 = (400, "A playlist job without task, or a format or parameter the artifact does not take.")
_JOB_409 = (409, "The job has not finished, failed before any runner ran, or is an experiment.")


_SUPPLIED_400 = "a field of the report that holds a value of the wrong type or shape"


def _scale_range() -> tuple:
    metadata = schemas.PublicationRenderRequest.model_fields["scale"].metadata
    return (next(m.ge for m in metadata if getattr(m, "ge", None) is not None),
            next(m.le for m in metadata if getattr(m, "le", None) is not None))


@router.get("/publication/views", responses={200: {"model": PublicationViews, "description": "Every export view with its artifacts, parameters and formats."}})
@limiter.limit("120/minute")
async def publication_views(request: Request):
    """Every export view of the Exports tab, in its order: the artifact ids it renders (with the
    formats POST /jobs/{job_id}/publication/render takes), the formats of an export item of
    the view, and its parameters with their type, allowed values and default. Which views a
    given report offers: GET /jobs/{job_id}/publication/artifacts."""
    return views_listing(_scale_range())


@router.post("/publication/artifacts", response_model=List[PublicationArtifact],
             responses=responses((400, f"No report given, a runner key of the wrong form, or {_SUPPLIED_400}.")))
@limiter.limit("120/minute")
async def publication_artifacts(request: Request, payload: PublicationArtifactsRequest):
    """The figures and tables the report in the body offers: their artifact ids, formats and
    captions at default parameters. The report is measured when it has ``n_shots``."""
    if not payload.results:
        raise HTTPException(status_code=400, detail="No results provided")
    reject_invalid_report(payload.results)
    return await _supplied_catalog(payload.results)


@router.get("/jobs/{job_id}/publication/artifacts", response_model=List[PublicationArtifact],
            responses=responses(_JOB_400, _JOB_404, _JOB_409))
@limiter.limit("120/minute")
async def job_publication_artifacts(request: Request, job_id: str,
                                    task: Optional[int] = Query(None, ge=0, description="For a playlist job: the circuit's index in benchmark_summary.")):
    """The figures and tables the server's copy of a finished job offers: their artifact
    ids (for POST /jobs/{job_id}/publication/render), formats and captions at default
    parameters. ``task`` picks a circuit of a playlist job."""
    report = await asyncio.to_thread(_job_circuit_report, job_id, task)
    return await asyncio.to_thread(_catalog, report)


@router.post("/publication/render", response_class=StreamingResponse, responses={**_RENDERED, **responses(
    (400, "No report given, a runner key of the wrong form, a format or parameter the artifact "
          f"does not take, or {_SUPPLIED_400}."),
    _UNKNOWN_ARTIFACT, _RENDER_BUSY)})
@render_rate_limit
async def publication_render(request: Request, payload: schemas.PublicationRenderRequest):
    """Render a single publication figure (svg/png/pdf) or table with its view's ``params``
    from the report in the request body (subject to the 1 MB upload limit) and stream the
    bytes back. The report is measured when it has ``n_shots``. POST /publication/artifacts
    lists the artifact ids the report offers. 400 for a format or parameter the artifact
    does not take, or a report field of the wrong type or shape; 404 for an artifact the
    report does not offer."""
    if not payload.results:
        raise HTTPException(status_code=400, detail="No results provided")
    reject_invalid_report(payload.results)
    return await _render_response(payload.results, payload.artifact_id, payload.format,
                                  payload.scale, payload.params, supplied=True)


@router.post("/jobs/{job_id}/publication/render", response_class=StreamingResponse,
             responses={**_RENDERED, **responses(_JOB_400, _JOB_404, _JOB_409, _RENDER_BUSY)})
@render_rate_limit
async def job_publication_render(request: Request, job_id: str,
                                 payload: schemas.PublicationJobRenderRequest):
    """Render a single publication figure or table from the server's copy of a finished
    job, kept for up to limits.job_ttl_sec seconds after it completes; ``task`` picks a circuit of a playlist job and
    ``circuit_name`` names the circuit in titles and captions in place of the copy's own.
    GET /jobs/{job_id}/publication/artifacts lists the artifact ids. 404 for an unknown or
    expired job, an unknown artifact or task; 409 for an unfinished job or one with no
    report."""
    report = await asyncio.to_thread(_job_circuit_report, job_id, payload.task)
    if payload.circuit_name:
        report = {**report, "circuit_name": payload.circuit_name}
    return await _render_response(report, payload.artifact_id, payload.format, payload.scale,
                                  payload.params, supplied=False)
