"""Documented shapes of the reports a job produces, for /openapi.json only.

Routes return the reports as built (dicts); these models are never used to validate or
filter them. Every model allows fields it does not list.
"""

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, RootModel

from schemas.benchmark import JobStatusResponse, RunnerPerformanceMetrics


class _Open(BaseModel):
    model_config = ConfigDict(extra="allow")


class RunnerResult(RunnerPerformanceMetrics):
    """One entry of ``raw_results``: one run of one backend (key ``<id>`` or
    ``<id>~opt<L>~run<N>`` when a backend runs at several levels)."""
    model_config = ConfigDict(extra="allow")

    dispatch_status: Optional[Literal["ok", "error", "timeout", "offline"]] = Field(None, description="How the dispatch ended: ok, error (the simulator rejected or crashed on the circuit), timeout, offline (service unreachable).")
    statevector: Optional[Union[str, List[Any]]] = Field(None, description="Statevector mode: the final state as Base64 of little-endian complex128 pairs, 2**declared_qubits amplitudes. In GET /jobs/{job_id} a vector over 16384 amplitudes (more than 14 qubits) is replaced by a placeholder string and statevector_omitted_for_display is true; GET /jobs/{job_id}/report has the full vector. Saved runs keep statevector_sha256 and statevector_length instead.")
    statevector_omitted_for_display: Optional[bool] = Field(None, description="True when statevector holds the display placeholder instead of the vector.")
    counts: Optional[Dict[str, int]] = Field(None, description="Measured mode: outcome bitstring -> shots. Keys are the circuit's classical bits in declaration order, bit 0 rightmost for 'lsb' runners (qubit_ordering).")
    qubit_ordering: Optional[str] = Field(None, description="'lsb' or 'msb': how this backend labels basis states.")
    precision: Optional[str] = Field(None, description="'complex64' or 'complex128'.")
    runner_seed: Optional[int] = Field(None, description="Measured mode: the seed this run received, derived from the report's seed and this result's key.")
    image_identity: Optional[Dict[str, Any]] = Field(None, description="What the runner's serving process read about its image: source (release, built_locally or 'not recorded'), release, git_sha, container (the runtime's view) and host_hypervisor_cpu_flag.")
    build_files: Optional[Dict[str, str]] = Field(None, description="sha256 of each build file the image copied (Dockerfile, requirements.lock).")
    runner_image: Optional[str] = Field(None, description="The image the API created a Kubernetes Job with, else the image the runtime showed the runner, else 'not recorded'; runner_image_basis says which.")
    specimen: Optional[Dict[str, Any]] = Field(None, description="kind (published_release, built_locally or 'not recorded'), release, image_git_sha and runner_image of a result that ran.")
    timing_caveats: Optional[List[Dict[str, Any]]] = Field(None, description="Conditions that limit how far this run's timings compare: {code, text, fields, detail?}.")
    server_overlapping_host_load: Optional[int] = Field(None, description="Local dispatch: host-load notices (qrosetta start, stop, remove, build, pull or image probes on this host) open at some time this run was in flight; null where not recorded (Kubernetes, or a run that never reached a runner).")
    stopped_by_user: Optional[bool] = Field(None, description="True when the run lost its runner or compiler while a stop notice (qrosetta stop --force or remove) covered that service; the error says so.")
    process_exit_code: Optional[int] = Field(None, description="When the runner's isolated process ended without a result: its exit code (negative: the signal number that ended it, as Python reports it).")
    process_exit_signal: Optional[str] = Field(None, description="When that process was ended by a signal: the signal's name, e.g. SIGKILL. A SIGKILL is what the kernel sends when memory runs out, and also what a forced stop sends, so it does not identify the cause alone.")


class PairVerdict(_Open):
    """``pair_verdict`` of a pair record: the verdict every view of the report shows for it."""
    verdict: Literal["not_comparable", "differs_by_only", "differs", "inconclusive", "agrees", "bit_order", "unassessed"] = Field(..., description="The pair's class, decided in this order: not compared; differs only under Benjamini–Yekutieli (measured; not under Holm, no single-bit marginal differs); differs (statevector: residual, only after an undeclared qubit permutation, or only in the basis the declared orderings do not imply; measured: distinguishable or a single-bit marginal differs); inconclusive (measured: inconclusive_low_shots or ambiguous); agrees; agrees after the bit reversal the declared orderings imply (statevector); no verdict recorded.")
    differs: bool = Field(..., description="The pair is a disagreement (badges, Agreement tab, Summary).")
    differs_by_only: bool = Field(..., description="Measured: its only evidence is significance under Benjamini–Yekutieli, not under Holm.")
    differs_full: bool = Field(..., description="Measured: differs on the full-distribution test (not BY only).")
    differs_marginal: bool = Field(..., description="Measured: differs in a single-bit marginal (not BY only).")
    agrees: bool = Field(..., description="Statevector: agrees (bit order as declared included); measured: consistent within shot noise and not a disagreement.")
    inconclusive: bool = Field(..., description="Measured: the shot-noise assessment is inconclusive_low_shots or ambiguous.")
    assessment: Optional[Any] = Field(None, description="The shot-noise assessment: measured_assessment, else metrics.measured_assessment, else read from metrics.statistical_test.verdict; not_comparable for a pair not compared; null when none is recorded.")
    statevector_group: Literal["agree", "bit_order", "disagree", "not_comparable", "other"] = Field(..., description="The group of the agreement label: agree (directly, up to a global phase, after normalisation), bit_order, disagree, not_comparable or other.")
    effective_agreement: Optional[Any] = Field(None, description="The agreement label; for agree_after_normalization the label the normalised vectors received.")
    unaligned_basis: Optional[str] = Field(None, description="direct or bit_reversal when the pair matches only in the basis its declared orderings do not imply; 'unrecorded' when the record says so without naming the basis.")


