# Pydantic schemas for request/response validation.

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union

# Agreement tolerances. Optional on every run payload; None keeps the documented defaults.
# Statevector tolerances (fidelity/phase = 1e-12) are numerical-precision cut-offs for exact
# statevectors. Measured cut-offs (js=0.01, hellinger=0.1) are HEURISTIC (not literature-
# derived) and shot-count dependent — the shot-noise-aware statistical_test is the rigorous
# verdict. The effective values are recorded per pair in the pairwise_agreement records.
class AgreementThresholds(BaseModel):
    fidelity_tolerance: float = 1e-12
    phase_tolerance: float = 1e-12
    js_threshold: float = 0.01
    hellinger_threshold: float = 0.1

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
    bypass_limits: bool = False
    apply_preprocessing: bool = True
    thresholds: Optional[AgreementThresholds] = None

class MeasuredQasmPayload(BaseModel):
    qasm_string: str
    n_shots: int = 1024
    optimization_level: int = 0
    runner_config: Dict[str, Union[int, List[int]]] = {}
    runner_phases: Dict[str, int] = {}
    timeout_seconds: int = 60
    target_simulators: List[str] = Field(default_factory=list)
    execution_target: str = "kubernetes"
    bypass_limits: bool = False
    apply_preprocessing: bool = True
    # Optional RNG seed for reproducible sampling; None = non-deterministic.
    seed: Optional[int] = None
    thresholds: Optional[AgreementThresholds] = None

class MeasuredBenchmarkPayload(BaseModel):
    n_shots: int = 1024

class GenerateCircuitPayload(BaseModel):
    algorithm: str
    qubits: int

class BenchmarkTask(BaseModel):
    algorithm: str
    qubits: int
    qasm_string: Optional[str] = None
    # Circuit source resolved server-side when qasm_string is absent:
    # None/"preset" = circuit_library; "mqt"/"qasmbench" = bundled benchmark suites.
    source: Optional[str] = None

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
    bypass_limits: bool = False
    apply_preprocessing: bool = True
    # Optional RNG seed for reproducible sampling (measured mode); None = non-deterministic.
    seed: Optional[int] = None
    thresholds: Optional[AgreementThresholds] = None

# --- Reproducible experiment runner (T3.5) -------------------------------------------
# One experiment = a set of circuits x the fleet, run over one or more preprocessing axes,
# frozen into a citable artifact bundle. Opt-in and additive: reuses the batch execution
# core; no change to the compare/batch payloads above.

class ExperimentCircuit(BaseModel):
    """One circuit to include, from any of the wired sources.

    source = "preset"    -> generated via circuit_library (needs algorithm + qubits)
             "qasmbench" -> bundled QASMBench circuit (algorithm = circuit file name)
             "mqt"       -> bundled MQTBench circuit (needs algorithm + qubits)
             "qasm"      -> user-supplied OpenQASM in qasm_string
    """
    source: str = "preset"
    algorithm: Optional[str] = None
    qubits: int = 0
    qasm_string: Optional[str] = None
    name: Optional[str] = None

class ExperimentPayload(BaseModel):
    circuits: List[ExperimentCircuit]
    mode: str = "measured"
    n_shots: int = 1024
    optimization_level: int = 0
    runner_config: Dict[str, Union[int, List[int]]] = {}
    runner_phases: Dict[str, int] = {}
    timeout_seconds: int = 300
    target_simulators: List[str] = Field(default_factory=list)
    execution_target: str = "local"
    bypass_limits: bool = False
    # The preprocessing axis: run once per value (True = pytket preprocessing on).
    preprocessing_modes: List[bool] = Field(default_factory=lambda: [True])
    # One seed shared across every circuit and axis; None => generated-and-recorded.
    seed: Optional[int] = None
    thresholds: Optional[AgreementThresholds] = None
    # Keep full statevectors in the frozen results (default: strip to sha256 + length).
    keep_statevectors: bool = False
    label: Optional[str] = None

class VisualizerResponse(BaseModel):
    url: str

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    target: str
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    runner_statuses: Optional[Dict[str, str]] = None
    # Batch-suite progress: {total, completed, current_index, tasks:[{name,status}]}.
    # Present only while a batch suite runs; None for single runs.
    progress: Optional[Dict[str, Any]] = None

class RunnerPerformanceMetrics(BaseModel):
    simulator: str
    execution_time_sec: float
    compilation_time_sec: Optional[float] = 0.0
    simulation_time_sec: Optional[float] = 0.0
    memory_usage_mb: Optional[float] = 0.0
    process_peak_mb: Optional[float] = 0.0
    error: Optional[str] = None
    preprocessing_applied: Optional[List[str]] = None
    transpiled_qasm: Optional[str] = None
    # Effective optimization level this runner actually executed at (clamped to the
    # runner's supported max, resolved from per-runner override or global). Stamped by
    # the dispatcher so the UI/report reflect ground truth, not just the override map.
    optimization_level: Optional[int] = None
    # Executed SDK versions (importlib.metadata, ground truth) reported by the runner.
    # {distribution_name: version}, e.g. {"qiskit": "2.4.1", "qiskit-aer": "0.17.2"}.
    sdk_versions: Optional[Dict[str, str]] = None

class ComparisonResult(BaseModel):
    input_qasm: str
    divergence_report: Dict[str, Any]
    performance_report: Dict[str, Any]
    resource_report: Dict[str, Any]
    raw_results: List[RunnerPerformanceMetrics]

class PublicationArtifactsSelection(BaseModel):
    """Opt-in selection of publication-ready figures/tables to bundle into the RO-Crate.

    Empty/absent `categories` => no artifacts generated (default, non-breaking).
    `categories` subset of PUBLICATION_CATEGORIES; formats subset of the supported sets.
    """
    categories: List[str] = Field(default_factory=list)
    figure_formats: List[str] = Field(default_factory=lambda: ["svg"])
    table_formats: List[str] = Field(default_factory=lambda: ["csv"])

class ExportPayload(BaseModel):
    format: str = "ro-crate"
    include_statevectors: bool = False
    author_name: Optional[str] = None
    author_affiliation: Optional[str] = None
    publication_artifacts: Optional[PublicationArtifactsSelection] = None

class ExportRequest(ExportPayload):
    results: Dict[str, Any]

class PublicationRenderRequest(BaseModel):
    """Render one publication figure on demand. `results` is the statevector-stripped
    report the browser holds; `scale` sets raster dpi (BASE_DPI x scale)."""
    results: Dict[str, Any]
    artifact_id: str
    format: str
    scale: int = 1
