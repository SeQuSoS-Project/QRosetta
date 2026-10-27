"""GET /health (the process serves requests) and GET /ready (the database and the job storage
directory work too), for container healthchecks and Kubernetes probes. No sign-in, no rate
limit, and no detail beyond which check failed."""

from typing import Dict, Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services import readiness

router = APIRouter(tags=["health"])

_NO_STORE = {"Cache-Control": "no-store"}

CheckResult = Literal["ok", "failed", "timeout"]


class Health(BaseModel):
    status: Literal["ok"]


class Ready(BaseModel):
    status: Literal["ready"]
    checks: Dict[str, CheckResult] = Field(..., description="database (SELECT 1) and job_storage (a new file in the job spill directory): ok.")


class NotReady(BaseModel):
    detail: str = Field(..., description="'Not ready: ' and the failed checks in words.")
    status: Literal["not_ready"]
    checks: Dict[str, CheckResult] = Field(..., description="Each check: ok, failed, or timeout (no answer within 2 s).")


@router.get("/health", responses={200: {"model": Health, "description": "The API process is serving requests."}})
async def health():
    """200 while the process serves requests. Touches nothing else, so it reads the same
    while the database or the job storage is down."""
    return JSONResponse({"status": "ok"}, headers=_NO_STORE)


@router.get("/ready", responses={
    200: {"model": Ready, "description": "The database answers and the job storage directory takes new files."},
    503: {"model": NotReady, "description": "A check failed or did not answer within 2 s."},
})
async def ready():
    """200 when the database answers ``SELECT 1`` and the job spill directory takes a new
    file, else 503 naming the failed checks. A result less than 1 s old is served again."""
    checks = await readiness.check()
    failed = [name for name, result in checks.items() if result != "ok"]
    if not failed:
        return JSONResponse({"status": "ready", "checks": checks}, headers=_NO_STORE)
    detail = "Not ready: " + "; ".join(readiness.REASONS[name] for name in failed) + "."
    return JSONResponse(status_code=503, headers=_NO_STORE,
                        content={"detail": detail, "status": "not_ready", "checks": checks})