class BackendVerdict(_Open):
    """One backend (or run) in ``backend_verdicts``."""
    key: str = Field(..., description="Result key.")
    status: Literal["ok", "error", "timeout", "offline"] = Field(..., description="dispatch_status, or for results without one, read from the error text.")
    compared: int = Field(..., description="Pairs with this backend that were compared.")
    differs: int = Field(..., description="Compared pairs that differ (BY-only ones included).")
    differs_full: int = Field(..., description="Measured: pairs that differ on the full-distribution test.")
    differs_marginal: int = Field(..., description="Measured: pairs in which a single-bit marginal differs.")
    differs_by_only: int = Field(..., description="Measured: pairs that differ under Benjamini–Yekutieli only.")
    inconclusive: int = Field(..., description="Measured: pairs that are inconclusive on the full-distribution test.")
    not_comparable: int = Field(..., description="Pairs that could not be compared.")
    differs_with: List[str] = Field(..., description="Backends it differs from, BY-only pairs left out.")
    by_only_with: List[str] = Field(..., description="Backends it differs from under Benjamini–Yekutieli only.")
    agrees_with: List[str] = Field(..., description="Backends it agrees with.")
    compared_with: List[str] = Field(..., description="Backends it was compared with.")
    worst_fidelity: Optional[float] = Field(None, description="Statevector: lowest label-aligned fidelity of a pair that differs.")
    largest_tv: Optional[float] = Field(None, description="Measured: largest total variation of a pair that differs.")
    bit_order: Optional[Any] = Field(None, description="The backend's entry in ordering_map.")
    size_with: Dict[str, float] = Field(..., description="Other backend -> total variation (measured) or label-aligned fidelity (statevector) of their pair.")


class BackendVerdicts(_Open):
    """``divergence_report.backend_verdicts``: per-backend counts over the pair verdicts."""
    mode: Literal["statevector", "measured"]
    backends: List[BackendVerdict] = Field(..., description="Backends of raw_results, then of simulators, then of the pairs, in that order.")
    pairs: int = Field(..., description="Pair records.")
    disagreeing: int = Field(..., description="Compared pairs that differ (BY-only ones included).")
    by_only: int = Field(..., description="Pairs that differ under Benjamini–Yekutieli only.")
    by_only_pairs: List[List[str]]
    inconclusive: int
    not_comparable: int
    marginal_tested: bool = Field(..., description="Some measured pair has single-bit marginal tests.")
    multi_run: bool = Field(..., description="Some key is <id>~opt<L>~run<N>.")


class PairwiseAgreement(_Open):
    """One entry of ``divergence_report.pairwise_agreement``: one pair of runs."""
    simulators: List[str] = Field(..., description="The two result keys compared.")
    mode: Literal["statevector", "measured"] = Field(..., description="Which comparison produced the record.")
    agreement: str = Field(..., description="Statevector mode: the verdict label, e.g. agree_directly, agree_up_to_global_phase, residual_disagreement; the manual's agreement section says which labels are disagreements. Measured mode: a distance label only (JS divergence and Hellinger distance against their thresholds); it ignores shot noise and is not the verdict.")
    measured_assessment: Optional[Literal["consistent_within_shot_noise", "inconclusive_low_shots", "ambiguous", "distinguishable", "not_comparable"]] = Field(None, description="Measured mode only: the verdict. 'distinguishable' is the only disagreement; check marginal_assessment too. A CI check of a measured run reads this field, not agreement.")
    marginal_assessment: Optional[str] = Field(None, description="Measured mode only: the single-bit marginal tests' outcome; a significant one is a disagreement too.")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Distances, fidelities and test statistics behind the labels.")
    pair_verdict: Optional[PairVerdict] = Field(None, description="The pair's verdict (reports from analysis version divergence-2026.10.27.1 on; POST /summary computes it for older reports).")


