"""Experiment routes: POST /experiments starts a sweep (poll GET /jobs/{id});
GET /experiments/{id}/bundle streams the finished bundle as an in-memory ZIP."""

from services.compilation import validate_compilers
from services.job_manager import require_exclusive_slot
from services.security import client_address
from config import settings
import io
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse

from qrosetta_commons.helpers import get_logger
from schemas import ExperimentPayload, JobStatusResponse
from routers.errors import responses
from services.availability import require_available
from services.job_store import JOB_NOT_FOUND
from services.security import limiter
from services.job_manager import ACTIVE_JOBS, new_job
from services.experiment import worker_experiment, build_bundle_zip
from services.validator import (
    check_statevector_circuit, validate_request, validate_runner_config, validate_runner_ids,
)

logger = get_logger("rosetta-experiment-api")
router = APIRouter()


@router.post("/experiments", response_model=JobStatusResponse, responses=responses(400, 413, 422))
@limiter.limit(settings.RUN_RATE_LIMIT)
async def start_experiment(request: Request, payload: ExperimentPayload, background_tasks: BackgroundTasks):
    """Start a fleet-wide experiment: run every circuit in the payload across the fleet, over
    every preprocessing axis, and freeze the results into a citable bundle. Runs in the
    background; poll GET /jobs/{job_id} for status, then GET /experiments/{job_id}/bundle once
    complete. 400 for no circuits, more circuits x preprocessing axes than max_experiment_cells
    in GET /config (unless bypass_limits), unknown/disabled/unavailable runner ids, or a literal
    circuit that fails the /compare or /compare_measured checks; 422 for an unknown field,
    mode or source. The job's target is the server's EXECUTION_MODE."""
    if not payload.circuits:
        raise HTTPException(status_code=400, detail="No circuits selected.")
    cells = len(payload.circuits) * len(payload.preprocessing_modes)
    if cells > settings.MAX_EXPERIMENT_CELLS and not payload.bypass_limits:
        raise HTTPException(status_code=400, detail=(
            f"Experiment too large: {len(payload.circuits)} circuits x {len(payload.preprocessing_modes)} "
            f"preprocessing axes = {cells} circuit-axis runs, over the limit of "
            f"{settings.MAX_EXPERIMENT_CELLS}. Reduce the selection."))

    validate_runner_ids(payload.target_simulators, payload.runner_config, payload.runner_phases)
    validate_runner_config(payload.runner_config)
    validate_compilers(payload.compilers)
    for index, circuit in enumerate(payload.circuits):
        if circuit.qasm_string:
            label = circuit.name or circuit.algorithm or f"circuit {index}"
            try:
                validate_request(circuit.qasm_string, mode=payload.mode, bypass_limits=payload.bypass_limits,
                                 apply_preprocessing=True in payload.preprocessing_modes)
                if payload.mode == "statevector":
                    check_statevector_circuit(circuit.qasm_string)
            except HTTPException as exc:
                raise HTTPException(status_code=exc.status_code, detail=f"Circuit {index} ({label}): {exc.detail}")
    await require_available(payload.target_simulators)

    job_id = str(uuid.uuid4())
    require_exclusive_slot(payload, client_address(request), job_id)
    ACTIVE_JOBS[job_id] = {**new_job(payload.execution_target), "kind": "experiment"}
    requested_target = ACTIVE_JOBS[job_id].get("requested_target")
    payload.execution_target = settings.EXECUTION_MODE
    background_tasks.add_task(worker_experiment, job_id, payload)
    return {"job_id": job_id, "status": ACTIVE_JOBS[job_id]["status"],
            "target": ACTIVE_JOBS[job_id]["target"], "requested_target": requested_target}


@router.get("/experiments/{job_id}/bundle", responses=responses(404, 409))
async def download_experiment_bundle(job_id: str):
    """Download a completed experiment as an in-memory ZIP: the frozen input circuits, the
    per-circuit results, a manifest (job id, git SHA, executed SDK versions, seeds, and
    image digests when the deployment sets QROSETTA_IMAGE_DIGESTS, otherwise marked 'not
    recorded'; runner_images lists the per-result images the Kubernetes path records), a
    conformance matrix (did each circuit run on each backend?), and an agreement-prevalence
    summary. 404 if the job id is unknown or is not an experiment; 409 if the experiment
    has not finished or failed."""
    job = ACTIVE_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=JOB_NOT_FOUND)
    if job.get("kind") != "experiment" and "bundle_files" not in job:
        raise HTTPException(status_code=404, detail="This job is not an experiment and has no bundle; use GET /jobs/{job_id}/report or POST /jobs/{job_id}/export.")
    if job.get("status") == "failed":
        raise HTTPException(status_code=409, detail=f"The experiment failed and has no bundle: {job.get('error')}")
    if job.get("status") != "completed" or not job.get("bundle_files"):
        raise HTTPException(status_code=409, detail=f"The experiment has not finished yet (status: {job.get('status')}).")

    data = build_bundle_zip(job["bundle_files"])
    name = job.get("bundle_name") or f"experiment_{job_id[:8]}"
    headers = {"Content-Disposition": f'attachment; filename="{name}.zip"'}
    return StreamingResponse(io.BytesIO(data), media_type="application/zip", headers=headers)
