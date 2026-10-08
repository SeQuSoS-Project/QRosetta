"""Background job lifecycle: single-circuit runs, batch suites, and their stored reports.

``ACTIVE_JOBS[job_id]`` holds ``results`` (the copy served to the browser, with oversized
statevectors replaced by a placeholder) and ``full_results`` (the untruncated report, on
disk, served by ``GET /jobs/{job_id}/report`` and exported by ``POST /jobs/{job_id}/export``).
A batch writes each task's full report to disk as the task finishes, so memory holds one
task's report at a time. Both copies are evicted together (``expired_job_ids``).
"""

import asyncio
import random
import time
from fastapi import HTTPException
from services.availability import filter_available
from services.compilation import compile_circuit, queue_compile_statuses
from services.job_store import JOB_NOT_FOUND, JobTable, full_report, spill_task_report
from services.run_registry import EXCLUSIVE, circuit_section, claim_exclusive, releases_exclusive
from services.validator import validate_request
from services.dispatcher import (
    STATEVECTOR_RUNNER_URLS,
    NATIVE_SAMPLING_URLS,
    SAMPLED_SV_URLS,
    SEED_DERIVATION,
    EXECUTION_MODE,
    annotate_overlaps,
    dispatch_to_runners,
    effective_phases,
    expand_runner_jobs,
    timeout_scope,
    utc_now_iso,
)
from schemas import AgreementThresholds, BatchPayload
from config import settings, server_git_sha, server_image_digests, runner_registry_snapshot
from services.aggregator import compile_comparison_reports, compile_measurement_reports
import services.analysis as analysis
from qrosetta_commons.helpers import TIMING_STATISTIC, get_logger, get_num_qubits_from_qasm
from qrosetta_commons.qasm_expressions import tket_parameter_note
from services.circuit_resolver import (
    resolve_circuit_qasm,
    prepare_measured_dispatch,
    prepare_statevector_dispatch,
)

logger = get_logger("rosetta-job-manager")

ACTIVE_JOBS = JobTable()

SEED_MAX = 2**31 - 1

JOB_TTL_SEC = 1800

_MAX_DISPLAY_STATEVECTOR_AMPLITUDES = 16384
_MAX_DISPLAY_STATEVECTOR_B64_CHARS = _MAX_DISPLAY_STATEVECTOR_AMPLITUDES * 16 * 4 // 3
_STATEVECTOR_PLACEHOLDER = (
    "<Statevector too large for display. The full vector is kept on the server with this job "
    "and returned by GET /jobs/{job_id}/report and POST /jobs/{job_id}/export "
    "(include_statevectors=true) until the job expires; it is not in this copy.>"
)


def effective_thresholds(thresholds) -> dict:
    """The agreement thresholds a run uses: the caller's (dict or model), else the defaults."""
    if thresholds is None:
        return AgreementThresholds().model_dump()
    if isinstance(thresholds, AgreementThresholds):
        return thresholds.model_dump()
    return dict(thresholds)


def clamp_timeout(timeout_seconds: int) -> int:
    """Per-runner budget: the request's value bounded to [MIN_TIMEOUT_SEC, RUNNER_TIMEOUT_SEC]."""
    return max(settings.MIN_TIMEOUT_SEC, min(int(timeout_seconds), settings.RUNNER_TIMEOUT_SEC))


def _resolve_seed(seed):
    """The caller's seed, or a generated one when it is None."""
    return seed if seed is not None else random.randint(0, SEED_MAX)


def _display_result(result):
    """Copy of a runner result for the browser: a statevector over
    ``_MAX_DISPLAY_STATEVECTOR_AMPLITUDES`` amplitudes (Base64 or list form) is replaced by
    ``_STATEVECTOR_PLACEHOLDER`` and ``statevector_omitted_for_display`` is set."""
    if not isinstance(result, dict):
        return result
    sv = result.get("statevector")
    too_large = (
        (isinstance(sv, str) and len(sv) > _MAX_DISPLAY_STATEVECTOR_B64_CHARS)
        or (isinstance(sv, list) and len(sv) > _MAX_DISPLAY_STATEVECTOR_AMPLITUDES)
    )
    if too_large:
        return {**result, "statevector": _STATEVECTOR_PLACEHOLDER,
                "statevector_omitted_for_display": True}
    return result


def display_report(report: dict) -> dict:
    """Browser copy of a single-circuit or batch report (see ``_display_result``)."""
    if not isinstance(report, dict):
        return report
    out = dict(report)
    if isinstance(report.get("raw_results"), list):
        out["raw_results"] = [_display_result(r) for r in report["raw_results"]]
    if isinstance(report.get("benchmark_summary"), list):
        out["benchmark_summary"] = [display_report(t) for t in report["benchmark_summary"]]
    return out