class DivergenceReport(_Open):
    """Cross-backend agreement of one circuit."""
    simulators: Optional[List[str]] = Field(None, description="Result keys in matrix order.")
    fidelity_matrix: Optional[List[List[Optional[float]]]] = Field(None, description="Statevector mode: pairwise fidelity; null for pairs not compared.")
    pairwise_agreement: Optional[List[PairwiseAgreement]] = Field(None, description="One record per pair of runs.")
    statistical_test_summary: Optional[Dict[str, Any]] = Field(None, description="Measured mode: multiple-testing correction, power, recommended shots and measured_assessment_counts.")
    backend_verdicts: Optional[BackendVerdicts] = Field(None, description="Per-backend counts over the pair verdicts (reports from analysis version divergence-2026.10.27.1 on).")
    error: Optional[str] = Field(None, description="Present when the analysis failed; the raw results are still in the report.")


class CompiledCircuit(_Open):
    """One entry of ``compiled_circuits``: one compile of one compile-only service."""
    compiler: str = Field(..., description="Record key: '<id>~opt<level>~run1' (the same key the job's runner_statuses uses).")
    compiler_id: str = Field(..., description="Compiler id, e.g. 'qmap'.")
    optimization_level: Optional[int] = Field(None, description="Pipeline level that ran.")
    dispatch_status: Optional[str] = Field(None, description="ok, error, timeout, offline or skipped.")
    transpiled_qasm: Optional[str] = Field(None, description="The compiled circuit.")
    refusal: Optional[str] = Field(None, description="Why the compiler refused the input or its output failed the check.")
    error: Optional[str] = Field(None, description="Failure message.")


class SingleCircuitReport(_Open):
    """The report of one circuit (POST /compare, /compare_measured, or one playlist task)."""
    input_qasm: Optional[str] = Field(None, description="The circuit as submitted.")
    n_shots: Optional[int] = Field(None, description="Measured mode only; its presence marks a measured report.")
    seed: Optional[int] = Field(None, description="Measured mode: the master seed (never null).")
    simulated: Optional[bool] = Field(None, description="false for a compile-only run (simulate=false): raw_results is empty.")
    raw_results: Optional[List[RunnerResult]] = Field(None, description="One entry per run, a list (not a map keyed by backend). Absent when the circuit failed before dispatch (then error is set).")
    divergence_report: Optional[DivergenceReport] = Field(None, description="Cross-backend agreement.")
    performance_report: Optional[Dict[str, Any]] = Field(None, description="'ranking' (successful runs, fastest first) and 'unranked' (with a reason).")
    resource_report: Optional[Dict[str, Any]] = Field(None, description="'ranking' by process_peak_rss_mb and 'unranked'.")
    compiled_circuits: Optional[List[CompiledCircuit]] = Field(None, description="Present when compilers were requested.")
    dispatched_circuits: Optional[List[Dict[str, Any]]] = Field(None, description="The exact text each runner group received, with the API's changes.")
    task_name: Optional[str] = Field(None, description="Playlist task only: display label, the task's name (or algorithm) followed by ' (<n>q)'; the name as sent is task_request.name.")
    task_qubits: Optional[int] = Field(None, description="Playlist task only: the circuit's qubit count.")
    task_request: Optional[Dict[str, Any]] = Field(None, description="Playlist task only: how the task asked for its circuit (source, algorithm, qubits, literal_qasm, name).")
    error: Optional[str] = Field(None, description="Set when the circuit (or task) failed before any runner ran.")
    specimens: Optional[Dict[str, Any]] = Field(None, description="statement (all_published, all_built_locally, mixed, unknown, none_ran), meaning, backends, image_git_shas, no_result, notes.")
    timing_caveats: Optional[List[Dict[str, Any]]] = Field(None, description="Report-level timing caveats: {code, text, fields, backends, detail?}; rules versioned by timing_caveats_version.")
    timing_caveats_version: Optional[str] = Field(None, description="Version of the timing caveat rules, separate from analysis_version.")
    run_completeness: Optional[Dict[str, Any]] = Field(None, description="Finished jobs: job_status, planned_tasks, recorded_tasks, tasks_with_results, stopped_early, reason.")


class BatchReport(_Open):
    """The report of a playlist (POST /run_batch_suite)."""
    mode: Literal["statevector", "measured"] = Field(..., description="Run mode of every task.")
    benchmark_summary: List[SingleCircuitReport] = Field(..., description="One report per task, in task order. A task that failed before dispatch is {task_name, task_qubits, task_request, error}.")
    seed: Optional[int] = Field(None, description="Measured mode: the master seed shared by every task.")
    specimens: Optional[Dict[str, Any]] = Field(None, description="The tasks' specimens records combined by backend key.")
    timing_caveats: Optional[List[Dict[str, Any]]] = Field(None, description="The tasks' report-level timing caveats combined by code.")
    run_completeness: Optional[Dict[str, Any]] = Field(None, description="job_status, planned_tasks, recorded_tasks, tasks_with_results, stopped_early, reason.")


