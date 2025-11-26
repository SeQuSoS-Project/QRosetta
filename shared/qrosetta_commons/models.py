# ./shared/models.py
from pydantic import BaseModel

class CircuitPayload(BaseModel):
    circuit_data: str 

class MeasuredCircuitPayload(BaseModel):
    circuit_data: str
    n_shots: int