def _run_context(optimization_level, runner_config, timeout_seconds, apply_preprocessing,
                 thresholds, runner_phases, bypass_limits=False, timing_repeats=1) -> dict:
    """Run-time configuration recorded at the top level of every report."""
    context = {
        "execution_mode": EXECUTION_MODE,
        "platform_version": settings.PLATFORM_VERSION,
        "git_sha": server_git_sha(),
        "image_digests": server_image_digests() or "not recorded (QROSETTA_IMAGE_DIGESTS unset)",
        "apply_preprocessing": apply_preprocessing,
        "optimization_level": optimization_level,
        "runner_config": runner_config or {},
        "runner_phases": runner_phases or {},
        "timeout_seconds": timeout_seconds,
        "timing_repeats": timing_repeats,
        "timing_statistic": TIMING_STATISTIC,
        "queue_max_wait_sec": settings.RUNNER_QUEUE_MAX_WAIT_SEC,
        "k8s_job_slots": settings.K8S_MAX_CONCURRENT_JOBS if EXECUTION_MODE == "kubernetes" else None,
        "timeout_scope": timeout_scope(),
        "agreement_thresholds": thresholds,
        "bypass_limits": bool(bypass_limits),
        "exclusive": bool(EXCLUSIVE.get()),
        "runner_registry": runner_registry_snapshot(),
    }
    analysis_version = getattr(analysis, "ANALYSIS_VERSION", None)
    if analysis_version is not None:
        context["analysis_version"] = analysis_version
    return context


def resolved_runners(target_simulators, dispatched_urls: dict, skipped: list) -> dict:
    """The runner set a report covers: the request's ids, the ids actually dispatched, and
    the ids left out with their reasons."""
    return {"requested": list(target_simulators or []),
            "dispatched": sorted(dispatched_urls),
            "skipped": list(skipped)}


_TKET_RUNNERS = frozenset(cid for cid, svc in settings.get_runner_services().items()
                          if svc.get("builds_with_tket"))


def _apply_api_preprocessing(results: list, group: str, circuit: dict) -> None:
    """Prepend the API-side transforms to each result's ``preprocessing_applied``, record
    which dispatched circuit it received, and, for a runner that builds its circuit with
    tket, append the gate parameters tket moves in the dispatched text (none after the
    pytket round-trip, which has already moved them)."""
    tket_note = None
    if any(isinstance(r, dict) and str(r.get("simulator", "")).split("~", 1)[0] in _TKET_RUNNERS
           for r in results):
        tket_note = tket_parameter_note(circuit["qasm"], "tket, which builds this backend's circuit,")
    for result in results:
        if not isinstance(result, dict):
            continue
        result["dispatch_group"] = group
        notes = circuit["api_preprocessing_applied"]
        if notes:
            result["preprocessing_applied"] = list(notes) + list(result.get("preprocessing_applied") or [])
        if tket_note and str(result.get("simulator", "")).split("~", 1)[0] in _TKET_RUNNERS:
            result["preprocessing_applied"] = list(result.get("preprocessing_applied") or []) + [tket_note]


def _dispatched_circuit_record(group: str, circuit: dict, results: list) -> dict:
    return {
        "group": group,
        "qasm": circuit["qasm"],
        "api_preprocessing_applied": list(circuit["api_preprocessing_applied"]),
        "runners": [r.get("simulator") for r in results if isinstance(r, dict)],
    }


