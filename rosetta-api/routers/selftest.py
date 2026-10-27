"""Self-test routes: the pinned plan (circuits, settings, expected answers, check rules) and
the evaluation of a finished self-test job against it."""

import asyncio

from fastapi import APIRouter, HTTPException, Request

from routers.errors import responses
from schemas.selftest import SelftestPlan, SelftestResult
from services.job_manager import job_with_report_or_error
from services.security import limiter
from services.selftest.evaluate import NotSelftestJob, evaluate_report, evaluate_task
from services.selftest.plan import selftest_plan

router = APIRouter()


@router.get("/selftest", responses={200: {"model": SelftestPlan, "description": "The self-test plan."}})
@limiter.limit("120/minute")
async def get_selftest(request: Request):
    """The self-test plan: two playlist requests for POST /run_batch_suite (statevector and
    measured) with every field pinned except target_simulators, the circuits as QASM, each
    circuit's expected answer per declared bit order (computed by a numpy reference, not by
    any backend), the known-answer and environment checks with their PASS/WARN/FAIL rules,
    and selftest_version. Submit both requests, then read GET /jobs/{job_id}/selftest-result
    for each job."""
    return await asyncio.to_thread(selftest_plan)


def _job_result(job_id: str) -> dict:
    _, report = job_with_report_or_error(job_id, "evaluate", each_task=evaluate_task)
    try:
        return evaluate_report(report, job_id)
    except NotSelftestJob as exc:
        raise HTTPException(status_code=409, detail=f"This job is not a self-test job: {exc}.")


@router.get("/jobs/{job_id}/selftest-result", responses={
    200: {"model": SelftestResult, "description": "Per-check PASS/WARN/FAIL/SKIP rows of one self-test job."},
    **responses(404, (409, "The job has not finished, failed before any runner ran, is an "
                           "experiment, or is not a playlist of a self-test plan part."))})
@limiter.limit("120/minute")
async def get_selftest_result(request: Request, job_id: str):
    """Evaluate a finished self-test job (one part of the GET /selftest plan) from the
    server's own copy of its report: each backend's result for each circuit against the
    plan's expected answer in that backend's declared bit order, the job's recorded
    settings against the plan, and the environment each result records. status is FAIL
    when any row FAILs, else WARN when any row WARNs, else PASS. 404 if the job id is
    unknown or expired; 409 if it has not finished, failed before any runner ran, is an
    experiment, or is not a self-test playlist."""
    return await asyncio.to_thread(_job_result, job_id)
