"""Pydantic payload models for the runner HTTP endpoints."""

from pydantic import BaseModel
from typing import Dict, Optional


class CircuitPayload(BaseModel):
    """``/run`` payload. ``hard_timeout_seconds`` is the wall-clock budget enforced by
    ``helpers.run_isolated``; None uses the runner default."""
    circuit_data: str
    optimization_level: int = 0
    runner_config: Dict[str, int] = {}
    apply_preprocessing: bool = True
    hard_timeout_seconds: Optional[int] = None


class MeasuredCircuitPayload(BaseModel):
    """``/run_measured`` payload. ``seed`` drives the runner's sampler; None is
    non-deterministic."""
    circuit_data: str
    n_shots: int
    optimization_level: int = 0
    runner_config: Dict[str, int] = {}
    apply_preprocessing: bool = True
    seed: Optional[int] = None
    hard_timeout_seconds: Optional[int] = None