async def run_single_circuit_comparison(qasm_string: str, optimization_level: int = 0, runner_config: dict = None, timeout_seconds: int = settings.DEFAULT_TIMEOUT_SEC, target_simulators: list = None, runner_statuses: dict = None, runner_phases: dict = None, apply_preprocessing: bool = True, thresholds: dict = None, bypass_limits: bool = False, timing_repeats: int = 1, exclusive: bool = False, compilers: dict = None):
    """Run one circuit on the statevector fleet, then any requested compilers, and return
    the full (untruncated) report."""
    started_at = utc_now_iso()
    thresholds = effective_thresholds(thresholds)
    context = _run_context(optimization_level, runner_config, timeout_seconds,
                           apply_preprocessing, thresholds, runner_phases, bypass_limits,
                           timing_repeats)
    try:
        circuit = await asyncio.to_thread(prepare_statevector_dispatch, qasm_string, apply_preprocessing)
    except Exception as e:
        return {"input_qasm": qasm_string, "error": str(e), **context}

    queue_compile_statuses(runner_statuses, compilers)
    runner_payload = {
        "circuit_data": circuit["qasm"],
        "optimization_level": optimization_level,
        "runner_config": runner_config or {},
        "runner_phases": runner_phases or {},
        "apply_preprocessing": apply_preprocessing,
        "timing_repeats": timing_repeats,
    }

    if target_simulators:
        filtered_urls = {k: v for k, v in STATEVECTOR_RUNNER_URLS.items() if k in target_simulators}
    else:
        filtered_urls = STATEVECTOR_RUNNER_URLS
    filtered_urls, skipped = await filter_available(filtered_urls, target_simulators)

    _queue_for_exclusive(runner_statuses, filtered_urls)
    async with circuit_section(settings.EXCLUSIVE_MAX_WAIT_SEC):
        aggregated_results = await dispatch_to_runners(
            runner_urls=filtered_urls,
            runner_payload=runner_payload,
            timeout_seconds=timeout_seconds,
            runner_statuses=runner_statuses,
        )
    _apply_api_preprocessing(aggregated_results, "statevector", circuit)
    compiled = await compile_circuit(qasm_string, apply_preprocessing, compilers, timeout_seconds,
                                     runner_statuses, prepared=circuit)

    try:
        divergence_report, performance_report, resource_report = await compile_comparison_reports(aggregated_results, thresholds)
    except Exception as e:
        logger.warning(f"Analysis failed (returning raw results only): {e}")
        divergence_report = {"error": f"Analysis failed: {e}"}
        performance_report = {}
        resource_report = {}

    return {
        "input_qasm": qasm_string,
        **context,
        "api_preprocessing_applied": list(circuit["api_preprocessing_applied"]),
        "dispatched_circuits": [_dispatched_circuit_record("statevector", circuit, aggregated_results)],
        **compiled,
        "resolved_runners": resolved_runners(target_simulators, filtered_urls, skipped),
        "skipped_runners": skipped,
        "effective_runner_phases": phase_plan(aggregated_results),
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "divergence_report": divergence_report,
        "performance_report": performance_report,
        "resource_report": resource_report,
        "raw_results": aggregated_results,
    }


async def run_compile_only(qasm_string: str, optimization_level: int = 0, timeout_seconds: int = settings.DEFAULT_TIMEOUT_SEC, runner_statuses: dict = None, apply_preprocessing: bool = True, thresholds: dict = None, bypass_limits: bool = False, compilers: dict = None):
    """Run only the requested compile-only services on one circuit; no simulator is
    dispatched, so the report has no simulator results and records ``simulated: False``."""
    started_at = utc_now_iso()
    context = _run_context(optimization_level, {}, timeout_seconds, apply_preprocessing,
                           effective_thresholds(thresholds), {}, bypass_limits, 1)
    queue_compile_statuses(runner_statuses, compilers)
    compiled = await compile_circuit(qasm_string, apply_preprocessing, compilers, timeout_seconds, runner_statuses)
    return {
        "input_qasm": qasm_string,
        **context,
        "simulated": False,
        **compiled,
        "resolved_runners": resolved_runners([], {}, []),
        "skipped_runners": [],
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "divergence_report": {},
        "performance_report": {},
        "resource_report": {},
        "raw_results": [],
    }


