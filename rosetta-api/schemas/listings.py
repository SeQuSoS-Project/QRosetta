"""Documented shapes of GET /config, GET /runners, GET /compilers and the circuit catalog
routes, for /openapi.json only.

The routes return their dicts as built; these models are never used to validate or filter
them. Every model allows fields it does not list. A field marked required here is one every
response carries, and `tests/openapi_cli_contract.py` holds it to that for older clients.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, RootModel


class _Open(BaseModel):
    model_config = ConfigDict(extra="allow")


class ServerBlock(_Open):
    """``server`` of GET /config: the version handshake."""
    platform_version: str = Field(..., description="Release of the platform the API image belongs to.")
    api_levels: List[int] = Field(..., description="[min, max]: the API levels this server serves. A breaking change to a route or field raises the maximum; the previous level stays served for at least 12 months.")
    analysis_version: str = Field(..., description="Version of the comparison code that labels new reports.")
    git_sha: str = Field(..., description="Commit the API image was built from, or 'unknown'.")
    features: Dict[str, int] = Field(..., description="Feature name -> version. Features are only added.")


class StatusLabel(_Open):
    label: str
    hint: Optional[str] = Field(..., description="Explanation shown beside the label, or null.")


class StatusLabels(_Open):
    """``status_labels`` of GET /config."""
    runs: Dict[str, StatusLabel] = Field(..., description="Values of runner_statuses.")
    tasks: Dict[str, StatusLabel] = Field(..., description="A playlist circuit's status.")
    phases: Dict[str, StatusLabel] = Field(..., description="A job's phase.")


class SummaryOutcomes(_Open):
    """``summary_outcomes`` of GET /config."""
    analysis_version: str
    roles: Dict[str, Literal["difference", "not_established", "runs_without_output", "agreement"]] = Field(
        ..., description="Outcome name -> role. Names are only added.")


class AgreementThresholdDefaults(_Open):
    fidelity_tolerance: float
    phase_tolerance: float
    norm_tolerance: float
    js_threshold: float
    hellinger_threshold: float


class RequestDefaults(_Open):
    """``request_defaults`` of GET /config: what the server fills in for each run request field."""
    requests: Dict[str, Dict[str, Any]] = Field(..., description="Endpoint key (compare, compare_measured, run_batch_suite, experiments) -> {endpoint, fields: {name: {server_fills, default?, when_omitted?}}, items?}.")
    agreement_thresholds: Dict[str, Any] = Field(..., description="Default agreement thresholds.")
    compile_only: Dict[str, Any] = Field(..., description="What makes /compare or /run_batch_suite a compile-only request.")


class BundledCircuit(_Open):
    source: str
    algorithm: str
    qubits: int


class Limits(_Open):
    """``limits`` of GET /config (see the route description for each bound)."""
    max_qubits_statevector: int
    max_qubits_measured: int
    max_qubits_compile: int
    timeout_min: float
    timeout_max: float
    timeout_default: float
    timing_repeats_max: int
    max_qasm_gate_statements: int
    max_expanded_gates: int
    max_nested_gate_calls: int
    max_classical_bits: int
    shots_min: int
    shots_max: int
    shots_default: int
    max_request_bytes: int
    max_plan_request_bytes: int
    plan_rate_limit: str
    run_rate_limit: str
    run_rate_limit_per_address: str
    render_rate_limit: str
    render_rate_limit_per_address: str
    login_rate_limit: str
    register_rate_limit: str
    access_token_expire_sec: int
    max_experiment_cells: int
    max_batch_tasks: int
    prep_max_mib: float
    prep_timeout_sec: float
    job_storage_max_mib: float
    job_storage_min_free_mib: float
    job_ttl_sec: float
    job_evictable_after_sec: float
    max_export_items: int
    max_report_tasks: int
    max_report_runner_keys: int
    max_report_pairs: int
    max_label_length: int
    email_max_length: int
    password_min_chars: int
    password_max_bytes: int


class ExclusiveGate(_Open):
    """``exclusive`` of GET /config: the exclusive-run switch and the run gate's state."""
    enabled: bool
    max_wait_sec: float
    exclusive_running: bool = Field(..., description="An exclusive dispatch holds the server.")
    exclusive_waiting: int = Field(..., description="Exclusive jobs waiting for the server.")
    shared_running: int = Field(..., description="Ordinary dispatches in flight.")


