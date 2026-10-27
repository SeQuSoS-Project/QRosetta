"""Verdict summary routes: each pair's verdict and the per-backend counts of a job's report or
of a report in the request body, computed by the rule new reports record."""

import asyncio

from fastapi import APIRouter, HTTPException, Request

from routers.errors import responses
from schemas import SummaryRequest
from schemas.reports import ReportSummary
from services.job_manager import job_with_report_or_error
from services.report_summary import batch_summary, report_summary, summary_problems, task_summary
from services.report_validation import REPORT_SHAPE_ERRORS, reject_invalid_report, unreadable_report
from services.security import limiter
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-summary-api")

router = APIRouter()


def _job_summary(job_id: str) -> dict:
    _, report = job_with_report_or_error(job_id, "summarise", each_task=task_summary)
    if isinstance(report.get("benchmark_summary"), list):
        return batch_summary(report["benchmark_summary"], "server_job")
    return report_summary(report, "server_job")


_SUMMARY_200 = {200: {"model": ReportSummary, "description": "The verdicts: a single-circuit report's at the top level, a playlist's per task in benchmark_summary."}}


@router.get("/jobs/{job_id}/summary", responses={
    **_SUMMARY_200, **responses(404, (409, "The job has not finished, failed before any runner ran, or is an experiment."))})
@limiter.limit("120/minute")
async def get_job_summary(request: Request, job_id: str):
    """Each pair's verdict and the per-backend counts of a finished job's report (a playlist:
    per task), with this server's analysis_version. The report records the same values in
    pair_verdict and divergence_report.backend_verdicts. 404 if the job id is unknown or
    expired; 409 if it has not finished, failed before any runner ran, or is an experiment."""
    return await asyncio.to_thread(_job_summary, job_id)


@router.post("/summary", responses={**_SUMMARY_200, **responses(
    (400, "A report that is not an object, a pair record that is not an object, a simulator key of the wrong form, or a field of the wrong type or shape."), 422)})
@limiter.limit("120/minute")
async def post_summary(request: Request, payload: SummaryRequest):
    """Each pair's verdict and the per-backend counts of the report in the body (a playlist:
    per task), computed with this server's rule (analysis_version) whatever the report
    records, so a report saved before pair_verdict existed gets the verdicts a new one
    records. report_source is client_supplied."""
    reject_invalid_report(payload.results)
    problems = summary_problems(payload.results)
    if problems:
        raise HTTPException(status_code=400, detail="Invalid report: " + "; ".join(problems) + ".")
    try:
        return await asyncio.to_thread(report_summary, payload.results, "client_supplied")
    except REPORT_SHAPE_ERRORS as exc:
        logger.warning("Could not summarise a supplied report", exc_info=True)
        raise unreadable_report(exc)