async def run_single_circuit_measurement(qasm_string: str, n_shots: int, optimization_level: int = 0, runner_config: dict = None, timeout_seconds: int = settings.DEFAULT_TIMEOUT_SEC, target_simulators: list = None, runner_statuses: dict = None, runner_phases: dict = None, apply_preprocessing: bool = True, seed: int = None, thresholds: dict = None, bypass_limits: bool = False, timing_repeats: int = 1, exclusive: bool = False, compilers: dict = None):
    """Run one circuit on the sampling fleet, then any requested compilers, and return the
    full report.

    ``seed`` is the master seed (generated when None); each runner receives a seed
    derived from it and its result key.
    """
    started_at = utc_now_iso()
    seed = _resolve_seed(seed)
    thresholds = effective_thresholds(thresholds)
    logger.info(f"Processing measured circuit for {n_shots} shots (seed={seed})...")
    context = _run_context(optimization_level, runner_config, timeout_seconds,
                           apply_preprocessing, thresholds, runner_phases, bypass_limits,
                           timing_repeats)
    seed_fields = {"n_shots": n_shots, "seed": seed, "seed_derivation": SEED_DERIVATION}

    try:
        circuits = await asyncio.to_thread(prepare_measured_dispatch, qasm_string, apply_preprocessing)
    except Exception as e:
        return {"input_qasm": qasm_string, **seed_fields, **context, "error": str(e)}

    queue_compile_statuses(runner_statuses, compilers)

    def payload_for(group):
        return {
            "circuit_data": circuits[group]["qasm"],
            "n_shots": n_shots,
            "optimization_level": optimization_level,
            "runner_config": runner_config or {},
            "runner_phases": runner_phases or {},
            "apply_preprocessing": apply_preprocessing,
            "seed": seed,
            "timing_repeats": timing_repeats,
        }

    if target_simulators:
        filtered_sampled = {k: v for k, v in SAMPLED_SV_URLS.items() if k in target_simulators}
        filtered_native = {k: v for k, v in NATIVE_SAMPLING_URLS.items() if k in target_simulators}
    else:
        filtered_sampled = SAMPLED_SV_URLS
        filtered_native = NATIVE_SAMPLING_URLS
    filtered_sampled, skipped_sampled = await filter_available(filtered_sampled, target_simulators)
    filtered_native, skipped_native = await filter_available(filtered_native, target_simulators)

    _queue_for_exclusive(runner_statuses, {**filtered_sampled, **filtered_native})
    async with circuit_section(settings.EXCLUSIVE_MAX_WAIT_SEC):
        results_sampled, results_native = await _dispatch_groups_by_phase(
            [(filtered_sampled, payload_for("measured_sampled")),
             (filtered_native, payload_for("measured_native"))],
            runner_phases, timeout_seconds, runner_statuses)
    annotate_overlaps(results_sampled + results_native)
    _apply_api_preprocessing(results_sampled, "measured_sampled", circuits["measured_sampled"])
    _apply_api_preprocessing(results_native, "measured_native", circuits["measured_native"])
    aggregated_results = results_native + results_sampled
    compiled = await compile_circuit(qasm_string, apply_preprocessing, compilers, timeout_seconds, runner_statuses)

    api_notes = []
    for group in ("measured_native", "measured_sampled"):
        api_notes += [f"{note} [{group} runners]" for note in circuits[group]["api_preprocessing_applied"]]

    report = {
        "input_qasm": qasm_string,
        **seed_fields,
        **context,
        "api_preprocessing_applied": api_notes,
        "dispatched_circuits": [
            _dispatched_circuit_record("measured_native", circuits["measured_native"], results_native),
            _dispatched_circuit_record("measured_sampled", circuits["measured_sampled"], results_sampled),
        ],
        **compiled,
        "resolved_runners": resolved_runners(
            target_simulators, {**filtered_native, **filtered_sampled},
            skipped_native + skipped_sampled),
        "skipped_runners": skipped_native + skipped_sampled,
        "effective_runner_phases": phase_plan(aggregated_results),
        "started_at": started_at,
    }

    try:
        divergence_report, performance_report, resource_report = await compile_measurement_reports(aggregated_results, n_shots, thresholds)
    except Exception as e:
        report.update({"finished_at": utc_now_iso(), "error": f"Error during comparison: {str(e)}",
                       "raw_results": aggregated_results})
        return report

    report.update({
        "finished_at": utc_now_iso(),
        "divergence_report": divergence_report,
        "performance_report": performance_report,
        "resource_report": resource_report,
        "raw_results": aggregated_results,
    })
    return report


def job_targets(requested_target: str = None) -> dict:
    """``target`` (the execution mode runs are dispatched with) and ``requested_target``
    (the value the request carried)."""
    targets = {"target": EXECUTION_MODE}
    if requested_target:
        targets["requested_target"] = requested_target
    return targets


def new_job(requested_target: str = None, owner_user_id: int = None) -> dict:
    """ACTIVE_JOBS entry for a job that has been accepted but not started. ``owner_user_id``
    is the signed-in account that submitted it (None for an anonymous submission)."""
    return {"status": "pending", **job_targets(requested_target), "owner_user_id": owner_user_id,
            "submitted_at": time.time()}


def start_job(job_id: str, runner_statuses: dict) -> None:
    """Mark a job as processing and record the asyncio task running it."""
    job = ACTIVE_JOBS[job_id]
    job["status"] = "processing"
    job["runner_statuses"] = runner_statuses
    job["worker"] = asyncio.current_task()


def expired_job_ids(now: float = None, ttl: float = JOB_TTL_SEC) -> list:
    """Jobs to evict: finished more than ``ttl`` ago, or submitted more than ``ttl`` ago and
    unfinished with no task running them (a worker that died). A job whose worker is still
    running is never evicted."""
    cutoff = (time.time() if now is None else now) - ttl
    expired = []
    for job_id, job in list(ACTIVE_JOBS.items()):
        if not isinstance(job, dict):
            continue
        if job.get("status") in ("completed", "failed"):
            if job.get("finished_at", 0) < cutoff:
                expired.append(job_id)
            continue
        worker = job.get("worker")
        if (worker is None or worker.done()) and job.get("submitted_at", 0) < cutoff:
            expired.append(job_id)
    return expired


