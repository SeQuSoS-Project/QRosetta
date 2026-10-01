# Pydantic request/response models for the read-only share-link endpoints.

from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from schemas.benchmark import Label
from schemas.timestamps import UtcDatetime

ShareLabel = Annotated[Label, Field(max_length=100)]
from services.share_links import DEFAULT_EXPIRY_DAYS, MAX_EXPIRY_DAYS, MIN_EXPIRY_DAYS


class ShareLinkCreate(BaseModel):
    """Request body for POST /history/runs/{run_id}/share-links."""
    model_config = ConfigDict(extra="forbid")

    expires_in_days: StrictInt = Field(DEFAULT_EXPIRY_DAYS, ge=MIN_EXPIRY_DAYS, le=MAX_EXPIRY_DAYS,
                                 description="Days until the link stops working.")
    label: Optional[ShareLabel] = Field(None, description="Your own name for the link, shown only in your list of links, never to its recipients.")


class ShareLinkResponse(BaseModel):
    """A share link's metadata. The token is never listed; it is returned once, on creation."""
    id: str = Field(..., description="Id of the link, used to revoke it.")
    run_id: str = Field(..., description="The saved run the link reads.")
    created_at: Optional[UtcDatetime] = Field(None, description="When the link was created, UTC ISO 8601 ending in 'Z'.")
    expires_at: UtcDatetime = Field(..., description="When the link stops working, UTC ISO 8601 ending in 'Z'.")
    revoked_at: Optional[UtcDatetime] = Field(None, description="When the owner revoked it; null while not revoked.")
    active: bool = Field(..., description="True while the link is unexpired and not revoked.")
    label: Optional[str] = Field(None, description="The owner's label for the link, if any.")

    model_config = ConfigDict(from_attributes=True)


class ShareLinkCreated(ShareLinkResponse):
    """A new share link, with its token. The token is not stored and cannot be shown again."""
    token: str = Field(..., description="Secret token; the read-only page is /share.html#<token>.")


class SharedCircuitsRequest(BaseModel):
    """Request body for POST /shared/circuits. The token travels in the body so it does not
    appear in request lines or access logs."""
    model_config = ConfigDict(extra="forbid")

    token: str = Field(..., max_length=64, description="The token of a share link.")
