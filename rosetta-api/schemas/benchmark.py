"""Pydantic request and response schemas for the benchmark endpoints."""

from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated, List, Dict, Any, Literal, Optional, Union

from config import settings

OptimizationLevel = Annotated[int, Field(ge=0, le=3)]
RunnerConfig = Dict[str, Union[OptimizationLevel, List[OptimizationLevel]]]
ExecutionTarget = Literal["local", "kubernetes"]

_OPT_LEVEL_DESCRIPTION = ("Requested transpiler/optimization level, 0-3; each backend clamps it "
                          "to its own supported max.")
_TIMEOUT_DESCRIPTION = (f"Requested wall-clock budget per runner in seconds, at least "
                        f"{settings.MIN_TIMEOUT_SEC}; values above the server's RUNNER_TIMEOUT_SEC "
                        f"are clamped to it.")
_SHOTS_DESCRIPTION = (f"Number of shots each runner samples, {settings.MIN_SHOTS} to "
                      f"{settings.MAX_SHOTS}.")
_TARGET_DESCRIPTION = ("'local' or 'kubernetes'. Defaults to the server's EXECUTION_MODE. Runs "
                       "are dispatched according to the server's EXECUTION_MODE; the job's "
                       "'target' records the mode actually used and 'requested_target' this "
                       "value.")
_BYPASS_DESCRIPTION = ("Skip the MAX_QASM_SIZE and MAX_QASM_GATES checks (local EXECUTION_MODE "
                       "only). The qubit limits still apply.")


def _default_execution_target() -> str:
    return settings.EXECUTION_MODE


class AgreementThresholds(BaseModel):
    """Cut-offs the comparator uses to label a backend pair as agreeing or not.

    Optional on every run payload; an omitted field keeps its default. The statevector
    tolerances are numerical-precision cut-offs. The measured cut-offs (JS divergence in
    nats, Hellinger distance) are descriptive and shot-count dependent; the report's
    statistical_test block carries the shot-noise-aware verdict. The values used are
    recorded in every pairwise_agreement record. NaN and infinity are rejected.
    """
    model_config = ConfigDict(allow_inf_nan=False)

    fidelity_tolerance: float = Field(1e-5, ge=0, description="A statevector pair agrees when fidelity >= 1 minus this value.")
    phase_tolerance: float = Field(1e-12, ge=0, description="A relative phase within this many radians of 0 is reported as 0.")
    norm_tolerance: float = Field(1e-4, ge=0, description="A statevector whose norm differs from 1 by more than this is flagged unnormalized_input; an agreeing pair is then labelled 'agree_after_normalization'.")
    js_threshold: float = Field(0.01, ge=0, description="Jensen-Shannon divergence (nats) between two backends' measured distributions above this is 'distance_exceeds_threshold'.")
    hellinger_threshold: float = Field(0.1, ge=0, description="Hellinger distance between two backends' measured distributions above this is 'distance_exceeds_threshold'.")

class QasmPayload(BaseModel):
    """Request body for POST /compare — an exact statevector comparison of one OpenQASM 2.0
    circuit across the simulator fleet."""
    qasm_string: str = Field(..., description="The circuit to run, as OpenQASM 2.0 text.")
    optimization_level: OptimizationLevel = Field(0, description=_OPT_LEVEL_DESCRIPTION)
    runner_config: RunnerConfig = Field({}, description="Per-runner optimization-level override. An int runs that runner once at that level; a list runs it once per element (repeats allowed, e.g. the same level twice).")
    runner_phases: Dict[str, int] = Field({}, description="Maps runner id to a phase number. Runners sharing a phase run concurrently; phases execute in ascending order. Absent/empty means every runner executes concurrently.")
    timeout_seconds: int = Field(60, ge=settings.MIN_TIMEOUT_SEC, description=_TIMEOUT_DESCRIPTION)
    target_simulators: List[str] = Field(default_factory=list, description="Which runner ids to dispatch to. Empty means every enabled runner.")
    execution_target: ExecutionTarget = Field(default_factory=_default_execution_target, description=_TARGET_DESCRIPTION)
    bypass_limits: bool = Field(False, description=_BYPASS_DESCRIPTION)
    apply_preprocessing: bool = Field(True, description="Whether each runner applies its own preprocessing pass (e.g. barrier stripping, gate rebasing) before simulating. Every applied pass is recorded in the result's preprocessing_applied list either way.")
    thresholds: Optional[AgreementThresholds] = Field(None, description="Override the default agreement thresholds for this run. Omit to use the defaults.")