def _completed_job(target: str, full_report: dict, runner_statuses: dict, results: dict = None,
                   **extra) -> dict:
    """A completed job; ``results`` is the browser copy (``display_report(full_report)`` when
    not given)."""
    return {"status": "completed", **job_targets(target),
            "results": display_report(full_report) if results is None else results,
            "full_results": full_report, "runner_statuses": runner_statuses,
            "finished_at": time.time(), **extra}


def _failed_job(target: str, error: str, runner_statuses: dict, report: dict = None,
                keep_full: bool = False, results: dict = None, **extra) -> dict:
    """A failed job. ``report`` (when any) is served in ``results`` (or the browser copy
    given as ``results``); with ``keep_full`` the untruncated copy is kept too, so a report
    that reached the runners stays exportable."""
    job = {"status": "failed", **job_targets(target), "error": error,
           "runner_statuses": runner_statuses, "finished_at": time.time(), **extra}
    if report is not None:
        job["results"] = display_report(report) if results is None else results
        if keep_full:
            job["full_results"] = report
    return job


async def _dispatch_groups_by_phase(groups: list, runner_phases: dict, timeout_seconds,
                                    runner_statuses) -> list:
    """Dispatch several runner groups of one circuit (``[(urls, payload)]``) under one phase
    plan (``effective_phases`` over every group's runners): phase p of every group runs
    together, after phase p-1 of every group has finished. Returns each group's results."""
    plan = effective_phases([name for urls, _ in groups for name in urls], runner_phases,
                            bool(EXCLUSIVE.get()))
    phases = sorted(set(plan.values()))
    if runner_statuses is not None and len(phases) > 1:
        for urls, payload in groups:
            later = {n: u for n, u in urls.items() if plan[n] != phases[0]}
            for spec in expand_runner_jobs(later, payload):
                runner_statuses.setdefault(spec["key"], "queued")
    results = [[] for _ in groups]
    for phase in phases:
        calls = [(i, {n: u for n, u in urls.items() if plan[n] == phase}, payload)
                 for i, (urls, payload) in enumerate(groups)]
        calls = [(i, urls, {**payload, "runner_phases": plan}) for i, urls, payload in calls if urls]
        batches = await asyncio.gather(*(dispatch_to_runners(urls, payload, timeout_seconds, runner_statuses)
                                         for _, urls, payload in calls))
        for (i, _, _), batch in zip(calls, batches):
            results[i].extend(batch)
    return results


def phase_plan(results: list) -> dict:
    """Result key -> the dispatch phase it ran in."""
    return {r["simulator"]: r.get("dispatch_phase", 1) for r in results
            if isinstance(r, dict) and r.get("simulator")}


def _queue_for_exclusive(runner_statuses, urls) -> None:
    """Show an exclusive job's runners as queued while it waits for the server to be idle."""
    if EXCLUSIVE.get() and runner_statuses is not None:
        for name in urls:
            runner_statuses.setdefault(name, "queued")


def require_exclusive_slot(payload, client: str, job_id: str) -> None:
    """For an exclusive request: 400 when the server disables exclusive runs, 429 when this
    client already has an exclusive job that has not finished."""
    if not getattr(payload, "exclusive", False):
        return
    if not settings.EXCLUSIVE_ENABLED:
        raise HTTPException(status_code=400, detail="Exclusive runs are disabled on this server.")
    held = claim_exclusive(client, job_id)
    if held is not None:
        raise HTTPException(status_code=429, detail=(
            f"You already have an exclusive job ({held}) that has not finished; one exclusive "
            f"job per client runs at a time."))


def report_failed_before_dispatch(report: dict) -> bool:
    """True for a report whose circuit never reached a runner (top-level error, no results)."""
    return isinstance(report, dict) and bool(report.get("error")) and "raw_results" not in report


def all_runners_failed(report: dict):
    """``"all N runners failed"`` when a dispatched report has results and none succeeded;
    for a compile-only report (``simulated: False``), ``"all N compiles failed"`` when no
    compile produced a circuit (errors, refusals and skips alike); else None."""
    if isinstance(report, dict) and report.get("simulated") is False:
        compiles = report.get("compiled_circuits") or []
        if compiles and not any(isinstance(c, dict) and not c.get("error") for c in compiles):
            return f"all {len(compiles)} compiles failed"
        return None
    results = report.get("raw_results") if isinstance(report, dict) else None
    if not results:
        return None
    if any(isinstance(r, dict) and not r.get("error") for r in results):
        return None
    return f"all {len(results)} runners failed"


