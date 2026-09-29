"""Experiment routes: POST /experiments starts a sweep (poll GET /jobs/{id});
GET /experiments/{id}/bundle streams the finished bundle as an in-memory ZIP."""

import io
import uuid

from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse

from qrosetta_commons.helpers import get_logger
from schemas import ExperimentPayload, JobStatusResponse
from services.security import limiter
from services.job_manager import ACTIVE_JOBS
from services.experiment import worker_experiment, build_bundle_zip

logger = get_logger("rosetta-experiment-api")
router = APIRouter()


@router.post("/experiments", response_model=JobStatusResponse)
@limiter.limit("10/minute")
async def start_experiment(request: Request, payload: ExperimentPayload, background_tasks: BackgroundTasks):
    """Start a fleet-wide experiment: run every circuit in the payload across the fleet, over
    every preprocessing axis, and freeze the results into a citable bundle. Runs in the
    background; poll GET /jobs/{job_id} for status, then GET /experiments/{job_id}/bundle once
    complete."""
    if not payload.circuits:
        return JSONResponse(status_code=400, content={"error": "No circuits selected."})
    if payload.mode not in ("measured", "statevector"):
        return JSONResponse(status_code=400,
                            content={"error": f"Unknown mode: {payload.mode}"})

    job_id = str(uuid.uuid4())
    ACTIVE_JOBS[job_id] = {"status": "pending", "target": payload.execution_target}
    background_tasks.add_task(worker_experiment, job_id, payload)
    return {"job_id": job_id, "status": ACTIVE_JOBS[job_id]["status"],
            "target": ACTIVE_JOBS[job_id]["target"]}


@router.get("/experiments/{job_id}/bundle")
async def download_experiment_bundle(job_id: str):
    """Download a completed experiment as an in-memory ZIP: the frozen input circuits, the
    per-circuit results, a manifest (git SHA, image digests, SDK versions, seeds), a
    conformance matrix (did each circuit run on each backend?), and an agreement-prevalence
    summary. 404 if the job id is unknown; 409 if the experiment has not finished yet."""
    job = ACTIVE_JOBS.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "Job not found"})
    if job.get("status") != "completed" or not job.get("bundle_files"):
        return JSONResponse(status_code=409,
                            content={"error": f"Bundle not ready (status: {job.get('status')})."})

    data = build_bundle_zip(job["bundle_files"])
    name = job.get("bundle_name") or f"experiment_{job_id[:8]}"
    headers = {"Content-Disposition": f'attachment; filename="{name}.zip"'}
    return StreamingResponse(io.BytesIO(data), media_type="application/zip", headers=headers)