class MeasuredQasmPayload(BaseModel):
    """Request body for POST /compare_measured — a shot-based measurement comparison of one
    OpenQASM 2.0 circuit across the simulator fleet."""
    qasm_string: str = Field(..., description="The circuit to run, as OpenQASM 2.0 text (must contain measurement instructions).")
    n_shots: int = Field(1024, ge=settings.MIN_SHOTS, le=settings.MAX_SHOTS, description=_SHOTS_DESCRIPTION)
    optimization_level: OptimizationLevel = Field(0, description=_OPT_LEVEL_DESCRIPTION)
    runner_config: RunnerConfig = Field({}, description="Per-runner optimization-level override. An int runs that runner once at that level; a list runs it once per element.")
    runner_phases: Dict[str, int] = Field({}, description="Maps runner id to a phase number. Runners sharing a phase run concurrently; phases execute in ascending order.")
    timeout_seconds: int = Field(60, ge=settings.MIN_TIMEOUT_SEC, description=_TIMEOUT_DESCRIPTION)
    target_simulators: List[str] = Field(default_factory=list, description="Which runner ids to dispatch to. Empty means every enabled runner.")
    execution_target: ExecutionTarget = Field(default_factory=_default_execution_target, description=_TARGET_DESCRIPTION)
    bypass_limits: bool = Field(False, description=_BYPASS_DESCRIPTION)
    apply_preprocessing: bool = Field(True, description="Whether each runner applies its own preprocessing pass before simulating.")
    seed: Optional[int] = Field(None, description="RNG seed shared by every runner's sampling, for a reproducible run. Omit for a fresh, non-deterministic seed that is still generated and recorded in the report.")
    thresholds: Optional[AgreementThresholds] = Field(None, description="Override the default agreement thresholds for this run.")

class GenerateCircuitPayload(BaseModel):
    """Request body for POST /generate_circuit — build one preset circuit's OpenQASM text
    server-side, without running it."""
    algorithm: str = Field(..., description="Preset circuit family, e.g. 'ghz', 'bell', 'qft', 'bv', 'grover'.")
    qubits: int = Field(..., ge=1, description="Number of qubits to generate the circuit for.")
    seed: Optional[int] = Field(None, description="Seed for presets with random content (e.g. 'random'). Omit to derive it from the qubit count, so the same request always yields the same circuit.")

class BenchmarkTask(BaseModel):
    """One circuit within a batch run (POST /run_batch_suite)."""
    algorithm: str = Field(..., description="Circuit identifier: a preset family name, or the file name for a bundled benchmark circuit.")
    qubits: int = Field(..., description="Number of qubits (ignored for bundled benchmark circuits, which are fixed-size).")
    qasm_string: Optional[str] = Field(None, description="User-supplied OpenQASM 2.0 text. When present, this is run as-is and algorithm/qubits/source are ignored.")
    source: Optional[str] = Field(None, description="Where to resolve the circuit from when qasm_string is absent: None or 'preset' generates it from the built-in circuit library; 'qasmbench' or 'mqt' loads it from the corresponding bundled benchmark suite.")

