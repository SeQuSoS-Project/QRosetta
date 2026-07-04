# Shared common utilities for the Rosetta ecosystem.

from pydantic import BaseModel
from typing import Dict, Optional

class CircuitPayload(BaseModel):
    circuit_data: str
    optimization_level: int = 0
    runner_config: Dict[str, int] = {}
    apply_preprocessing: bool = True

class MeasuredCircuitPayload(BaseModel):
    circuit_data: str
    n_shots: int
    optimization_level: int = 0
    runner_config: Dict[str, int] = {}
    apply_preprocessing: bool = True
    # Optional RNG seed for reproducible sampling. None = non-deterministic.
    # Active runners consume this through their native SDK RNG, numpy's global RNG,
    # or the shared statevector sampler depending on the backend.
    seed: Optional[int] = None
