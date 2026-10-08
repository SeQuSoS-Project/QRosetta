"""Publication figures and tables: list the artifacts a report offers, and render one, from
a report posted by the browser or from the server's copy of a job."""

import asyncio
import io
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

import schemas
from services.security import limiter
from services.publication import ParameterError, list_artifacts, render_artifact
from routers.errors import responses
from services.job_manager import job_report_or_error
from services.report_validation import reject_invalid_report
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


async def _render_response(results: dict, artifact_id: str, fmt: str, scale: int, params: dict):
    """Render one artifact off the event loop and stream it; 404 for an artifact this report
    does not offer (the detail lists those it does), 400 for a format or parameter it does
    not take."""
    try:
        data, mime, _ = await asyncio.to_thread(
            render_artifact, results, _mode(results), artifact_id, fmt, scale, params, False)
    except KeyError:
        ids = [a["id"] for a in await asyncio.to_thread(_catalog, results)]
        raise HTTPException(status_code=404, detail=(
            f"Unknown artifact {artifact_id!r} for this report; it offers: {', '.join(ids) or 'none'}. "
            f"{_LIST_ROUTE} lists them with their formats."))
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


def _job_circuit_report(job_id: str, task: Optional[int]) -> dict:
    """The server's report of one circuit of ``job_id``; ``task`` picks a playlist circuit."""
    report = job_report_or_error(job_id, "render")
    tasks = report.get("benchmark_summary")
    if task is not None:
        if not isinstance(tasks, list) or task >= len(tasks):
            raise HTTPException(status_code=404, detail=f"This job has no circuit {task}.")
        return tasks[task]
    if isinstance(tasks, list):
        raise HTTPException(status_code=400, detail="This is a playlist job: give the circuit's index as task.")
    return report


_UNKNOWN_ARTIFACT = (404, "An artifact this report does not offer; the detail lists the ids it does.")
_JOB_404 = (404, "Unknown or expired job id, a task index the playlist does not have, or an artifact the report does not offer (the detail lists the ids it does).")
_JOB_400 = (400, "A playlist job without task, or a format or parameter the artifact does not take.")
_JOB_409 = (409, "The job has not finished, failed before any runner ran, or is an experiment.")


@router.post("/publication/artifacts", response_model=List[PublicationArtifact],
             responses=responses((400, "No report given, or a runner key of the wrong form.")))
@limiter.limit("120/minute")
async def publication_artifacts(request: Request, payload: PublicationArtifactsRequest):
    """The figures and tables the report in the body offers: their artifact ids, formats and
    captions at default parameters. The report is measured when it has ``n_shots``."""
    if not payload.results:
        raise HTTPException(status_code=400, detail="No results provided")
    reject_invalid_report(payload.results)
    return await asyncio.to_thread(_catalog, payload.results)


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


@router.post("/publication/render", responses=responses(
    (400, "No report given, a runner key of the wrong form, or a format or parameter the artifact does not take."),
    _UNKNOWN_ARTIFACT))
@limiter.limit("120/minute")
async def publication_render(request: Request, payload: schemas.PublicationRenderRequest):
    """Render a single publication figure (svg/png/pdf) or table with its view's ``params``
    from the report in the request body (subject to the 1 MB upload limit) and stream the
    bytes back. The report is measured when it has ``n_shots``. POST /publication/artifacts
    lists the artifact ids the report offers. 400 for a format or parameter the artifact
    does not take; 404 for an artifact the report does not offer."""
    if not payload.results:
        raise HTTPException(status_code=400, detail="No results provided")
    reject_invalid_report(payload.results)
    return await _render_response(payload.results, payload.artifact_id, payload.format,
                                  payload.scale, payload.params)


@router.post("/jobs/{job_id}/publication/render", responses=responses(_JOB_400, _JOB_404, _JOB_409))
@limiter.limit("120/minute")
async def job_publication_render(request: Request, job_id: str,
                                 payload: schemas.PublicationJobRenderRequest):
    """Render a single publication figure or table from the server's copy of a finished
    job, kept for 30 minutes after it completes; ``task`` picks a circuit of a playlist job and
    ``circuit_name`` names the circuit in titles and captions in place of the copy's own.
    GET /jobs/{job_id}/publication/artifacts lists the artifact ids. 404 for an unknown or
    expired job, an unknown artifact or task; 409 for an unfinished job or one with no
    report."""
    report = await asyncio.to_thread(_job_circuit_report, job_id, payload.task)
    if payload.circuit_name:
        report = {**report, "circuit_name": payload.circuit_name}
    return await _render_response(report, payload.artifact_id, payload.format, payload.scale,
                                  payload.params)