class ExperimentResults(_Open):
    """``results`` of a finished POST /experiments job; the per-circuit data is in the bundle."""
    experiment_summary: Dict[str, Any] = Field(..., description="label, mode, axes, seeds, resolved circuits and runners, conformance, prevalence, sdk_versions, error_count, cells, bundle_name, job_id. Download the bundle with GET /experiments/{job_id}/bundle.")


class JobReport(RootModel[Union[SingleCircuitReport, BatchReport]]):
    """GET /jobs/{job_id}/report: the untruncated report itself (not wrapped in a job
    envelope). A single-circuit report, or a batch report when it has benchmark_summary."""


class SavedRunReport(RootModel[Union[SingleCircuitReport, BatchReport]]):
    """GET /history/runs/{run_id}: the stored report with run_id, run_name and created_at
    added at the top level. Statevectors are replaced by statevector_sha256 and
    statevector_length, and statevector_storage is "removed_before_storage"; saved_from is
    "server_job" or "upload"."""


class JobStatus(JobStatusResponse):
    """GET /jobs/{job_id}."""
    saves: Optional[Dict[str, Dict[str, Any]]] = Field(None, description="Save requests for this job's report and crate (keys report, crate), each with gate_busy_refusals (gated requests answered 409 gate_busy), first_refused_at, gated_admitted_at, deferred_sec (from the first refusal to admission), ungated_requests and ungated_with_dispatches_in_flight (ungated requests that started while a dispatch was in flight); null before any.")
    results: Optional[Union[SingleCircuitReport, BatchReport, ExperimentResults]] = Field(None, description="The report (display copy), once status is 'completed', and for a failed job that reached the runners. Statevectors over 14 qubits are replaced by a placeholder (statevector_omitted_for_display); GET /jobs/{job_id}/report returns the full report.")


class PairVerdictEntry(PairVerdict):
    """One entry of ``pair_verdicts``: a pair's verdict with its two result keys."""
    simulators: Any = Field(None, description="The pair's simulators, as recorded.")


_OUTCOMES_DESCRIPTION = ("Outcome name -> count: each pair under its verdict, no_comparison (1 when no pair was "
                         "compared), runs_without_output (runs whose status is not ok, plus 1 for a circuit "
                         "that failed before any runner ran). outcome_roles gives each name's role.")


class TaskSummary(_Open):
    """Verdicts of one circuit's report."""
    report_analysis_version: Optional[str] = Field(None, description="The analysis version the report records (null for reports that record none).")
    pair_verdicts: List[PairVerdictEntry] = Field(..., description="One per pair record, in pairwise_agreement order.")
    backend_verdicts: BackendVerdicts
    outcomes: Dict[str, int] = Field(..., description=_OUTCOMES_DESCRIPTION)
    runs: Dict[str, Any] = Field(..., description="total, returned (status ok), without_output, and circuit_failed (the circuit never reached a runner).")


class ReportSummary(_Open):
    """GET /jobs/{job_id}/summary, GET /history/runs/{run_id}/summary and POST /summary."""
    analysis_version: str = Field(..., description="This server's analysis version: the rule the verdicts were computed with.")
    report_source: Literal["server_job", "saved_run", "client_supplied"] = Field(..., description="Where the report came from.")
    saved_from: Optional[str] = Field(None, description="Saved runs: the stored report's saved_from (server_job or upload).")
    report_analysis_version: Optional[str] = Field(None, description="Single-circuit report: the analysis version it records.")
    pair_verdicts: Optional[List[PairVerdictEntry]] = Field(None, description="Single-circuit report: one per pair record, in pairwise_agreement order.")
    backend_verdicts: Optional[BackendVerdicts] = Field(None, description="Single-circuit report: per-backend counts.")
    outcomes: Dict[str, int] = Field(..., description=_OUTCOMES_DESCRIPTION + " A playlist's are the sums over its tasks.")
    outcome_roles: Dict[str, Literal["difference", "not_established", "runs_without_output", "agreement"]] = Field(..., description="Each outcome name's role: difference (a pair differs; BY-only included), not_established (inconclusive, not comparable, unassessed, or nothing compared), runs_without_output, agreement.")
    runs: Optional[Dict[str, Any]] = Field(None, description="Runs: total, returned, without_output; a playlist's are sums, with circuits_failed.")
    benchmark_summary: Optional[List[TaskSummary]] = Field(None, description="Playlist report: one summary per task, in task order; null for a single-circuit report.")
