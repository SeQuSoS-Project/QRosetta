"""POST /timing-caveats: the timing caveats of runner results that were stored without them
(reports saved or downloaded before the server recorded them)."""

from typing import Any, Dict, List

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from routers.errors import responses
from services.security import limiter
from services.timing_caveats import derive

router = APIRouter(tags=["benchmark"])

MAX_RESULTS = 5000


class TimingCaveatsRequest(BaseModel):
    """Runner results of one report (statevectors, counts and circuit texts may be left out)."""
    model_config = ConfigDict(extra="forbid")
    raw_results: List[Dict[str, Any]] = Field(..., max_length=MAX_RESULTS)


class TimingCaveat(BaseModel):
    code: str
    text: str
    fields: List[str]
    backends: List[str] = Field(None, description="Report-level entries: the result keys it applies to.")
    detail: Dict[str, Any] = Field(None, description="Values the page shows with the caveat (core classes, sample range).")


class TimingCaveatsResponse(BaseModel):
    results: List[List[TimingCaveat]] = Field(..., description="Caveats of each result, in request order.")
    report: List[TimingCaveat] = Field(..., description="Report-level caveats.")
    version: str


@router.post("/timing-caveats", response_model=TimingCaveatsResponse, response_model_exclude_none=True,
             responses=responses(413, 422))
@limiter.limit("120/minute")
async def timing_caveats(request: Request, payload: TimingCaveatsRequest):
    """Per-result and report-level timing caveats (``services.timing_caveats``) of the
    results in the body, by the same rules the server applies when it records a report."""
    return derive(payload.raw_results)
