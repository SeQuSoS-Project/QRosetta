"""Pydantic request and response schemas for the benchmark endpoints."""

from pydantic import (
    BaseModel, BeforeValidator, ConfigDict, Field, PlainValidator, StrictBool, StrictInt,
    WithJsonSchema, field_validator, model_validator,
)
import unicodedata
from typing import Annotated, List, Dict, Any, Literal, Optional, Union

from config import settings



def _reject_bool(value):
    if isinstance(value, bool):
        raise ValueError("must be an integer, not a boolean")
    return value


Int = Annotated[int, BeforeValidator(_reject_bool)]
Seed = Annotated[StrictInt, Field(ge=0)]
OptimizationLevel = Annotated[Int, Field(ge=0, le=3)]

RUNNER_CONFIG_MESSAGE = "runner_config values must be an int 0–3 or a non-empty list of ints 0–3"


def _is_level(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 3


def _runner_config_value(value):
    if _is_level(value):
        return value
    if isinstance(value, list) and value and all(_is_level(v) for v in value):
        return list(value)
    raise ValueError(RUNNER_CONFIG_MESSAGE)


RunnerConfigValue = Annotated[
    Union[int, List[int]],
    PlainValidator(_runner_config_value),
    WithJsonSchema({"anyOf": [{"type": "integer", "minimum": 0, "maximum": 3},
                              {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 3}}]}),
]
RunnerConfig = Dict[str, RunnerConfigValue]


