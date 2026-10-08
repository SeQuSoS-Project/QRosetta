"""Benchmark job routes: start single, measured and batch runs; poll and fetch job reports."""

import asyncio

from services.job_manager import require_exclusive_slot
from services.security import client_address, get_optional_user
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
import uuid
from routers.errors import responses
from qrosetta_commons.helpers import get_logger
from services.validator import (
    check_statevector_circuit, validate_request, validate_runner_config, validate_runner_ids,
)
from schemas import QasmPayload, MeasuredQasmPayload, BatchPayload, JobStatusResponse
from schemas.reports import JobReport, JobStatus
from services.security import limiter
from services.availability import require_available
from services.job_store import JOB_NOT_FOUND, file_chunks, report_json_file
from services.compilation import validate_compilers
from config import settings
from services.job_manager import (
    ACTIVE_JOBS,
    finished_job_or_error,
    clamp_timeout,
    effective_thresholds,
    new_job,
    worker_compare,
    worker_compare_measured,
    worker_batch_suite
)

logger = get_logger("rosetta-benchmark-api")
router = APIRouter()


def _job_envelope(job_id: str) -> dict:
    job = ACTIVE_JOBS[job_id]
    return {"job_id": job_id, "status": job["status"], "target": job["target"],
            "requested_target": job.get("requested_target")}

@router.get("/jobs/{job_id}", response_model=None,
            responses={200: {"model": JobStatus, "description": "The job envelope with its status and, once finished, its report."}, **responses(404)})
async def get_job_status(job_id: str):
    """Poll the status of any background job started by /compare, /compare_measured,
    /run_batch_suite, or /experiments. 404 if the job id is unknown."""
    if job_id not in ACTIVE_JOBS:
        raise HTTPException(status_code=404, detail=JOB_NOT_FOUND)

    job_data = ACTIVE_JOBS[job_id]
    return {
        "job_id": job_id,
        "status": job_data["status"],
        "target": job_data["target"],
        "requested_target": job_data.get("requested_target"),
        "results": job_data.get("results"),
        "error": job_data.get("error"),
        "runner_statuses": job_data.get("runner_statuses"),
        "progress": job_data.get("progress"),
    }

def _report_file(job_id: str):
    """The job's full report as an open JSON file; 404 when the job expires meanwhile."""
    job = finished_job_or_error(job_id, "download")
    try:
        return report_json_file(job)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=JOB_NOT_FOUND)


@router.get("/jobs/{job_id}/report", responses={
    200: {"model": JobReport, "description": "The report itself as a JSON attachment (no job envelope)."},
    **responses(404, (409, "The job has not finished, failed before any runner ran, or is an experiment."))})
@limiter.limit("30/minute")
async def get_job_full_report(request: Request, job_id: str):
    """Download the untruncated report of a finished /compare, /compare_measured or
    /run_batch_suite job as JSON, including statevectors that GET /jobs/{job_id} replaces
    with a placeholder. A job whose runners all failed is 'failed' but still has a report.
    404 if the job id is unknown or expired; 409 if the job has not finished, failed before
    any runner ran, or is an experiment (use GET /experiments/{job_id}/bundle)."""
    fh = await asyncio.to_thread(_report_file, job_id)
    return StreamingResponse(
        file_chunks(fh), media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="qrosetta_report_{job_id[:8]}.json"'},
    )

@router.post("/compare", response_model=JobStatusResponse, responses=responses(400, 413, 422))
@limiter.limit(settings.RUN_RATE_LIMIT)
async def compare_circuits_endpoint(request: Request, payload: QasmPayload, background_tasks: BackgroundTasks, user=Depends(get_optional_user)):
    """Dispatch one OpenQASM 2.0 circuit for an exact statevector comparison across the
    simulator fleet. Runs in the background; poll GET /jobs/{job_id} for the result, which
    includes the fidelity/phase agreement matrices, per-backend performance/resource data, and
    the explained-cause pairwise agreement classification. 400 for a circuit that does not
    parse as OpenQASM 2.0, has too many qubits, or has mid-circuit measurement, reset or
    classical control, and for unknown, disabled or unavailable runner ids; 413 for a
    circuit over MAX_QASM_SIZE. 400 also for a gate definition under a name a runner's
    parser reserves, and a runner_config level above that runner's max."""
    validate_request(payload.qasm_string, mode="statevector" if payload.simulate else "compile",
                     bypass_limits=payload.bypass_limits, apply_preprocessing=payload.apply_preprocessing)
    if payload.simulate:
        check_statevector_circuit(payload.qasm_string)
    validate_runner_ids(payload.target_simulators, payload.runner_config, payload.runner_phases)
    validate_runner_config(payload.runner_config)
    validate_compilers(payload.compilers)
    await require_available(payload.target_simulators)
    timeout = clamp_timeout(payload.timeout_seconds)
    job_id = str(uuid.uuid4())
    require_exclusive_slot(payload, client_address(request), job_id)

    ACTIVE_JOBS[job_id] = new_job(payload.execution_target, user.id if user else None)
    thresholds = effective_thresholds(payload.thresholds)
    background_tasks.add_task(worker_compare, job_id, payload.qasm_string, payload.optimization_level, payload.runner_config, timeout, payload.target_simulators, payload.execution_target, payload.runner_phases, payload.apply_preprocessing, thresholds, payload.bypass_limits, payload.timing_repeats, exclusive=payload.exclusive, compilers=payload.compilers, simulate=payload.simulate)

    return _job_envelope(job_id)