class BatchPayload(BaseModel):
    """Request body for POST /run_batch_suite — run a list of circuits (BenchmarkTask entries)
    across the simulator fleet in a single job."""
    tasks: List[BenchmarkTask] = Field(..., description="The circuits to run, in order.")
    n_shots: int = Field(1024, ge=settings.MIN_SHOTS, le=settings.MAX_SHOTS, description=_SHOTS_DESCRIPTION + " Used only when mode is 'measured'.")
    mode: str = Field(..., description="'statevector' or 'measured'.")
    optimization_level: OptimizationLevel = Field(0, description=_OPT_LEVEL_DESCRIPTION)
    runner_config: RunnerConfig = Field({}, description="Per-runner optimization-level override, same semantics as in QasmPayload.")
    runner_phases: Dict[str, int] = Field({}, description="Maps runner id to a phase number for staged concurrent execution, same semantics as in QasmPayload.")
    timeout_seconds: int = Field(60, ge=settings.MIN_TIMEOUT_SEC, description=_TIMEOUT_DESCRIPTION)
    target_simulators: List[str] = Field(default_factory=list, description="Which runner ids to dispatch to. Empty means every enabled runner.")
    execution_target: ExecutionTarget = Field(default_factory=_default_execution_target, description=_TARGET_DESCRIPTION)
    bypass_limits: bool = Field(False, description=_BYPASS_DESCRIPTION)
    apply_preprocessing: bool = Field(True, description="Whether each runner applies its own preprocessing pass before simulating.")
    seed: Optional[int] = Field(None, description="RNG seed shared by every task and runner's sampling (measured mode only), for a reproducible run. Omit for a fresh, non-deterministic seed that is still generated and recorded.")
    thresholds: Optional[AgreementThresholds] = Field(None, description="Override the default agreement thresholds for this run.")

class ExperimentCircuit(BaseModel):
    """One circuit to include in an experiment (POST /experiments), from any of the wired
    sources.

    source = "preset"    -> generated via circuit_library (needs algorithm + qubits)
             "qasmbench" -> bundled QASMBench circuit (algorithm = circuit file name)
             "mqt"       -> bundled MQTBench circuit (needs algorithm + qubits)
             "qasm"      -> user-supplied OpenQASM in qasm_string
    """
    source: str = Field("preset", description="Where to resolve this circuit from: 'preset', 'qasmbench', 'mqt', or 'qasm'.")
    algorithm: Optional[str] = Field(None, description="Circuit identifier for the 'preset', 'qasmbench', or 'mqt' sources.")
    qubits: int = Field(0, description="Number of qubits, for the 'preset' and 'mqt' sources.")
    qasm_string: Optional[str] = Field(None, description="User-supplied OpenQASM 2.0 text, for source='qasm'.")
    name: Optional[str] = Field(None, description="Display label for this circuit in the frozen bundle; defaults to a name derived from algorithm/qubits.")

class ExperimentPayload(BaseModel):
    """Request body for POST /experiments — run a fixed set of circuits across the fleet
    over one or more preprocessing axes, and freeze the inputs, environment, and outputs into
    a citable artifact bundle (downloaded via GET /experiments/{job_id}/bundle)."""
    circuits: List[ExperimentCircuit] = Field(..., description="The circuits to include.")
    mode: str = Field("measured", description="'statevector' or 'measured'.")
    n_shots: int = Field(1024, ge=settings.MIN_SHOTS, le=settings.MAX_SHOTS, description=_SHOTS_DESCRIPTION + " Used only when mode is 'measured'.")
    optimization_level: OptimizationLevel = Field(0, description=_OPT_LEVEL_DESCRIPTION)
    runner_config: RunnerConfig = Field({}, description="Per-runner optimization-level override, same semantics as in QasmPayload.")
    runner_phases: Dict[str, int] = Field({}, description="Maps runner id to a phase number for staged concurrent execution.")
    timeout_seconds: int = Field(300, ge=settings.MIN_TIMEOUT_SEC, description=_TIMEOUT_DESCRIPTION)
    target_simulators: List[str] = Field(default_factory=list, description="Which runner ids to include. Empty means every enabled runner.")
    execution_target: ExecutionTarget = Field(default_factory=_default_execution_target, description=_TARGET_DESCRIPTION)
    bypass_limits: bool = Field(False, description=_BYPASS_DESCRIPTION + " For experiments it also lifts the circuit-axis cell cap.")
    preprocessing_modes: List[bool] = Field(default_factory=lambda: [True], description="The preprocessing axis: the whole circuit set runs once per value in this list (True = each runner's own preprocessing pass applied, False = raw circuit). Multiple values run multiple full passes.")
    seed: Optional[int] = Field(None, description="RNG seed shared by every circuit, axis, and runner's sampling. Omit for a fresh seed that is still generated and recorded in the manifest, so every experiment is replayable.")
    thresholds: Optional[AgreementThresholds] = Field(None, description="Override the default agreement thresholds for this experiment.")
    keep_statevectors: bool = Field(False, description="Keep full statevectors in the frozen results bundle. Default strips them to a sha256 hash + length to keep the bundle small; the live report is unaffected either way.")
    label: Optional[str] = Field(None, description="Human-readable name for this experiment, recorded in the manifest.")

