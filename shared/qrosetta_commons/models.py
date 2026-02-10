# ./shared/models.py
from pydantic import BaseModel

class CircuitPayload(BaseModel):
    circuit_data: str 
    optimization_level: int = 0 

class MeasuredCircuitPayload(BaseModel):
    circuit_data: str
    n_shots: int
    optimization_level: int = 0