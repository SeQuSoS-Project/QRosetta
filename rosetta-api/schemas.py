from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class QasmPayload(BaseModel):
    qasm_string: str
    optimization_level: int = 0

class MeasuredQasmPayload(BaseModel):
    qasm_string: str
    n_shots: int = 1024
    optimization_level: int = 0

class MeasuredBenchmarkPayload(BaseModel):
    n_shots: int = 1024

class GenerateCircuitPayload(BaseModel):
    algorithm: str
    qubits: int

class BenchmarkTask(BaseModel):
    algorithm: str
    qubits: int

class BatchPayload(BaseModel):
    tasks: List[BenchmarkTask]
    n_shots: int = 1024
    mode: str  # 'statevector' or 'measured'
    optimization_level: int = 0

# --- NEW OUTPUT MODELS ---

class RunnerPerformanceMetrics(BaseModel):
    simulator: str
    execution_time_sec: float
    # New Split Metrics (Optional for backward compatibility)
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
    raw_results: List[RunnerPerformanceMetrics] # This enforces the new structure
