"""Pydantic payload models for the runner HTTP endpoints."""

from pydantic import BaseModel, Field
from typing import Dict, Optional

def _timing_repeats():
    return Field(1, ge=1, le=10, description=(
        "Timed runs after the one warm-up; the reported times are their medians. The hard "
        "timeout covers the warm-up and every timed run."))


class CircuitPayload(BaseModel):
    """``/run`` payload. ``hard_timeout_seconds`` is the wall-clock budget enforced by
    ``helpers.run_isolated``; None uses the runner default. ``max_queue_wait_seconds``
    bounds the wait for an execution slot (``helpers.ExecutionSlots``); None waits
    indefinitely. ``timing_repeats`` is the number of timed runs
    (``helpers.run_with_uniform_measurement``)."""
    circuit_data: str
    optimization_level: int = 0
    runner_config: Dict[str, int] = {}
    apply_preprocessing: bool = True
    hard_timeout_seconds: Optional[int] = None
    max_queue_wait_seconds: Optional[float] = None
    timing_repeats: int = _timing_repeats()


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
    max_queue_wait_seconds: Optional[float] = None
    timing_repeats: int = _timing_repeats()


class CompilePayload(BaseModel):
    """``/compile`` payload of a compile-only service. ``optimization_level`` picks one of
    the service's documented pipelines; the hard timeout and queue wait are as for
    ``CircuitPayload``."""
    circuit_data: str
    optimization_level: int = 0
    hard_timeout_seconds: Optional[int] = None
    max_queue_wait_seconds: Optional[float] = None
