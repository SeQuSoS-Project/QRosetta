# Pydantic request/response models for the /history endpoints.

from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from typing import List, Optional

from schemas.timestamps import UtcDatetime

_CREATED_AT = "When it was saved, UTC ISO 8601 ending in 'Z'."



from schemas.benchmark import VisibleLabel as VisibleName

class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SavedCircuitCreate(_Request):
    """Request body for POST /history/circuits."""
    name: VisibleName = Field(..., description="Display name for the saved circuit.")
    qasm_string: str = Field(..., description="The circuit as OpenQASM 2.0 text.")

class SavedCircuitResponse(BaseModel):
    """A saved circuit, as returned by the /history/circuits endpoints."""
    id: str = Field(..., description="Unique id of the saved circuit.")
    user_id: int = Field(..., description="Id of the account that saved it.")
    name: str = Field(..., description="Display name.")
    qasm_string: str = Field(..., description="The circuit as OpenQASM 2.0 text.")
    created_at: UtcDatetime = Field(..., description=_CREATED_AT)

    model_config = ConfigDict(from_attributes=True)

class RunHistoryResponse(BaseModel):
    """A saved run's metadata, as returned by the /history/runs endpoints (the full report
    itself is fetched separately via GET /history/runs/{run_id})."""
    id: str = Field(..., description="Unique id of the saved run.")
    user_id: int = Field(..., description="Id of the account that saved it.")
    circuit_id: Optional[str] = Field(None, description="Id of the saved circuit this run used, if any.")
    run_name: str = Field(..., description="Display name for the run.")
    created_at: UtcDatetime = Field(..., description=_CREATED_AT)
    job_id: Optional[str] = Field(None, description="The server job the run was saved from with POST /history/runs/from_job/{job_id}; null for a report uploaded with POST /history/runs (its stored report keeps the id the client gave as source_job_id) and for runs saved before job ids were recorded.")

    model_config = ConfigDict(from_attributes=True)

class RunHistoryFromJob(_Request):
    """Request body for POST /history/runs/from_job/{job_id}."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    run_name: Optional[VisibleName] = Field(None, validation_alias=AliasChoices("run_name", "name"), description="Display name for the saved run (also accepted as 'name'). Defaults to the mode and the first 8 characters of the job id.")

class RunHistoryUpdate(_Request):
    """Request body for PATCH /history/runs/{run_id}."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    run_name: VisibleName = Field(..., validation_alias=AliasChoices("run_name", "name"), description="New display name for the run (also accepted as 'name').")

class SavedCircuitUpdate(_Request):
    """Request body for PATCH /history/circuits/{circuit_id}."""
    name: VisibleName = Field(..., description="New display name for the saved circuit.")

class RunHistoryBatchDelete(_Request):
    """Request body for DELETE /history/runs."""
    run_ids: List[str] = Field(..., description="Ids of the saved runs to delete.")

class RunHistoryBatchDeleteResponse(BaseModel):
    """Response body for DELETE /history/runs."""
    detail: str = Field(..., description="Summary, e.g. 'Deleted 2 runs'.")
    deleted: List[str] = Field(..., description="Ids that were deleted.")
    not_found: List[str] = Field(..., description="Requested ids that do not exist or belong to another account; nothing was done for them.")