_SOURCE_TAGS = {"mqt": "MQT Bench", "qasmbench": "QASMBench"}


def task_label(algorithm, qubits: int, source: str = None) -> str:
    """``"<name> (<n>q)"``, plus ``" [MQT Bench]"`` or ``" [QASMBench]"`` for a bundled
    benchmark circuit so it is not mistaken for a preset of the same name. A name already
    ending in ``(<n>q)`` keeps it; an unknown qubit count (0 or None) adds no count."""
    name = str(algorithm or "circuit").strip()
    if qubits:
        suffix = f"({qubits}q)"
        name = name if name.endswith(suffix) else f"{name} {suffix}"
    tag = _SOURCE_TAGS.get(source)
    return f"{name} [{tag}]" if tag else name


def task_qubits(task, qasm_string: str = None) -> int:
    """Qubit count of a task: read from its QASM when available, else the declared field."""
    text = qasm_string or getattr(task, "qasm_string", None)
    if text:
        n = get_num_qubits_from_qasm(text)
        if n:
            return n
    return int(getattr(task, "qubits", 0) or 0)


def is_user_circuit(task) -> bool:
    """True for a task whose QASM the caller supplied (not a preset or bundled circuit)."""
    return bool(getattr(task, "qasm_string", None)) and getattr(task, "source", None) in (None, "qasm")


def task_request(task) -> dict:
    """How a batch task asked for its circuit: ``source`` (as resolved: 'qasm' for literal
    text, 'preset' when unset), ``algorithm``, ``qubits`` as sent, ``literal_qasm``, and ``name`` when the task had one."""
    literal = bool(getattr(task, "qasm_string", None))
    source = getattr(task, "source", None)
    request = {"source": "qasm" if literal else (source or "preset"),
               "algorithm": getattr(task, "algorithm", None),
               "qubits": getattr(task, "qubits", None),
               "literal_qasm": literal}
    if getattr(task, "name", None):
        request["name"] = task.name
    return request


def experiment_report_detail(job_id: str) -> str:
    return (f"This is an experiment job; it has no single report. Download its bundle with "
            f"GET /experiments/{job_id}/bundle.")


def is_experiment_job(job: dict) -> bool:
    return job.get("kind") == "experiment" or "bundle_path" in job


def finished_job_or_error(job_id: str, action: str) -> dict:
    """The ACTIVE_JOBS entry of a finished job that has a report; raises 404 for an unknown
    job and 409 for an experiment job, an unfinished job, or a job with no report (failed
    before dispatch)."""
    job = ACTIVE_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=JOB_NOT_FOUND)
    if is_experiment_job(job):
        raise HTTPException(status_code=409, detail=experiment_report_detail(job_id))
    if job.get("status") not in ("completed", "failed"):
        raise HTTPException(status_code=409, detail=f"The job has not finished yet (status: {job.get('status')}); poll GET /jobs/{job_id}.")
    if not job.get("full_results"):
        raise HTTPException(status_code=409, detail=f"This job failed before any runner ran and has no report to {action}: {job.get('error')}")
    return job


def job_with_report_or_error(job_id: str, action: str, each_task=None) -> tuple:
    """``(job, full report)`` of a finished job, with the errors of ``finished_job_or_error``
    and 404 when the job expires while its report is read. ``each_task`` as in
    ``job_store.full_report``."""
    job = finished_job_or_error(job_id, action)
    try:
        return job, full_report(job, each_task)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=JOB_NOT_FOUND)


def job_report_or_error(job_id: str, action: str) -> dict:
    """The server's full report of ``job_id`` (see ``job_with_report_or_error``)."""
    return job_with_report_or_error(job_id, action)[1]


def internal_error_message(kind: str, exc: Exception) -> str:
    """Client-facing error for a job whose worker raised: the exception type, no detail."""
    return (f"The {kind} stopped on an internal error ({type(exc).__name__}); its results were "
            f"not kept. Submit it again.")


async def _run_single_job(job_id: str, execution_target: str, runner_statuses: dict, run_coro):
    """Await ``run_coro`` (a run_single_* coroutine) and record the terminal state.

    A report that failed before dispatch (e.g. the circuit does not parse) is ``failed``;
    so is one where every runner returned an error, which keeps its report.
    """
    start_job(job_id, runner_statuses)
    try:
        report = await run_coro
        every_runner_failed = all_runners_failed(report)
        if report_failed_before_dispatch(report):
            job = _failed_job(execution_target, str(report["error"]), runner_statuses, report)
        elif every_runner_failed:
            job = _failed_job(execution_target, every_runner_failed, runner_statuses, report,
                              keep_full=True)
        else:
            job = _completed_job(execution_target, report, runner_statuses)
        await ACTIVE_JOBS.store(job_id, job)
    except Exception as e:
        logger.error(f"Job {job_id} failed", exc_info=True)
        ACTIVE_JOBS[job_id] = _failed_job(execution_target, str(e), runner_statuses)


