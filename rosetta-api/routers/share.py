"""Read-only share links: owners create, list and revoke links to their saved runs; anyone
holding a token reads that run's circuit texts."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

import db.models as models
import services.share_links as share_links
from db.database import get_db
from routers.errors import responses
from schemas.share import ShareLinkCreate, ShareLinkCreated, ShareLinkResponse, SharedCircuitsRequest
from services.security import get_current_user, limiter

router = APIRouter(tags=["share"])

_NOT_FOUND = "This link does not exist, has expired or was revoked."
_PRIVATE_HEADERS = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
                    "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY"}


def _response(link, **extra) -> dict:
    return {"id": link.id, "run_id": link.run_id, "created_at": link.created_at,
            "expires_at": link.expires_at, "revoked_at": link.revoked_at,
            "active": share_links.is_active(link), "label": link.label, **extra}


@router.post("/history/runs/{run_id}/share-links", response_model=ShareLinkCreated,
             status_code=status.HTTP_201_CREATED, responses=responses(404, 409, 422))
@limiter.limit("20/minute")
def create_share_link(request: Request, run_id: str, response: Response,
                      body: ShareLinkCreate | None = None, db: Session = Depends(get_db),
                      current_user: models.User = Depends(get_current_user)):
    """Create a read-only link to the circuit texts of one of your saved runs. The token is
    in this response only. 404 if the run is not yours; 409 when the run already has the
    maximum number of active links."""
    body = body or ShareLinkCreate()
    try:
        link, token = share_links.create_link(db, current_user.id, run_id, body.expires_in_days, body.label)
    except share_links.RunNotFound:
        raise HTTPException(status_code=404, detail="Run history not found")
    except share_links.TooManyLinks:
        raise HTTPException(status_code=409, detail=(
            f"This run already has {share_links.MAX_ACTIVE_LINKS_PER_RUN} active links; "
            "revoke one first."))
    response.headers.update(_PRIVATE_HEADERS)
    return _response(link, token=token)


@router.get("/history/runs/{run_id}/share-links", response_model=list[ShareLinkResponse],
            responses=responses(404))
def list_share_links(run_id: str, db: Session = Depends(get_db),
                     current_user: models.User = Depends(get_current_user)):
    """The links to one of your saved runs, without their tokens. 404 if the run is not yours."""
    try:
        return [_response(link) for link in share_links.list_links(db, current_user.id, run_id)]
    except share_links.RunNotFound:
        raise HTTPException(status_code=404, detail="Run history not found")


@router.delete("/history/share-links/{link_id}", response_model=ShareLinkResponse,
               responses=responses(404))
def revoke_share_link(link_id: str, db: Session = Depends(get_db),
                      current_user: models.User = Depends(get_current_user)):
    """Revoke one of your links; it stops working at once. 404 if the link is not yours."""
    try:
        return _response(share_links.revoke_link(db, current_user.id, link_id))
    except share_links.ShareNotFound:
        raise HTTPException(status_code=404, detail="Share link not found")


@router.post("/shared/circuits", responses=responses(404, 422))
@limiter.limit("30/minute")
def read_shared_circuits(request: Request, body: SharedCircuitsRequest, response: Response,
                         db: Session = Depends(get_db)):
    """The circuit texts a share link reads: the submitted circuit, each dispatched circuit,
    and each backend's executed circuit with its gate metrics, transforms and SDK versions,
    plus the run's name, save time and the link's expiry. No authentication. 404 for a
    token that is unknown, expired or revoked, whose owner is deactivated, or whose run was
    deleted."""
    try:
        texts = share_links.resolve(db, body.token)
    except share_links.ShareNotFound:
        raise HTTPException(status_code=404, detail=_NOT_FOUND, headers=_PRIVATE_HEADERS)
    response.headers.update(_PRIVATE_HEADERS)
    return texts
