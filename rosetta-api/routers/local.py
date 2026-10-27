"""POST /local/host-load: the qrosetta command's notices of host load it causes (start, stop,
remove, build, pull, image probes). Hidden, and 404 without the local lifecycle token."""

from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing_extensions import Annotated

from services import host_load
from services.lifecycle_token import matches_lifecycle_token

router = APIRouter()

ServiceId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")]


class HostLoadNotice(BaseModel):
    """begin (with kind and services), heartbeat or end (with notice_id)."""
    model_config = ConfigDict(extra="forbid")
    action: Literal["begin", "heartbeat", "end"]
    kind: Optional[Literal[host_load.KINDS]] = None
    services: Optional[List[ServiceId]] = Field(None, max_length=64)
    notice_id: Optional[Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{32}$")]] = None


def _lifecycle_only(request: Request) -> None:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not matches_lifecycle_token(token.strip()):
        raise HTTPException(status_code=404, detail="Not Found")


@router.post("/local/host-load", include_in_schema=False, dependencies=[Depends(_lifecycle_only)])
async def host_load_notice(payload: HostLoadNotice):
    """Open, keep alive or end a host-load notice (``services.host_load``). 400 for begin
    without kind or heartbeat/end without notice_id; 404 for a notice that is not open (it
    ended or expired) and for a request without the lifecycle token; 409 when too many are
    open."""
    if payload.action == "begin":
        if payload.kind is None:
            raise HTTPException(status_code=400, detail="begin needs kind.")
        try:
            return await host_load.begin(payload.kind, payload.services)
        except host_load.TooManyNotices:
            raise HTTPException(status_code=409, detail=(
                f"{host_load.MAX_OPEN} host-load notices are open; end one first."))
    if payload.notice_id is None:
        raise HTTPException(status_code=400, detail=f"{payload.action} needs notice_id.")
    try:
        if payload.action == "heartbeat":
            return await host_load.heartbeat(payload.notice_id)
        return await host_load.end(payload.notice_id)
    except host_load.NoticeNotFound:
        raise HTTPException(status_code=404, detail=(
            "No open host-load notice has this id: it ended, or expired "
            f"{host_load.NOTICE_TTL_SEC:g} s after its last heartbeat."))