class VisualizerResponse(BaseModel):
    """Response body carrying a URL to an interactive circuit visualization."""
    url: str = Field(..., description="URL of the rendered visualization.")

class JobStatusResponse(BaseModel):
    """Response body for GET /jobs/{job_id}, and the initial response to every job-creating
    POST endpoint (/compare, /compare_measured, /run_batch_suite, /experiments)."""
    job_id: str = Field(..., description="Identifier to poll via GET /jobs/{job_id}.")
    status: str = Field(..., description="'pending', 'processing', 'completed', or 'failed'. 'failed' means the circuit could not be dispatched at all (e.g. it does not parse), or every task of a batch failed.")
    target: str = Field(..., description="The execution mode this job was dispatched with ('local' or 'kubernetes').")
    requested_target: Optional[str] = Field(None, description="The execution_target the request asked for, when it differs from target.")
    results: Optional[Dict[str, Any]] = Field(None, description="The report, present once status is 'completed' (and for a failed single-circuit job).")
    error: Optional[str] = Field(None, description="Failure message, present if status is 'failed'. A failed single-circuit job still carries its report in results.")
    runner_statuses: Optional[Dict[str, str]] = Field(None, description="Per-runner status while the job is in flight.")
    progress: Optional[Dict[str, Any]] = Field(None, description="Batch/experiment progress: {total, completed, current_index, tasks:[{name,status}]}. Present only while a multi-circuit run is in progress; absent for single-circuit runs.")

class RunnerPerformanceMetrics(BaseModel):
    """One backend's raw result for a single circuit run — the entries in a report's
    raw_results list.

    Declared as the documented shape of a report rather than as a request/response model:
    runs complete asynchronously, so endpoints return a job envelope and the report itself
    travels inside JobStatusResponse.results.
    """
    simulator: str = Field(..., description="Runner id, e.g. 'qiskit', 'torchquantum'.")
    execution_time_sec: Optional[float] = Field(None, description="Total wall-clock time (compilation + simulation), after the uniform warm-up run. None when the run failed.")
    compilation_time_sec: Optional[float] = Field(None, description="Time to parse the circuit and prepare it for simulation. None when the run failed.")
    simulation_time_sec: Optional[float] = Field(None, description="Time to execute the circuit and retrieve results. None when the run failed.")
    memory_usage_mb: Optional[float] = Field(None, description="RAM added during the simulation window only. None when the run failed. Kept for continuity; process_peak_rss_mb in the resource report is the ranking basis.")
    process_peak_mb: Optional[float] = Field(None, description="Peak RAM during the simulation window only. None when the run failed. Kept for continuity; process_peak_rss_mb is the ranking basis.")
    queue_wait_sec: Optional[float] = Field(None, description="Seconds the request waited for the runner's execution slot before its process started; 0 on the Kubernetes path; None when the API never got a runner response.")
    timed_out: Optional[bool] = Field(None, description="True when the run was stopped by a time budget (in the runner's queue or while running).")
    never_started: Optional[bool] = Field(None, description="True when the run's queue budget expired before it started.")
    error: Optional[str] = Field(None, description="Failure message if this runner did not complete.")
    preprocessing_applied: Optional[List[str]] = Field(None, description="Each preprocessing pass this runner actually applied, described in plain language.")
    transpiled_qasm: Optional[str] = Field(None, description="The circuit as this runner's own compiler actually saw it, after transpilation.")
    optimization_level: Optional[int] = Field(None, description="Optimization level this runner actually executed at (clamped to its own supported max).")
    sdk_versions: Optional[Dict[str, str]] = Field(None, description="Executed SDK package versions, read at runtime from the runner's own environment, e.g. {'qiskit': '2.4.1', 'qiskit-aer': '0.17.2'}.")

