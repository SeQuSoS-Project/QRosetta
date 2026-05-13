# Shared common utilities for the Rosetta ecosystem.

from pydantic import BaseModel
from typing import Dict

class CircuitPayload(BaseModel):
    circuit_data: str
    optimization_level: int = 0
    runner_config: Dict[str, int] = {}

class MeasuredCircuitPayload(BaseModel):
    circuit_data: str
    n_shots: int
    optimization_level: int = 0
    runner_config: Dict[str, int] = {}