class ServerConfig(_Open):
    """GET /config."""
    server: ServerBlock
    status_labels: StatusLabels
    summary_outcomes: SummaryOutcomes
    max_qubits_statevector: int
    max_qubits_measured: int
    max_qubits_compile: int
    max_qasm_size: int
    max_qasm_gates: int
    max_runs_per_runner: int
    max_total_runs: int
    execution_mode: str = Field(..., description="'local' or 'kubernetes'.")
    queue_max_wait_sec: float
    agreement_threshold_defaults: AgreementThresholdDefaults
    default_n_shots: int
    request_defaults: RequestDefaults
    bypass_limits_requires_account: bool
    bundled_over_prep_limit: List[BundledCircuit]
    limits: Limits
    exclusive: ExclusiveGate


class PerEndpoint(_Open):
    """A value per run endpoint: ``statevector`` (/run) and ``measured`` (/run_measured)."""
    statevector: Optional[str] = Field(..., description="Null when the runner sets it at run time; each result records the value used.")
    measured: Optional[str] = Field(..., description="Null when the runner sets it at run time; each result records the value used.")


class FreshProbe(BaseModel):
    """Fields a ``fresh=true`` request adds to each row."""
    fresh: Optional[bool] = Field(None, description="fresh=true only: this round probed the service.")
    reason: Optional[str] = Field(None, description="fresh=true only: busy, exclusive_run, no_long_lived_services, disabled or not_deployed, else null.")
    error_kind: Optional[str] = Field(None, description="fresh=true only: dns, connect, timeout or http when the probe got no answer or an error status, else null.")
    probed_at: Optional[str] = Field(None, description="fresh=true only: UTC time of the probe, ISO 8601 ending in 'Z'.")


class RunnerRow(FreshProbe):
    """One runner of GET /runners."""
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Canonical runner key, opaque to clients.")
    enabled: bool
    available: bool
    unavailable_reason: Optional[str] = Field(..., description="Null when available; else disabled, not_deployed, unreachable or the runner's own reason.")
    device: Optional[str] = Field(..., description="What the runner's /capabilities reported, else null.")
    requires_gpu: bool
    max_level: int
    optimization_levels: Dict[str, str] = Field(..., description="Level (as a string) -> description.")
    precision: PerEndpoint = Field(..., description="Amplitude dtype per endpoint, e.g. complex128.")
    qubit_ordering: PerEndpoint = Field(..., description="'lsb' or 'msb' per endpoint.")
    default_selected: bool = Field(..., description="A run that names no backends uses this runner when it is available.")
    profiles: List[str] = Field(..., description="Built-in profiles the runner belongs to.")
    versions: Optional[Dict[str, Any]] = Field(None, description="image_git_sha, image_identity (source, release, git_sha) and build_files as the running image's /capabilities reports them; null when the runner did not report them.")
    backend: Optional[str]
    version: Optional[str]


class CompilerRow(FreshProbe):
    """One compile-only service of GET /compilers."""
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., description="Compiler id, opaque to clients.")
    name: str = Field(..., description="Display name.")
    enabled: bool
    available: bool
    unavailable_reason: Optional[str]
    optimization_levels: Dict[str, str] = Field(..., description="Level (as a string) -> pipeline description.")
    versions: Optional[Dict[str, Any]] = Field(..., description="sdk_versions, native_components, build_files, image_git_sha and image_identity as the running image reports them; null when no long-lived service answered.")
    default_selected: bool
    profiles: List[str]
    backend: Optional[str]
    version: Optional[str]


class RunnerList(RootModel[List[RunnerRow]]):
    """GET /runners: every registered runner, in registry order."""


class CompilerList(RootModel[List[CompilerRow]]):
    """GET /compilers: every registered compile-only service, in registry order."""


class AlgorithmEntry(_Open):
    """One preset circuit family of GET /algorithms."""
    id: str
    name: str
    min_qubits: int
    max_qubits: int
    max_qubits_statevector: int
    max_qubits_measured: int
    default_qubits: int
    description: str


class AlgorithmList(RootModel[List[AlgorithmEntry]]):
    """GET /algorithms, in menu order."""


class ExampleEntry(_Open):
    """One bundled example circuit of GET /examples."""
    name: str = Field(..., description="File name, with .qasm.")
    title: str
    description: str
    mode: str = Field(..., description="The mode the example is meant for: statevector or measured.")
    qubits: int


class ExampleList(RootModel[List[ExampleEntry]]):
    """GET /examples."""


class ExampleText(_Open):
    """GET /examples/{name}."""
    name: str
    qasm: str = Field(..., description="OpenQASM 2.0 text.")


class QasmText(_Open):
    """A circuit's OpenQASM 2.0 text."""
    qasm: str


class MqtIndex(RootModel[Dict[str, List[int]]]):
    """GET /benchmarks/mqt/list: algorithm -> bundled qubit sizes."""


class QasmbenchIndex(RootModel[List[str]]):
    """GET /benchmarks/qasmbench/list: circuit names, sorted."""
