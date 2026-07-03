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
    # Optional RNG seed for reproducible sampling. None = non-deterministic (the
    # prior behaviour). Consumed by runners that sample from a computed statevector;
    # native-sampler backends ignore it until per-SDK seeding lands (see T2.1).
    seed: Optional[int] = None