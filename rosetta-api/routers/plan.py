"""POST /plan: the run requests a workspace makes, and the problems the server would refuse."""

import asyncio

from fastapi import APIRouter, Depends, Request

from config import settings
from routers.errors import responses
from schemas.plan import PlanRequest, PlanResponse
from services.plan import check_settings, circuit_problems, limit_problems, plan_runs, request_problems
from services.security import get_optional_user, limiter

router = APIRouter()


@router.post("/plan", response_model=PlanResponse, responses=responses(
    (400, "A setting that is not a run request field, that the planner sets itself, or that has its own option given with source 'set'."),
    413, 422, 429))
@limiter.limit(settings.PLAN_RATE_LIMIT)
async def plan_endpoint(request: Request, payload: PlanRequest, user=Depends(get_optional_user)):
    """Plan the run requests for circuits, modes, preprocessing, compile-only services, a run
    name and explicit settings, as the page's Run button and ``qrosetta run`` do; nothing is
    run. Two modes make two jobs (compilers go with the first), preprocessing 'both' makes
    experiments, no mode with compilers makes a compile-only run. Each planned run has
    ``endpoint``, ``kind``, ``mode``, ``title``, the ``payload`` to POST unchanged, and
    ``sources`` (each payload field's source: the setting's, or 'plan').

    ``problems`` lists why the server would refuse the plan, each with a stable ``code``,
    ``params``, a ``message``, and ``run_index``/``circuit_index``/``line`` where they apply:
    playlist_empty, editor_empty, no_mode and compile_only_needs_one_setting (nothing could be
    planned); playlist_too_long, bundled_over_prep_limit, experiment_too_many_cells,
    circuit_too_large and request_too_large (server limits; the request size is the payload
    as JSON.stringify writes it, in UTF-8); invalid_request (the payload fails its request
    schema); bypass_needs_account; and, with ``check_circuits``, circuit_refused for each
    literal circuit the run route's checks refuse. A setting whose source is 'set' may not
    name a field that has its own option (400)."""
    check_settings(payload.settings)
    runs, problem = plan_runs(payload)
    if problem:
        return {"schema": "qrosetta.plan@1", "runs": [], "problems": [problem]}
    problems = await asyncio.to_thread(limit_problems, runs)
    problems += request_problems(runs, signed_in=user is not None)
    if payload.check_circuits:
        problems += await asyncio.to_thread(circuit_problems, runs)
    return {"schema": "qrosetta.plan@1", "runs": runs, "problems": problems}
