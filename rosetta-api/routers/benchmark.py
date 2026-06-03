# FastAPI router endpoints for benchmark.

from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import JSONResponse
import uuid
from qrosetta_commons.helpers import get_logger
from services.validator import validate_request, validate_runner_config
from schemas import QasmPayload, MeasuredQasmPayload, BatchPayload, JobStatusResponse
from services.security import limiter
from config import settings
from services.job_manager import (
    ACTIVE_JOBS,
    worker_compare,
    worker_compare_measured,
    worker_batch_suite
)

logger = get_logger("rosetta-benchmark-api")
router = APIRouter()

@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    if job_id not in ACTIVE_JOBS:
        return JSONResponse(status_code=404, content={"error": "Job not found"})

    job_data = ACTIVE_JOBS[job_id]
    return {
        "job_id": job_id,
        "status": job_data["status"],
        "target": job_data["target"],
        "results": job_data.get("results"),
        "error": job_data.get("error"),
        "runner_statuses": job_data.get("runner_statuses"),
    }

@router.post("/compare", response_model=JobStatusResponse)
@limiter.limit("10/minute")
async def compare_circuits_endpoint(request: Request, payload: QasmPayload, background_tasks: BackgroundTasks):
    validate_request(payload.qasm_string, mode="statevector", bypass_limits=payload.bypass_limits)
    validate_runner_config(payload.runner_config)
    timeout = max(1, min(payload.timeout_seconds, settings.RUNNER_TIMEOUT_SEC))
    job_id = str(uuid.uuid4())

    ACTIVE_JOBS[job_id] = {"status": "pending", "target": payload.execution_target}
    background_tasks.add_task(worker_compare, job_id, payload.qasm_string, payload.optimization_level, payload.runner_config, timeout, payload.target_simulators, payload.execution_target, payload.runner_phases, payload.apply_preprocessing)

    return {"job_id": job_id, "status": ACTIVE_JOBS[job_id]["status"], "target": ACTIVE_JOBS[job_id]["target"]}

@router.post("/compare_measured", response_model=JobStatusResponse)
@limiter.limit("10/minute")
async def compare_measured_circuits_endpoint(request: Request, payload: MeasuredQasmPayload, background_tasks: BackgroundTasks):
    validate_request(payload.qasm_string, mode="measured", bypass_limits=payload.bypass_limits)
    validate_runner_config(payload.runner_config)
    timeout = max(1, min(payload.timeout_seconds, settings.RUNNER_TIMEOUT_SEC))
    job_id = str(uuid.uuid4())

    ACTIVE_JOBS[job_id] = {"status": "pending", "target": payload.execution_target}
    background_tasks.add_task(worker_compare_measured, job_id, payload.qasm_string, payload.n_shots, payload.optimization_level, payload.runner_config, timeout, payload.target_simulators, payload.execution_target, payload.runner_phases, payload.apply_preprocessing)

    return {"job_id": job_id, "status": ACTIVE_JOBS[job_id]["status"], "target": ACTIVE_JOBS[job_id]["target"]}

@router.post("/run_batch_suite", response_model=JobStatusResponse)
@limiter.limit("10/minute")
async def run_batch_suite_endpoint(request: Request, payload: BatchPayload, background_tasks: BackgroundTasks):
    validate_runner_config(payload.runner_config)
    job_id = str(uuid.uuid4())

    ACTIVE_JOBS[job_id] = {"status": "pending", "target": payload.execution_target}
    background_tasks.add_task(worker_batch_suite, job_id, payload)

    return {"job_id": job_id, "status": ACTIVE_JOBS[job_id]["status"], "target": ACTIVE_JOBS[job_id]["target"]}