@releases_exclusive
async def worker_compare(job_id: str, qasm_string: str, optimization_level: int, runner_config: dict, timeout: int, target_simulators: list, execution_target: str, runner_phases: dict = None, apply_preprocessing: bool = True, thresholds: dict = None, bypass_limits: bool = False, timing_repeats: int = 1, exclusive: bool = False, compilers: dict = None, simulate: bool = True):
    """Background task for POST /compare."""
    EXCLUSIVE.set(exclusive)
    runner_statuses = {}
    run = (run_single_circuit_comparison(qasm_string, optimization_level, runner_config, timeout, target_simulators, runner_statuses, runner_phases, apply_preprocessing, thresholds, bypass_limits, timing_repeats, compilers=compilers)
           if simulate else
           run_compile_only(qasm_string, optimization_level, timeout, runner_statuses, apply_preprocessing, thresholds, bypass_limits, compilers))
    await _run_single_job(job_id, execution_target, runner_statuses, run)


@releases_exclusive
async def worker_compare_measured(job_id: str, qasm_string: str, n_shots: int, optimization_level: int, runner_config: dict, timeout: int, target_simulators: list, execution_target: str, runner_phases: dict = None, apply_preprocessing: bool = True, seed: int = None, thresholds: dict = None, bypass_limits: bool = False, timing_repeats: int = 1, exclusive: bool = False, compilers: dict = None):
    """Background task for POST /compare_measured."""
    EXCLUSIVE.set(exclusive)
    runner_statuses = {}
    await _run_single_job(job_id, execution_target, runner_statuses,
        run_single_circuit_measurement(qasm_string, n_shots, optimization_level, runner_config, timeout, target_simulators, runner_statuses, runner_phases, apply_preprocessing, seed, thresholds, bypass_limits, timing_repeats, compilers=compilers))


async def run_batch_tasks(payload: BatchPayload, runner_statuses: dict, progress: dict = None,
                          batch_seed: int = None, task_offset: int = 0, store=None) -> tuple:
    """Run every task in a BatchPayload sequentially; return (benchmark_summary, batch_seed).

    Shared by ``worker_batch_suite`` and ``services.experiment.worker_experiment``. Each
    entry of ``benchmark_summary`` is a full, untruncated report, or what ``store`` returned
    for it.

    * ``progress`` — when supplied, mutated per task ({total, completed, current_index,
      tasks:[{name,status}]}); ``task_offset`` indexes into a progress list shared by
      several calls.
    * ``batch_seed`` — master seed for every task; resolved here when None.
    * ``store`` — ``async (index, report) -> entry``, called as each task finishes, so the
      caller can write the report out instead of holding every task's report in memory.
    """
    benchmark_summary = []
    batch_thresholds = effective_thresholds(payload.thresholds)
    if batch_seed is None:
        batch_seed = _resolve_seed(payload.seed)

    for idx, task in enumerate(payload.tasks):
        gi = task_offset + idx
        task_name = task_label(task.name or task.algorithm, task_qubits(task), task.source)
        logger.info(f"--- Running task: {task_name} ---")
        if progress is not None:
            progress["current_index"] = gi
            progress["tasks"][gi]["status"] = "running"
        try:
            qasm_string = await asyncio.to_thread(
                resolve_circuit_qasm, task.source, task.algorithm, task.qubits, task.qasm_string,
                mode=payload.mode)
            task_name = task_label(task.name or task.algorithm, task_qubits(task, qasm_string), task.source)
            if progress is not None:
                axis = progress["tasks"][gi].get("axis")
                progress["tasks"][gi]["name"] = task_name + (f" · {axis}" if axis else "")

            simulate = getattr(payload, "simulate", True)
            await asyncio.to_thread(
                validate_request, qasm_string, mode=payload.mode if simulate else "compile",
                bypass_limits=payload.bypass_limits,
                apply_preprocessing=payload.apply_preprocessing,
                check_reserved_names=is_user_circuit(task))
            timeout = clamp_timeout(payload.timeout_seconds)
            if not simulate:
                report = await run_compile_only(qasm_string, payload.optimization_level, timeout, runner_statuses, payload.apply_preprocessing, batch_thresholds, payload.bypass_limits, payload.compilers)
            elif payload.mode == 'statevector':
                report = await run_single_circuit_comparison(qasm_string, payload.optimization_level, payload.runner_config, timeout, payload.target_simulators, runner_statuses, payload.runner_phases, payload.apply_preprocessing, batch_thresholds, payload.bypass_limits, payload.timing_repeats, compilers=payload.compilers)
            elif payload.mode == 'measured':
                report = await run_single_circuit_measurement(qasm_string, payload.n_shots, payload.optimization_level, payload.runner_config, timeout, payload.target_simulators, runner_statuses, payload.runner_phases, payload.apply_preprocessing, batch_seed, batch_thresholds, payload.bypass_limits, payload.timing_repeats, compilers=payload.compilers)
            else:
                raise ValueError(f"Unknown mode: {payload.mode}")

            report["task_name"] = task_name
            report["task_request"] = task_request(task)
            status = ("error" if report_failed_before_dispatch(report) or all_runners_failed(report)
                      else "done")

        except Exception as e:
            reason = e.detail if isinstance(e, HTTPException) else str(e)
            report = {
                "task_name": task_name,
                "task_request": task_request(task),
                "error": f"Failed to process task: {reason}"
            }
            status = "error"

        benchmark_summary.append(await store(idx, report) if store is not None else report)
        del report
        if progress is not None:
            progress["tasks"][gi]["status"] = status
            progress["completed"] += 1

    return benchmark_summary, batch_seed


