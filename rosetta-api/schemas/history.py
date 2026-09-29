# Pydantic request/response models for the /history endpoints.

from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime

class SavedCircuitCreate(BaseModel):
    """Request body for POST /history/circuits."""
    name: str = Field(..., description="Display name for the saved circuit.")
    qasm_string: str = Field(..., description="The circuit as OpenQASM 2.0 text.")

class SavedCircuitResponse(BaseModel):
    """A saved circuit, as returned by the /history/circuits endpoints."""
    id: str = Field(..., description="Unique id of the saved circuit.")
    user_id: int = Field(..., description="Id of the account that saved it.")
    name: str = Field(..., description="Display name.")
    qasm_string: str = Field(..., description="The circuit as OpenQASM 2.0 text.")
    created_at: datetime = Field(..., description="When it was saved.")

    model_config = ConfigDict(from_attributes=True)

class RunHistoryResponse(BaseModel):
    """A saved run's metadata, as returned by the /history/runs endpoints (the full report
    itself is fetched separately via GET /history/runs/{run_id})."""
    id: str = Field(..., description="Unique id of the saved run.")
    user_id: int = Field(..., description="Id of the account that saved it.")
    circuit_id: Optional[str] = Field(None, description="Id of the saved circuit this run used, if any.")
    s3_object_key: str = Field(..., description="Storage key of the saved report.")
    run_name: str = Field(..., description="Display name for the run.")
    created_at: datetime = Field(..., description="When it was saved.")

    model_config = ConfigDict(from_attributes=True)

class RunHistoryUpdate(BaseModel):
    """Request body for PATCH /history/runs/{run_id}."""
    run_name: str = Field(..., description="New display name for the run.")

class RunHistoryBatchDelete(BaseModel):
    """Request body for DELETE /history/runs."""
    run_ids: List[str] = Field(..., description="Ids of the saved runs to delete.")
