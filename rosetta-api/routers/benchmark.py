"""Benchmark job routes: start single, measured and batch runs; poll and fetch job reports."""

from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
import uuid
from qrosetta_commons.helpers import get_logger
from services.validator import (
    check_statevector_circuit, validate_request, validate_runner_config, validate_runner_ids,
)
from schemas import QasmPayload, MeasuredQasmPayload, BatchPayload, JobStatusResponse
from services.security import limiter
from config import settings
from services.job_manager import (
    ACTIVE_JOBS,
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

@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Poll the status of any background job started by /compare, /compare_measured,
    /run_batch_suite, or /experiments. 404 if the job id is unknown."""
    if job_id not in ACTIVE_JOBS:
        return JSONResponse(status_code=404, content={"error": "Job not found"})

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

@router.get("/jobs/{job_id}/report")
@limiter.limit("30/minute")
async def get_job_full_report(request: Request, job_id: str):
    """Download the untruncated report of a completed /compare, /compare_measured or
    /run_batch_suite job as JSON, including statevectors that GET /jobs/{job_id} replaces
    with a placeholder. 404 if the job id is unknown or expired; 409 if the job has not
    completed (including a failed job) or has no server copy."""
    job = ACTIVE_JOBS.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    if job.get("status") != "completed" or not job.get("full_results"):
        return JSONResponse(status_code=409, content={"error": f"No report for this job (status: {job.get('status')})"})
    return JSONResponse(
        content=job["full_results"],
        headers={"Content-Disposition": f'attachment; filename="qrosetta_report_{job_id[:8]}.json"'},
    )

@router.post("/compare", response_model=JobStatusResponse)
@limiter.limit(settings.RUN_RATE_LIMIT)
async def compare_circuits_endpoint(request: Request, payload: QasmPayload, background_tasks: BackgroundTasks):
    """Dispatch one OpenQASM 2.0 circuit for an exact statevector comparison across the
    simulator fleet. Runs in the background; poll GET /jobs/{job_id} for the result, which
    includes the fidelity/phase agreement matrices, per-backend performance/resource data, and
    the explained-cause pairwise agreement classification."""
    validate_request(payload.qasm_string, mode="statevector", bypass_limits=payload.bypass_limits)
    check_statevector_circuit(payload.qasm_string)
    validate_runner_ids(payload.target_simulators, payload.runner_config, payload.runner_phases)
    validate_runner_config(payload.runner_config)
    timeout = clamp_timeout(payload.timeout_seconds)
    job_id = str(uuid.uuid4())

    ACTIVE_JOBS[job_id] = new_job(payload.execution_target)
    thresholds = effective_thresholds(payload.thresholds)
    background_tasks.add_task(worker_compare, job_id, payload.qasm_string, payload.optimization_level, payload.runner_config, timeout, payload.target_simulators, payload.execution_target, payload.runner_phases, payload.apply_preprocessing, thresholds)

    return _job_envelope(job_id)

@router.post("/compare_measured", response_model=JobStatusResponse)
@limiter.limit(settings.RUN_RATE_LIMIT)
async def compare_measured_circuits_endpoint(request: Request, payload: MeasuredQasmPayload, background_tasks: BackgroundTasks):
    """Dispatch one OpenQASM 2.0 circuit for a shot-based measurement comparison across the
    simulator fleet. Runs in the background; poll GET /jobs/{job_id} for the result, which
    includes the divergence matrices, the explained-cause pairwise agreement classification,
    and (for measured mode) the shot-noise-aware statistical test alongside it."""
    validate_request(payload.qasm_string, mode="measured", bypass_limits=payload.bypass_limits)
    validate_runner_ids(payload.target_simulators, payload.runner_config, payload.runner_phases)
    validate_runner_config(payload.runner_config)
    timeout = clamp_timeout(payload.timeout_seconds)
    job_id = str(uuid.uuid4())

    ACTIVE_JOBS[job_id] = new_job(payload.execution_target)
    thresholds = effective_thresholds(payload.thresholds)
    background_tasks.add_task(worker_compare_measured, job_id, payload.qasm_string, payload.n_shots, payload.optimization_level, payload.runner_config, timeout, payload.target_simulators, payload.execution_target, payload.runner_phases, payload.apply_preprocessing, payload.seed, thresholds)

    return _job_envelope(job_id)

@router.post("/run_batch_suite", response_model=JobStatusResponse)
@limiter.limit(settings.RUN_RATE_LIMIT)
async def run_batch_suite_endpoint(request: Request, payload: BatchPayload, background_tasks: BackgroundTasks):
    """Dispatch a list of circuits (presets, bundled benchmark circuits, or user-supplied
    QASM) across the simulator fleet in a single job, in either statevector or measured mode.
    Runs in the background; poll GET /jobs/{job_id} for progress and the per-task results.
    400 for an unknown mode, unknown/disabled runner ids, or (statevector mode) a literal
    circuit with mid-circuit measurement, reset or classical control."""
    if payload.mode not in ("statevector", "measured"):
        raise HTTPException(status_code=400, detail=f"Unknown mode: {payload.mode}. Use 'statevector' or 'measured'.")
    validate_runner_ids(payload.target_simulators, payload.runner_config, payload.runner_phases)
    validate_runner_config(payload.runner_config)
    if payload.mode == "statevector":
        for task in payload.tasks:
            if task.qasm_string:
                check_statevector_circuit(task.qasm_string)
    job_id = str(uuid.uuid4())

    ACTIVE_JOBS[job_id] = new_job(payload.execution_target)
    background_tasks.add_task(worker_batch_suite, job_id, payload)

    return _job_envelope(job_id)