def has_control_characters(value: str) -> bool:
    """True when ``value`` holds a control character, a format character (bidirectional
    overrides, zero-width characters) or a line or paragraph separator."""
    return any(unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp") for ch in value)


def _printable_text(value):
    if isinstance(value, str) and has_control_characters(value):
        raise ValueError("must not contain control characters, invisible formatting characters "
                         "(such as direction overrides) or line separators")
    return value


Label = Annotated[str, BeforeValidator(_printable_text), Field(max_length=200)]
TimingRepeats = Annotated[Int, Field(ge=1, le=settings.MAX_TIMING_REPEATS)]
RunnerPhases = Dict[str, Int]
ExecutionTarget = Literal["local", "kubernetes"]
RunMode = Literal["statevector", "measured"]
CircuitSource = Literal["preset", "qasmbench", "mqt", "qasm"]
FigureFormat = Literal["svg", "png", "pdf"]
TableFormat = Literal["latex", "csv", "html", "xlsx"]
PublicationCategory = Literal["agreement", "heatmaps", "performance", "statistical"]
ExportView = Literal["agreement_distribution", "agreement", "statistical_test", "counts",
                     "marginals", "hamming", "rank", "fidelity_heatmap",
                     "js_divergence_heatmap", "hellinger_heatmap", "execution_time",
                     "resource_usage", "metadata", "glossary"]
ItemFormat = Literal["svg", "png", "pdf", "latex", "csv", "html", "markdown", "xlsx", "text"]

_EXCLUSIVE_DESCRIPTION = ("Run for timing: every backend in its own phase, one after another, and "
                          "only while no other run is in flight on this server (other jobs wait, "
                          "and this job waits for running ones; the wait is recorded as "
                          "exclusive_wait_sec). Local mode isolates the server's own runs only; "
                          "it cannot hold back other processes on the host.")
_OPT_LEVEL_DESCRIPTION = ("Requested transpiler/optimization level, 0-3; each backend runs at "
                          "the nearest level it supports (at most its max_level in /runners). "
                          "Each result records optimization_level_requested and the applied "
                          "optimization_level.")
_RUNNER_CONFIG_DESCRIPTION = ("Per-runner optimization-level override. An int runs that runner "
                              "once at that level; a list runs it once per element (repeats "
                              "allowed, e.g. the same level twice). A level above the runner's "
                              "max_level in /runners is rejected with 400.")
_TIMING_REPEATS_DESCRIPTION = (
    "Timed runs per backend, 1-10, after the one discarded warm-up. Each timed run is a full "
    "compile + execute with the same seed. compilation_time_sec and simulation_time_sec are "
    "the medians over the timed runs (timing_statistic 'median'), execution_time_sec their "
    "sum; per-run values are in compilation_time_samples and simulation_time_samples with "
    "*_sec_mean, *_sec_median and *_sec_stdev. Counts, statevector and memory come from the "
    "first timed run. The per-run timeout covers the warm-up and every timed run.")
_TIMEOUT_DESCRIPTION = (f"Requested wall-clock budget per run in seconds, at least "
                        f"{settings.MIN_TIMEOUT_SEC}; values above the server's RUNNER_TIMEOUT_SEC "
                        f"are clamped to it. It starts when the run leaves the runner's queue; "
                        f"the queue wait is capped separately by the server's "
                        f"RUNNER_QUEUE_MAX_WAIT_SEC (the report's queue_max_wait_sec).")
_SHOTS_DESCRIPTION = (
    f"Number of shots each runner samples, {settings.MIN_SHOTS} to {settings.MAX_SHOTS}. "
    f"Default {settings.DEFAULT_SHOTS}. The statistical test labels a backend pair "
    f"'consistent' only when its power to detect a total-variation distance of 0.05 is at "
    f"least 0.8 at the Benjamini-Yekutieli level alpha/(m*c_m) over the m backend pairs. "
    f"The report computes each pair's power and recommended_shots_per_backend for the "
    f"circuit's outcome count and backend set; circuits with more outcomes or more backends "
    f"need more shots.")
_TARGET_DESCRIPTION = ("'local' or 'kubernetes'. Defaults to the server's EXECUTION_MODE. Runs "
                       "are dispatched according to the server's EXECUTION_MODE; the job's "
                       "'target' records the mode actually used and 'requested_target' this "
                       "value.")
_BYPASS_DESCRIPTION = ("Skip the MAX_QASM_SIZE and MAX_QASM_GATES checks when the server's "
                       "EXECUTION_MODE is 'local'; ignored otherwise. The qubit limits, the "
                       "expanded-gate and nested-gate-call limits, the syntax checks and the "
                       "measurement checks still apply.")
_SEED_DESCRIPTION = ("Master seed, a non-negative integer. Each runner result receives its own "
                     "seed derived from it and the result key (see the report's "
                     "seed_derivation and each result's runner_seed), so a replay with the "
                     "same master seed reproduces every runner's sampling. Omit for a "
                     "generated master seed, which is recorded in the report.")
_PREPROCESSING_DESCRIPTION = (
    "Whether preprocessing is applied. Each runner applies its own pass (e.g. barrier "
    "stripping, gate rebasing). The API also rewrites the circuit it dispatches to every "
    "runner group (statevector, measured with native sampling, measured with statevector "
    "sampling): quantum registers are merged into one in declaration order, and the circuit "
    "is parsed and re-emitted with pytket, which inlines custom gate definitions, rewrites "
    "gates into pytket's QASM gate set and removes barriers. With false, every runner "
    "receives the circuit as submitted, except that statevector mode removes terminal "
    "measurements and native samplers get measure-all appended to a circuit without "
    "measure statements. Every change is listed in api_preprocessing_applied and each "
    "result's preprocessing_applied.")


_COMPILERS_DESCRIPTION = (
    "Compile-only services to run after the simulators, as compiler id -> list of distinct "
    "optimization levels (GET /compilers lists them). Each compiles the circuit the API "
    "prepares for statevector runners (recorded as compile_input) and returns only circuit "
    "text, recorded in compiled_circuits; compilers are not simulated and are not part of "
    "the pairwise comparison. Empty runs none.")


def _check_compilers(value):
    if not isinstance(value, dict):
        raise ValueError("compilers must map compiler ids to lists of optimization levels")
    total = 0
    for name, levels in value.items():
        if not isinstance(levels, list) or not levels or not all(_is_level(lvl) for lvl in levels):
            raise ValueError(f"compilers[{name!r}] must be a non-empty list of ints 0–3")
        if len(set(levels)) != len(levels):
            raise ValueError(f"compilers[{name!r}] repeats a level; compilation is deterministic")
        total += len(levels)
    limit = settings.max_compile_jobs()
    if total > limit:
        raise ValueError(f"at most {limit} compile jobs per circuit")
    return value


Compilers = Annotated[Dict[str, List[int]], BeforeValidator(_check_compilers)]


class _Request(BaseModel):
    """Request body base: unknown fields are rejected."""
    model_config = ConfigDict(extra="forbid")


def _default_execution_target() -> str:
    return settings.EXECUTION_MODE


class AgreementThresholds(BaseModel):
    """Cut-offs the comparator uses to label a backend pair as agreeing or not.

    Optional on every run payload; an omitted field keeps its default. The statevector
    tolerances are numerical-precision cut-offs. The measured cut-offs (JS divergence in
    nats, Hellinger distance) are descriptive and shot-count dependent; the report's
    statistical_test block carries the shot-noise-aware verdict. The values used are
    recorded in every pairwise_agreement record and in the divergence report's
    agreement_thresholds, next to its analysis_version. NaN and infinity are rejected.
    """
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")

    fidelity_tolerance: float = Field(1e-5, ge=0, description="A statevector pair agrees when fidelity >= 1 minus this value.")
    phase_tolerance: float = Field(1e-6, ge=0, description="A global phase offset arg<a|b> between two statevectors within this many radians of 0 is reported as 0 (the pair then agrees directly). The default lies above complex64 rounding (about 1e-8 rad). Reported in the relative_phase* fields.")
    norm_tolerance: float = Field(1e-4, ge=0, description="A statevector whose norm differs from 1 by more than this is flagged unnormalized_input; an agreeing pair is then labelled 'agree_after_normalization'.")
    js_threshold: float = Field(0.01, ge=0, description="Jensen-Shannon divergence (nats) between two backends' measured distributions above this is 'distance_exceeds_threshold'.")
    hellinger_threshold: float = Field(0.1, ge=0, description="Hellinger distance between two backends' measured distributions above this is 'distance_exceeds_threshold'.")

_SIMULATE_DESCRIPTION = (
    "false runs only the requested compile-only services on the circuit (compilers must not be "
    "empty) and no simulator; the report then has no simulator results and records simulated: false. "
    "runner_config, runner_phases and target_simulators must then be empty."
)


def _check_compile_only(payload):
    """A compile-only request names compilers and no simulator settings."""
    if payload.simulate:
        return payload
    if not payload.compilers:
        raise ValueError("simulate=false needs at least one compile-only service in compilers")
    named = [f for f in ("runner_config", "runner_phases", "target_simulators") if getattr(payload, f)]
    if named:
        raise ValueError(f"simulate=false runs no simulator; leave {', '.join(named)} empty")
    return payload


class QasmPayload(_Request):
    """Request body for POST /compare — an exact statevector comparison of one OpenQASM 2.0
    circuit across the simulator fleet."""
    qasm_string: str = Field(..., description="The circuit to run, as OpenQASM 2.0 text.")
    optimization_level: OptimizationLevel = Field(0, description=_OPT_LEVEL_DESCRIPTION)
    runner_config: RunnerConfig = Field({}, description=_RUNNER_CONFIG_DESCRIPTION)
    runner_phases: RunnerPhases = Field({}, description="Maps runner id to a phase number. Runners sharing a phase run concurrently; phases execute in ascending order. Absent/empty means every runner executes concurrently.")
    timeout_seconds: Int = Field(settings.DEFAULT_TIMEOUT_SEC, ge=settings.MIN_TIMEOUT_SEC, description=_TIMEOUT_DESCRIPTION)
    timing_repeats: TimingRepeats = Field(1, description=_TIMING_REPEATS_DESCRIPTION)
    exclusive: StrictBool = Field(False, description=_EXCLUSIVE_DESCRIPTION)
    target_simulators: List[str] = Field(default_factory=list, description="Which runner ids to dispatch to. Empty means every enabled runner.")
    execution_target: ExecutionTarget = Field(default_factory=_default_execution_target, description=_TARGET_DESCRIPTION)
    bypass_limits: StrictBool = Field(False, description=_BYPASS_DESCRIPTION)
    apply_preprocessing: StrictBool = Field(True, description=_PREPROCESSING_DESCRIPTION)
    thresholds: Optional[AgreementThresholds] = Field(None, description="Override the default agreement thresholds for this run. Omit to use the defaults.")
    compilers: Compilers = Field(default_factory=dict, description=_COMPILERS_DESCRIPTION)
    simulate: StrictBool = Field(True, description=_SIMULATE_DESCRIPTION)

    @model_validator(mode="after")
    def _compile_only(self):
        return _check_compile_only(self)

class MeasuredQasmPayload(_Request):
    """Request body for POST /compare_measured — a shot-based measurement comparison of one
    OpenQASM 2.0 circuit across the simulator fleet."""
    qasm_string: str = Field(..., description="The circuit to run, as OpenQASM 2.0 text. A circuit without measure statements is measured on every qubit (see api_preprocessing_applied).")
    n_shots: Int = Field(settings.DEFAULT_SHOTS, ge=settings.MIN_SHOTS, le=settings.MAX_SHOTS, description=_SHOTS_DESCRIPTION)
    optimization_level: OptimizationLevel = Field(0, description=_OPT_LEVEL_DESCRIPTION)
    runner_config: RunnerConfig = Field({}, description=_RUNNER_CONFIG_DESCRIPTION)
    runner_phases: RunnerPhases = Field({}, description="Maps runner id to a phase number. Runners sharing a phase run concurrently; phases execute in ascending order.")
    timeout_seconds: Int = Field(settings.DEFAULT_TIMEOUT_SEC, ge=settings.MIN_TIMEOUT_SEC, description=_TIMEOUT_DESCRIPTION)
    timing_repeats: TimingRepeats = Field(1, description=_TIMING_REPEATS_DESCRIPTION)
    exclusive: StrictBool = Field(False, description=_EXCLUSIVE_DESCRIPTION)
    target_simulators: List[str] = Field(default_factory=list, description="Which runner ids to dispatch to. Empty means every enabled runner.")
    execution_target: ExecutionTarget = Field(default_factory=_default_execution_target, description=_TARGET_DESCRIPTION)
    bypass_limits: StrictBool = Field(False, description=_BYPASS_DESCRIPTION)
    apply_preprocessing: StrictBool = Field(True, description=_PREPROCESSING_DESCRIPTION)
    seed: Optional[Seed] = Field(None, description=_SEED_DESCRIPTION)
    thresholds: Optional[AgreementThresholds] = Field(None, description="Override the default agreement thresholds for this run.")
    compilers: Compilers = Field(default_factory=dict, description=_COMPILERS_DESCRIPTION)

class GenerateCircuitPayload(_Request):
    """Request body for POST /generate_circuit — build one preset circuit's OpenQASM text
    server-side, without running it."""
    algorithm: str = Field(..., description="Preset circuit family, e.g. 'ghz', 'bell', 'qft', 'bv', 'grover'.")
    qubits: Int = Field(..., ge=1, description="Number of qubits to generate the circuit for.")
    seed: Optional[Seed] = Field(None, description="Seed for presets with random content (e.g. 'random'). Omit to derive it from the qubit count, so the same request always yields the same circuit.")

class BenchmarkTask(_Request):
    """One circuit within a batch run (POST /run_batch_suite)."""
    name: Optional[Label] = Field(None, description="Display name for this circuit in the report and progress list. Omit to use algorithm.")
    algorithm: Optional[Label] = Field(None, description="Circuit identifier: a preset family name, or the file name for a bundled benchmark circuit. Required unless qasm_string is given, where it is only a label.")
    qubits: Optional[Int] = Field(None, ge=0, description="Number of qubits for a generated preset or MQT Bench circuit; required for those sources. Optional and ignored for QASMBench and literal circuits, whose qubit count is read from the QASM.")
    qasm_string: Optional[str] = Field(None, description="User-supplied OpenQASM 2.0 text. When present, this is run as-is and algorithm/qubits/source are ignored.")
    source: Optional[CircuitSource] = Field(None, description="Where to resolve the circuit from when qasm_string is absent: None or 'preset' generates it from the built-in circuit library; 'qasmbench' or 'mqt' loads it from the corresponding bundled benchmark suite; 'qasm' requires qasm_string.")

    @model_validator(mode="after")
    def _qubits_for_generated_sources(self):
        if not self.qasm_string and not self.algorithm:
            raise ValueError("algorithm is required unless qasm_string is given")
        if not self.qasm_string and (self.source or "preset") in ("preset", "mqt") and self.qubits is None:
            raise ValueError("qubits is required for preset and MQT Bench tasks")
        return self

class BatchPayload(_Request):
    """Request body for POST /run_batch_suite — run a list of circuits (BenchmarkTask entries)
    across the simulator fleet in a single job."""
    tasks: List[BenchmarkTask] = Field(..., description="The circuits to run, in order.")
    n_shots: Int = Field(settings.DEFAULT_SHOTS, ge=settings.MIN_SHOTS, le=settings.MAX_SHOTS, description=_SHOTS_DESCRIPTION + " Used only when mode is 'measured'.")
    mode: RunMode = Field(..., description="'statevector' or 'measured'.")
    optimization_level: OptimizationLevel = Field(0, description=_OPT_LEVEL_DESCRIPTION)
    runner_config: RunnerConfig = Field({}, description=_RUNNER_CONFIG_DESCRIPTION)
    runner_phases: RunnerPhases = Field({}, description="Maps runner id to a phase number for staged concurrent execution, same semantics as in QasmPayload.")
    timeout_seconds: Int = Field(settings.DEFAULT_TIMEOUT_SEC, ge=settings.MIN_TIMEOUT_SEC, description=_TIMEOUT_DESCRIPTION)
    timing_repeats: TimingRepeats = Field(1, description=_TIMING_REPEATS_DESCRIPTION)
    exclusive: StrictBool = Field(False, description=_EXCLUSIVE_DESCRIPTION)
    target_simulators: List[str] = Field(default_factory=list, description="Which runner ids to dispatch to. Empty means every enabled runner.")
    execution_target: ExecutionTarget = Field(default_factory=_default_execution_target, description=_TARGET_DESCRIPTION)
    bypass_limits: StrictBool = Field(False, description=_BYPASS_DESCRIPTION)
    apply_preprocessing: StrictBool = Field(True, description=_PREPROCESSING_DESCRIPTION)
    seed: Optional[Seed] = Field(None, description=_SEED_DESCRIPTION + " One master seed covers every task; used only when mode is 'measured'.")
    thresholds: Optional[AgreementThresholds] = Field(None, description="Override the default agreement thresholds for this run.")
    compilers: Compilers = Field(default_factory=dict, description=_COMPILERS_DESCRIPTION + " Applied to every task.")
    simulate: StrictBool = Field(True, description=_SIMULATE_DESCRIPTION + " Applies to every task.")

    @model_validator(mode="after")
    def _compile_only(self):
        return _check_compile_only(self)

class ExperimentCircuit(_Request):
    """One circuit to include in an experiment (POST /experiments), from any of the wired
    sources.

    source = "preset"    -> generated via circuit_library (needs algorithm + qubits)
             "qasmbench" -> bundled QASMBench circuit (algorithm = circuit file name)
             "mqt"       -> bundled MQTBench circuit (needs algorithm + qubits)
             "qasm"      -> user-supplied OpenQASM in qasm_string
    """
    source: CircuitSource = Field("preset", description="Where to resolve this circuit from: 'preset', 'qasmbench', 'mqt', or 'qasm'.")
    algorithm: Optional[Label] = Field(None, description="Circuit identifier for the 'preset', 'qasmbench', or 'mqt' sources.")
    qubits: Int = Field(0, ge=0, description="Number of qubits, for the 'preset' and 'mqt' sources. For 'qasmbench' and 'qasm' the count is read from the QASM.")
    qasm_string: Optional[str] = Field(None, description="User-supplied OpenQASM 2.0 text, for source='qasm'.")
    name: Optional[Label] = Field(None, description="Display label for this circuit in the frozen bundle; defaults to a name derived from algorithm/qubits.")

class ExperimentPayload(_Request):
    """Request body for POST /experiments — run a fixed set of circuits across the fleet
    over one or more preprocessing axes, and freeze the inputs, environment, and outputs into
    a citable artifact bundle (downloaded via GET /experiments/{job_id}/bundle)."""
    circuits: List[ExperimentCircuit] = Field(..., description="The circuits to include.")
    mode: RunMode = Field("measured", description="'statevector' or 'measured'.")
    n_shots: Int = Field(settings.DEFAULT_SHOTS, ge=settings.MIN_SHOTS, le=settings.MAX_SHOTS, description=_SHOTS_DESCRIPTION + " Used only when mode is 'measured'.")
    optimization_level: OptimizationLevel = Field(0, description=_OPT_LEVEL_DESCRIPTION)
    runner_config: RunnerConfig = Field({}, description=_RUNNER_CONFIG_DESCRIPTION)
    runner_phases: RunnerPhases = Field({}, description="Maps runner id to a phase number for staged concurrent execution.")
    timeout_seconds: Int = Field(settings.DEFAULT_TIMEOUT_SEC, ge=settings.MIN_TIMEOUT_SEC, description=_TIMEOUT_DESCRIPTION)
    timing_repeats: TimingRepeats = Field(1, description=_TIMING_REPEATS_DESCRIPTION)
    exclusive: StrictBool = Field(False, description=_EXCLUSIVE_DESCRIPTION)
    target_simulators: List[str] = Field(default_factory=list, description="Which runner ids to include. Empty means every enabled runner.")
    execution_target: ExecutionTarget = Field(default_factory=_default_execution_target, description=_TARGET_DESCRIPTION)
    bypass_limits: StrictBool = Field(False, description=_BYPASS_DESCRIPTION + " For experiments it also lifts the circuit-axis cell cap.")
    preprocessing_modes: List[StrictBool] = Field(default_factory=lambda: [True], min_length=1, max_length=2, description="The preprocessing axis: the whole circuit set runs once per value in this list (True = preprocessing applied, False = raw circuit). One or both of true and false, each at most once.")
    seed: Optional[Seed] = Field(None, description=_SEED_DESCRIPTION + " One master seed covers every circuit and axis and is recorded in the manifest.")
    thresholds: Optional[AgreementThresholds] = Field(None, description="Override the default agreement thresholds for this experiment.")
    compilers: Compilers = Field(default_factory=dict, description=_COMPILERS_DESCRIPTION + " Applied to every circuit on every axis.")
    keep_statevectors: StrictBool = Field(False, description="Keep full statevectors in the frozen results bundle. Default strips them to a sha256 hash + length to keep the bundle small; the live report is unaffected either way.")
    label: Optional[Label] = Field(None, description="Human-readable name for this experiment, recorded in the manifest.")

    @field_validator("preprocessing_modes")
    @classmethod
    def _unique_modes(cls, modes):
        if len(set(modes)) != len(modes):
            raise ValueError("preprocessing_modes must not repeat a value")
        return modes

class VisualizerResponse(BaseModel):
    """Response body carrying a URL to an interactive circuit visualization."""
    url: str = Field(..., description="URL of the rendered visualization.")

class JobStatusResponse(BaseModel):
    """Response body for GET /jobs/{job_id}, and the initial response to every job-creating
    POST endpoint (/compare, /compare_measured, /run_batch_suite, /experiments)."""
    job_id: str = Field(..., description="Identifier to poll via GET /jobs/{job_id}.")
    status: str = Field(..., description="'pending', 'processing', 'completed', or 'failed'. 'failed' means the circuit could not be dispatched (e.g. it does not parse), every runner returned an error, or every task of a batch failed. A failed job that reached the runners still carries its report in results.")
    target: str = Field(..., description="The execution mode this job was dispatched with ('local' or 'kubernetes').")
    requested_target: Optional[str] = Field(None, description="The execution_target value the request carried (the server's EXECUTION_MODE when omitted).")
    results: Optional[Dict[str, Any]] = Field(None, description="The report, present once status is 'completed' (and for a failed single-circuit job).")
    error: Optional[str] = Field(None, description="Failure message, present if status is 'failed', e.g. 'all 14 runners failed'.")
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

class PublicationItem(_Request):
    """One export view with its parameters and the formats to write."""
    view: ExportView = Field(..., description="The view: a figure and/or table (or text) of the report.")
    params: Dict[str, Any] = Field(default_factory=dict, description="The view's parameters (backends, layout, outcomes, figure size, ...); omitted ones take their defaults. Recorded in figures/<slug>.spec.json.")
    formats: List[ItemFormat] = Field(..., min_length=1, max_length=9, description="Formats to write: figure formats (svg, png, pdf) for the view's figure, table formats (latex, csv, html, markdown, xlsx) for its table, markdown/text for a text view.")

class PublicationArtifactsSelection(_Request):
    """Opt-in selection of publication-ready figures/tables to bundle into an RO-Crate export.

    Either ``items`` (views with parameters) or ``categories`` (every artifact of a category at
    its defaults); empty or absent, nothing is generated (the default).
    """
    items: List[PublicationItem] = Field(default_factory=list, max_length=60, description="Views to write, each with its parameters and formats. Figures go to figures/<slug>.<fmt> with a .spec.json, tables to tables/<slug>.<ext>.")
    categories: List[PublicationCategory] = Field(default_factory=list, description="Which artifact categories to generate: 'agreement', 'heatmaps', 'performance', 'statistical'. Empty generates none.")
    figure_formats: List[FigureFormat] = Field(default_factory=lambda: ["svg"], description="Formats to render each figure in: 'svg', 'png', 'pdf'.")
    table_formats: List[TableFormat] = Field(default_factory=lambda: ["csv"], description="Formats to render each table in: 'latex', 'csv', 'html', 'xlsx'.")

class ExportPayload(_Request):
    """Options for exporting a completed report as a citable artifact."""
    format: Literal["ro-crate"] = Field("ro-crate", description="Export format. Only 'ro-crate' (an RO-Crate 1.1 archive conforming to the Process Run Crate profile) is accepted.")
    include_statevectors: StrictBool = Field(False, description="Include full statevectors in the export. Default strips them to keep the archive small.")
    author_name: Optional[Label] = Field(None, description="Author name recorded in the crate's metadata.")
    author_affiliation: Optional[str] = Field(None, description="Author affiliation recorded in the crate's metadata.")
    publication_artifacts: Optional[PublicationArtifactsSelection] = Field(None, description="Optionally bundle publication-ready figures/tables into the crate alongside the raw results.")

class ExportRequest(ExportPayload):
    """POST /export request body: export options plus the report to export."""
    results: Dict[str, Any] = Field(..., description="The full report to export (as returned in a completed job's results field).")

class PublicationJobRenderRequest(_Request):
    """Request body for POST /jobs/{job_id}/publication/render: one figure or table drawn from
    the server's copy of a finished job, so no report is uploaded."""
    artifact_id: str = Field(..., description="Which figure or table to render, from the report's list of available artifacts.")
    format: str = Field(..., description="Output format for this artifact, e.g. 'svg', 'png', 'pdf', 'csv', 'xlsx'.")
    scale: Int = Field(1, ge=1, le=4, description="Raster resolution multiplier for image formats, 1-4. Ignored for vector/text formats.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters of the artifact's view; omitted ones take their defaults.")
    task: Optional[Int] = Field(None, ge=0, description="For a playlist job: the index of the circuit in benchmark_summary. Omit for a single-circuit job.")

class PublicationRenderRequest(_Request):
    """Request body for POST /publication/render — render one publication figure or table
    on demand, without generating a full export."""
    results: Dict[str, Any] = Field(..., description="The statevector-stripped report the browser already holds.")
    artifact_id: str = Field(..., description="Which figure or table to render, from the report's list of available artifacts.")
    format: str = Field(..., description="Output format for this artifact, e.g. 'svg', 'png', 'pdf', 'csv', 'html', 'latex'.")
    scale: Int = Field(1, ge=1, le=4, description="Raster resolution multiplier for image formats, 1-4 (rendered at BASE_DPI x scale). Ignored for vector/text formats.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters of the artifact's view (backends, layout, outcomes, figure size, ...); omitted ones take their defaults.")