@router.post("/compare_measured", response_model=JobStatusResponse, responses=responses(400, 413, 422))
@limiter.limit(settings.RUN_RATE_LIMIT)
async def compare_measured_circuits_endpoint(request: Request, payload: MeasuredQasmPayload, background_tasks: BackgroundTasks, user=Depends(get_optional_user)):
    """Dispatch one OpenQASM 2.0 circuit for a shot-based measurement comparison across the
    simulator fleet. Runs in the background; poll GET /jobs/{job_id} for the result, which
    includes the divergence matrices, the explained-cause pairwise agreement classification,
    and (for measured mode) the shot-noise-aware statistical test alongside it. 400 for a
    circuit that does not parse as OpenQASM 2.0 (including a measure whose operands differ
    in size) or has too many qubits, and for unknown, disabled or unavailable runner ids;
    413 for a circuit over MAX_QASM_SIZE.

    The verdict of each pair of backends is ``measured_assessment`` in
    ``divergence_report.pairwise_agreement`` (``distinguishable`` is the disagreement), with
    ``marginal_assessment`` beside it. The ``agreement`` field of a measured pair is a
    distance label that ignores shot noise; a CI check should not read it as the verdict.

    There is no ``simulate`` field: a compile-only run of a circuit with measurements goes
    to POST /compare with ``simulate: false``, which compiles the same input (terminal
    measurements removed) and accepts circuits with measurements."""
    validate_request(payload.qasm_string, mode="measured", bypass_limits=payload.bypass_limits,
                     apply_preprocessing=payload.apply_preprocessing)
    validate_runner_ids(payload.target_simulators, payload.runner_config, payload.runner_phases)
    validate_runner_config(payload.runner_config)
    validate_compilers(payload.compilers)
    await require_available(payload.target_simulators)
    timeout = clamp_timeout(payload.timeout_seconds)
    job_id = str(uuid.uuid4())
    require_exclusive_slot(payload, client_address(request), job_id)

    ACTIVE_JOBS[job_id] = new_job(payload.execution_target, user.id if user else None)
    thresholds = effective_thresholds(payload.thresholds)
    background_tasks.add_task(worker_compare_measured, job_id, payload.qasm_string, payload.n_shots, payload.optimization_level, payload.runner_config, timeout, payload.target_simulators, payload.execution_target, payload.runner_phases, payload.apply_preprocessing, payload.seed, thresholds, payload.bypass_limits, payload.timing_repeats, exclusive=payload.exclusive, compilers=payload.compilers)

    return _job_envelope(job_id)

@router.post("/run_batch_suite", response_model=JobStatusResponse, responses=responses(400, 413, 422))
@limiter.limit(settings.RUN_RATE_LIMIT)
async def run_batch_suite_endpoint(request: Request, payload: BatchPayload, background_tasks: BackgroundTasks, user=Depends(get_optional_user)):
    """Dispatch a list of circuits (presets, bundled benchmark circuits, or user-supplied
    QASM) across the simulator fleet in a single job, in either statevector or measured mode.
    Runs in the background; poll GET /jobs/{job_id} for progress and the per-task results.
    400 for no tasks, unknown/disabled/unavailable runner ids, a literal circuit that
    fails the same checks as /compare or /compare_measured, or a preset or MQT Bench task
    over the mode's qubit limit (unless bypass_limits); the detail names the task as
    ``tasks[i]`` (0-based index). 422 for an unknown mode or source. Preset and benchmark
    tasks are generated in the background, and one that fails there is reported as that
    task's error.

    The finished job's ``results`` is a batch report: ``mode``, ``benchmark_summary`` (one
    single-circuit report per task, in task order, each with ``task_name``, ``task_qubits``
    and ``task_request``; a task that failed before dispatch is ``{task_name, task_request,
    error}``) and the shared run settings."""
    if not payload.tasks:
        raise HTTPException(status_code=400, detail="No tasks given.")
    validate_runner_ids(payload.target_simulators, payload.runner_config, payload.runner_phases)
    validate_runner_config(payload.runner_config)
    validate_compilers(payload.compilers)
    run_mode = payload.mode if payload.simulate else "compile"
    for index, task in enumerate(payload.tasks):
        label = f"tasks[{index}] ({task.name or task.algorithm or 'qasm'})"
        if task.qasm_string:
            try:
                validate_request(task.qasm_string, mode=run_mode,
                                 bypass_limits=payload.bypass_limits,
                                 apply_preprocessing=payload.apply_preprocessing)
                if payload.mode == "statevector" and payload.simulate:
                    check_statevector_circuit(task.qasm_string)
            except HTTPException as exc:
                raise HTTPException(status_code=exc.status_code, detail=f"{label}: {exc.detail}")
        elif (task.source or "preset") in ("preset", "mqt") and not payload.bypass_limits:
            cap = settings.max_qubits_for_mode(run_mode)
            if task.qubits and task.qubits > cap:
                raise HTTPException(status_code=400, detail=(
                    f"{label}: {task.qubits} qubits is over the {run_mode} limit of {cap}."))
    await require_available(payload.target_simulators)
    job_id = str(uuid.uuid4())
    require_exclusive_slot(payload, client_address(request), job_id)

    ACTIVE_JOBS[job_id] = new_job(payload.execution_target, user.id if user else None)
    background_tasks.add_task(worker_batch_suite, job_id, payload)

    return _job_envelope(job_id)
