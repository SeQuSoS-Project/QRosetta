"""The circuit texts of a finished job, as the Circuits view shows them: submitted, dispatched
per runner group, executed per backend, compile input and compiled, with the share-link
allowlist's fields."""

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from routers.errors import responses
from schemas.reports import CircuitTexts
from services.circuit_texts import report_circuits, task_panes
from services.job_manager import finished_job_or_error, job_with_report_or_error
from services.job_store import JOB_NOT_FOUND, report_or_task
from services.security import limiter

router = APIRouter()


def _job_circuits(job_id: str, task: Optional[int]) -> dict:
    if task is None:
        _, report = job_with_report_or_error(job_id, "read", each_task=task_panes)
        circuits = report_circuits(report)
    else:
        job = finished_job_or_error(job_id, "read")
        try:
            report, n_tasks = report_or_task(job, task)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=JOB_NOT_FOUND)
        if n_tasks is None:
            raise HTTPException(status_code=400, detail="This job has one circuit; leave out task.")
        if report is None:
            raise HTTPException(status_code=404, detail=f"This job has no circuit {task}.")
        circuits = [task_panes(report, task)]
    return {"job_id": job_id, "report_source": "server_job", "circuits": circuits}


@router.get("/jobs/{job_id}/circuit-texts", responses={
    200: {"model": CircuitTexts, "description": "The panes of each circuit, in the Circuits view's order."},
    **responses((400, "task given for a single-circuit job."),
                (404, "Unknown or expired job id, or a task index the playlist does not have."),
                (409, "The job has not finished, failed before any runner ran, or is an experiment."))})
@limiter.limit("120/minute")
async def get_job_circuit_texts(request: Request, job_id: str,
                                task: Optional[int] = Query(None, ge=0, description="For a playlist job: one circuit's index in benchmark_summary.")):
    """The circuit texts of a finished job, kept for up to limits.job_ttl_sec seconds after it
    completes: per circuit, the panes of the page's Circuits view (submitted, dispatched per
    runner group, executed per backend, compile input, compiled) with their ids and the
    share-link allowlist's fields (transforms, gate metrics, status, SDK versions; no error
    text, timings or outputs). ``task`` picks one circuit of a playlist job."""
    return await asyncio.to_thread(_job_circuits, job_id, task)
