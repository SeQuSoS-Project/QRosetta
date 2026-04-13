from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional
from datetime import datetime

class QasmPayload(BaseModel):
    qasm_string: str
    optimization_level: int = 0
    runner_config: Dict[str, int] = {}
    timeout_seconds: int = 60
    target_simulators: List[str] = Field(default_factory=list)
    execution_target: str = "rahti"

class MeasuredQasmPayload(BaseModel):
    qasm_string: str
    n_shots: int = 1024
    optimization_level: int = 0
    runner_config: Dict[str, int] = {}
    timeout_seconds: int = 60
    target_simulators: List[str] = Field(default_factory=list)
    execution_target: str = "rahti"

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
    mode: str  # 'statevector' or 'measured'
    optimization_level: int = 0
    runner_config: Dict[str, int] = {}
    timeout_seconds: int = 60
    target_simulators: List[str] = Field(default_factory=list)
    execution_target: str = "rahti"

# --- NEW OUTPUT MODELS ---

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

# --- AUTH MODELS ---

class UserCreate(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    auth_provider: str
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

# --- PERSISTENCE MODELS ---

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