def _task_outcome(report: dict) -> str:
    if report_failed_before_dispatch(report):
        return "before_dispatch"
    return "no_result" if all_runners_failed(report) else "ok"


@releases_exclusive
async def worker_batch_suite(job_id: str, payload: BatchPayload):
    """Background task for POST /run_batch_suite, with live per-task progress. Each task's
    full report is written to disk as it finishes; the job keeps its browser copy."""
    EXCLUSIVE.set(payload.exclusive)
    runner_statuses = {}
    start_job(job_id, runner_statuses)
    try:
        await _run_batch_suite(job_id, payload, runner_statuses)
    except Exception as e:
        logger.error(f"Batch job {job_id} failed", exc_info=True)
        ACTIVE_JOBS[job_id] = _failed_job(payload.execution_target,
                                          internal_error_message("batch job", e), runner_statuses,
                                          progress=ACTIVE_JOBS.get(job_id, {}).get("progress"))


async def _run_batch_suite(job_id: str, payload: BatchPayload, runner_statuses: dict) -> None:
    logger.info(f"--- Starting Batch Suite ({payload.mode}) with {len(payload.tasks)} tasks ---")
    progress = {
        "total": len(payload.tasks),
        "completed": 0,
        "current_index": None,
        "tasks": [{"name": task_label(t.name or t.algorithm, task_qubits(t), t.source), "status": "queued"}
                  for t in payload.tasks],
    }
    ACTIVE_JOBS[job_id]["progress"] = progress
    displayed, outcomes, errors = [], [], []

    async def store(index: int, report: dict):
        displayed.append(display_report(report))
        outcomes.append(_task_outcome(report))
        errors.append(report.get("error"))
        return await asyncio.to_thread(spill_task_report, job_id, index, report)

    started_at = utc_now_iso()
    benchmark_summary, batch_seed = await run_batch_tasks(payload, runner_statuses, progress,
                                                          store=store)

    progress["current_index"] = None
    logger.info("--- Batch Suite Complete ---")
    full_report = {
        "mode": payload.mode,
        "bypass_limits": payload.bypass_limits,
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "benchmark_summary": benchmark_summary,
    }
    if payload.mode == "measured":
        full_report["seed"] = batch_seed
        full_report["seed_derivation"] = SEED_DERIVATION
    results = {**full_report, "benchmark_summary": displayed}
    target = payload.execution_target
    if outcomes and all(o == "before_dispatch" for o in outcomes):
        job = _failed_job(target, f"All {len(outcomes)} task(s) failed before dispatch; first "
                                  f"error: {errors[0]}",
                          runner_statuses, full_report, results=results, progress=progress)
    elif outcomes and all(o != "ok" for o in outcomes):
        produced = "no runner returned a result" if getattr(payload, "simulate", True) else \
            "no compile produced a circuit"
        job = _failed_job(target, f"All {len(outcomes)} task(s) failed: {produced}",
                          runner_statuses, full_report, keep_full=True, results=results,
                          progress=progress)
    else:
        job = _completed_job(target, full_report, runner_statuses, results=results,
                             progress=progress)
    await ACTIVE_JOBS.store(job_id, job)
