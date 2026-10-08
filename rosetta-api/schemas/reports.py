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


class PairwiseAgreement(_Open):
    """One entry of ``divergence_report.pairwise_agreement``: one pair of runs."""
    simulators: List[str] = Field(..., description="The two result keys compared.")
    mode: Literal["statevector", "measured"] = Field(..., description="Which comparison produced the record.")
    agreement: str = Field(..., description="Statevector mode: the verdict label, e.g. agree_directly, agree_up_to_global_phase, residual_disagreement; the manual's agreement section says which labels are disagreements. Measured mode: a distance label only (JS divergence and Hellinger distance against their thresholds); it ignores shot noise and is not the verdict.")
    measured_assessment: Optional[Literal["consistent_within_shot_noise", "inconclusive_low_shots", "ambiguous", "distinguishable", "not_comparable"]] = Field(None, description="Measured mode only: the verdict. 'distinguishable' is the only disagreement; check marginal_assessment too. A CI check of a measured run reads this field, not agreement.")
    marginal_assessment: Optional[str] = Field(None, description="Measured mode only: the single-bit marginal tests' outcome; a significant one is a disagreement too.")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Distances, fidelities and test statistics behind the labels.")


class DivergenceReport(_Open):
    """Cross-backend agreement of one circuit."""
    simulators: Optional[List[str]] = Field(None, description="Result keys in matrix order.")
    fidelity_matrix: Optional[List[List[Optional[float]]]] = Field(None, description="Statevector mode: pairwise fidelity; null for pairs not compared.")
    pairwise_agreement: Optional[List[PairwiseAgreement]] = Field(None, description="One record per pair of runs.")
    statistical_test_summary: Optional[Dict[str, Any]] = Field(None, description="Measured mode: multiple-testing correction, power, recommended shots and measured_assessment_counts.")
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


class BatchReport(_Open):
    """The report of a playlist (POST /run_batch_suite)."""
    mode: Literal["statevector", "measured"] = Field(..., description="Run mode of every task.")
    benchmark_summary: List[SingleCircuitReport] = Field(..., description="One report per task, in task order. A task that failed before dispatch is {task_name, task_qubits, task_request, error}.")
    seed: Optional[int] = Field(None, description="Measured mode: the master seed shared by every task.")


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
    results: Optional[Union[SingleCircuitReport, BatchReport, ExperimentResults]] = Field(None, description="The report (display copy), once status is 'completed', and for a failed job that reached the runners. Statevectors over 14 qubits are replaced by a placeholder (statevector_omitted_for_display); GET /jobs/{job_id}/report returns the full report.")