class ComparisonResult(BaseModel):
    """The full report for one circuit run across the fleet."""
    input_qasm: str = Field(..., description="The circuit as submitted, before any runner-specific preprocessing.")
    divergence_report: Dict[str, Any] = Field(..., description="Cross-backend agreement: fidelity/distance matrices, the explained-cause pairwise_agreement records, and (measured mode) the statistical_test_summary.")
    performance_report: Dict[str, Any] = Field(..., description="Per-backend timing: 'ranking' lists successful backends fastest first; 'unranked' lists the rest with a reason.")
    resource_report: Dict[str, Any] = Field(..., description="Per-backend memory usage: 'ranking' lists successful backends by process peak RSS (lowest first); 'unranked' lists the rest with a reason.")
    raw_results: List[RunnerPerformanceMetrics] = Field(..., description="Every backend's individual result.")

class PublicationArtifactsSelection(BaseModel):
    """Opt-in selection of publication-ready figures/tables to bundle into an RO-Crate export.

    Empty/absent categories means no artifacts are generated (the default, non-breaking).
    """
    categories: List[str] = Field(default_factory=list, description="Which artifact categories to generate, e.g. 'agreement', 'performance', 'resources'. Empty generates none.")
    figure_formats: List[str] = Field(default_factory=lambda: ["svg"], description="Raster/vector formats to render each figure in, e.g. 'svg', 'png', 'pdf'.")
    table_formats: List[str] = Field(default_factory=lambda: ["csv"], description="Formats to render each table in, e.g. 'csv', 'html', 'latex', 'xlsx'.")

class ExportPayload(BaseModel):
    """Options for exporting a completed report as a citable artifact."""
    format: str = Field("ro-crate", description="Export format. Currently only 'ro-crate' (an RO-Crate 1.1 archive conforming to the Process Run Crate profile) is supported.")
    include_statevectors: bool = Field(False, description="Include full statevectors in the export. Default strips them to keep the archive small.")
    author_name: Optional[str] = Field(None, description="Author name recorded in the crate's metadata.")
    author_affiliation: Optional[str] = Field(None, description="Author affiliation recorded in the crate's metadata.")
    publication_artifacts: Optional[PublicationArtifactsSelection] = Field(None, description="Optionally bundle publication-ready figures/tables into the crate alongside the raw results.")

class ExportRequest(ExportPayload):
    """POST /export request body: export options plus the report to export."""
    results: Dict[str, Any] = Field(..., description="The full report to export (as returned in a completed job's results field).")

class PublicationRenderRequest(BaseModel):
    """Request body for POST /publication/render — render one publication figure or table
    on demand, without generating a full export."""
    results: Dict[str, Any] = Field(..., description="The statevector-stripped report the browser already holds.")
    artifact_id: str = Field(..., description="Which figure or table to render, from the report's list of available artifacts.")
    format: str = Field(..., description="Output format for this artifact, e.g. 'svg', 'png', 'pdf', 'csv', 'html', 'latex'.")
    scale: int = Field(1, ge=1, le=4, description="Raster resolution multiplier for image formats, 1-4 (rendered at BASE_DPI x scale). Ignored for vector/text formats.")
