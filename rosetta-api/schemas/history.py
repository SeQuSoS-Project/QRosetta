from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime


class SavedCircuitCreate(BaseModel):
    name: str
    qasm_string: str


class SavedCircuitResponse(BaseModel):
    id: str
    user_id: int
    name: str
    qasm_string: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunHistoryCreate(BaseModel):
    s3_object_key: str
    circuit_id: Optional[str] = None


class RunHistoryResponse(BaseModel):
    id: str
    user_id: int
    circuit_id: Optional[str]
    s3_object_key: str
    run_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunHistoryUpdate(BaseModel):
    run_name: str


class RunHistoryBatchDelete(BaseModel):
    run_ids: List[str]
