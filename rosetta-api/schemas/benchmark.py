# Pydantic schemas for request/response validation.

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union

# runner_config values: int = single run at that opt level (default mode);
# list = self-comparison, one run per element (repeats allowed → same level N times).
# runner_phases: maps runner → phase number. Runners sharing a phase run concurrently;
# phases execute in ascending order. Absent/empty = all concurrent (default behavior).
class QasmPayload(BaseModel):
    qasm_string: str
    optimization_level: int = 0
    runner_config: Dict[str, Union[int, List[int]]] = {}
    runner_phases: Dict[str, int] = {}
    timeout_seconds: int = 60
    target_simulators: List[str] = Field(default_factory=list)
    execution_target: str = "kubernetes"

class MeasuredQasmPayload(BaseModel):
    qasm_string: str
    n_shots: int = 1024
    optimization_level: int = 0
    runner_config: Dict[str, Union[int, List[int]]] = {}
    runner_phases: Dict[str, int] = {}
    timeout_seconds: int = 60
    target_simulators: List[str] = Field(default_factory=list)
    execution_target: str = "kubernetes"

class MeasuredBenchmarkPayload(BaseModel):
    n_shots: int = 1024

class GenerateCircuitPayload(BaseModel):
    algorithm: str
    qubits: int

class BenchmarkTask(BaseModel):
    algorithm: str
    qubits: int
    qasm_string: Optional[str] = None

class BatchPayload(BaseModel):
    tasks: List[BenchmarkTask]
    n_shots: int = 1024
    mode: str
    optimization_level: int = 0
    runner_config: Dict[str, Union[int, List[int]]] = {}
    runner_phases: Dict[str, int] = {}
    timeout_seconds: int = 60
    target_simulators: List[str] = Field(default_factory=list)
    execution_target: str = "kubernetes"

class VisualizerResponse(BaseModel):
    url: str

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    target: str
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    runner_statuses: Optional[Dict[str, str]] = None

class RunnerPerformanceMetrics(BaseModel):
    simulator: str
    execution_time_sec: float
    compilation_time_sec: Optional[float] = 0.0
    simulation_time_sec: Optional[float] = 0.0
    memory_usage_mb: Optional[float] = 0.0
    process_peak_mb: Optional[float] = 0.0
    error: Optional[str] = None

class ComparisonResult(BaseModel):
    input_qasm: str
    divergence_report: Dict[str, Any]
    performance_report: Dict[str, Any]
    resource_report: Dict[str, Any]
    raw_results: List[RunnerPerformanceMetrics]

class ExportPayload(BaseModel):
    format: str = "ro-crate"
    include_statevectors: bool = False
    author_name: Optional[str] = None
    author_affiliation: Optional[str] = None

class ExportRequest(ExportPayload):
    results: Dict[str, Any]
