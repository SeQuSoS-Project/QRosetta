"""Saved-circuit and run-history routes, all scoped to the authenticated user."""

from services.report_validation import reject_invalid_report
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from typing import List

import db.models as models
import schemas
import services.history as history_service
from db.database import get_db
from services.security import get_current_user
from services.exporter import build_export_context, build_ro_crate, crate_name
from services.publication.views import ParameterError
from services.job_manager import ACTIVE_JOBS, job_with_report_or_error
from services.report_filters import remove_statevectors
from routers.errors import responses
from services.validator import validate_request
from schemas.reports import SavedRunReport
from qrosetta_commons.helpers import get_logger
from fastapi.responses import StreamingResponse
import io
import threading

logger = get_logger("rosetta-history")

router = APIRouter(
    prefix="/history",
    tags=["history"],
)

_SAVE_LOCKS: dict = {}
_SAVE_LOCKS_GUARD = threading.Lock()


def _job_save_lock(job_id: str) -> threading.Lock:
    """One lock per job id for from_job saves; locks of evicted jobs are dropped."""
    with _SAVE_LOCKS_GUARD:
        for stale in [jid for jid in _SAVE_LOCKS if jid not in ACTIVE_JOBS]:
            _SAVE_LOCKS.pop(stale, None)
        return _SAVE_LOCKS.setdefault(job_id, threading.Lock())


_CIRCUIT_NOT_FOUND = "Saved circuit not found"
_RUN_NOT_FOUND = "Run history not found"
_RUN_NOT_FOUND_DOC = "No saved run with that id belongs to this account."


@router.post("/circuits", response_model=schemas.SavedCircuitResponse, status_code=status.HTTP_201_CREATED,
             responses=responses((400, "The text does not parse as OpenQASM 2.0, or is over the compile-only qubit cap (max_qubits_compile in GET /config)."), 413))
def create_saved_circuit(
    circuit: schemas.SavedCircuitCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Save a named QASM circuit to the current user's account, for later reuse. The text
    must pass the checks of a compile-only run (parses as OpenQASM 2.0, at most
    max_qubits_compile qubits, MAX_QASM_SIZE bytes): 400 or 413 otherwise."""
    validate_request(circuit.qasm_string, mode="compile")
    return history_service.create_circuit(
        db, current_user.id, circuit.name, circuit.qasm_string)


@router.patch("/circuits/{circuit_id}", response_model=schemas.SavedCircuitResponse,
              responses=responses((404, "No saved circuit with that id belongs to this account.")))
def rename_saved_circuit(
    circuit_id: str,
    update: schemas.SavedCircuitUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Rename one of the current user's saved circuits. 404 if it is not one of theirs."""
    try:
        return history_service.rename_circuit(db, current_user.id, circuit_id, update.name)
    except history_service.CircuitNotFound:
        raise HTTPException(status_code=404, detail=_CIRCUIT_NOT_FOUND)


@router.delete("/circuits/{circuit_id}", status_code=status.HTTP_204_NO_CONTENT,
               responses=responses((404, "No saved circuit with that id belongs to this account.")))
def delete_saved_circuit(
    circuit_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Delete one of the current user's saved circuits. Saved runs linked to it are kept and
    their circuit_id becomes null. 404 if it is not one of theirs."""
    try:
        history_service.delete_circuit(db, current_user.id, circuit_id)
    except history_service.CircuitNotFound:
        raise HTTPException(status_code=404, detail=_CIRCUIT_NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/circuits", response_model=List[schemas.SavedCircuitResponse])
def get_saved_circuits(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """List every circuit the current user has saved."""
    return history_service.list_circuits(db, current_user.id)


@router.post("/runs", response_model=schemas.RunHistoryResponse, status_code=status.HTTP_201_CREATED,
             responses=responses(
                 (400, "The report names a runner key of the wrong form, or has the wrong shape inside raw_results."),
                 (404, "circuit_id is not one of this account's saved circuits."),
                 (422, "The body is neither a single-circuit report (raw_results list) nor a batch report (benchmark_summary list), or circuit_id is not a string or differs between the query and the body. Body: {\"detail\": [{\"loc\": [...], \"msg\": str, \"type\": str}]}.")))
def save_run(
    run_payload: dict,
    circuit_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Save a completed run's report to the current user's history. Statevectors are
    removed and the stored report is marked ``statevector_storage="removed_before_storage"``;
    it goes to local disk or S3 per STORAGE_MODE, with a reference in the database.
    Optionally link it to a saved circuit with ``circuit_id``, as a query parameter or a
    top-level body field (not stored in the report); 404 if it is not one of the current
    user's saved circuits. 422 for a body that is neither a single-circuit report
    (raw_results list) nor a batch report (benchmark_summary list).
    Prefer POST /history/runs/from_job/{job_id}, which stores the server's copy."""
    body_circuit_id = run_payload.pop("circuit_id", None)
    if body_circuit_id is not None and not isinstance(body_circuit_id, str):
        raise HTTPException(status_code=422, detail=[
            {"loc": ["body", "circuit_id"], "msg": "circuit_id must be a string", "type": "string_type"}])
    if body_circuit_id is not None and circuit_id is not None and body_circuit_id != circuit_id:
        raise HTTPException(status_code=422, detail=[
            {"loc": ["body", "circuit_id"], "msg": "circuit_id differs between the query and the body",
             "type": "value_error"}])
    circuit_id = circuit_id if circuit_id is not None else body_circuit_id
    problems = history_service.report_structure_problems(run_payload)
    if problems:
        raise HTTPException(status_code=422, detail=[
            {"loc": loc, "msg": msg, "type": "value_error"} for loc, msg in problems])
    reject_invalid_report(run_payload)
    try:
        return history_service.save_run(db, current_user.id, run_payload, circuit_id)
    except history_service.CircuitNotFound:
        raise HTTPException(status_code=404, detail=_CIRCUIT_NOT_FOUND)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save run history")


@router.post("/runs/from_job/{job_id}", response_model=schemas.RunHistoryResponse,
             status_code=status.HTTP_201_CREATED, responses={
                 200: {"model": schemas.RunHistoryResponse,
                       "description": "This account already saved the job: the existing run, renamed when a different run_name is given. Answered even after the job has expired."},
                 **responses(
                     (403, "Another signed-in account started this job, or this account is deactivated."),
                     (404, "Unknown or expired job id, and this account has not saved it."),
                     (409, "The job has not finished, failed before any runner ran, or is an experiment."),
                     422)})
def save_run_from_job(
    job_id: str,
    response: Response,
    body: schemas.RunHistoryFromJob | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Save a finished /compare, /compare_measured or /run_batch_suite job to the current
    user's history from the server's copy of its report, so the browser uploads nothing.
    Statevectors are removed before storage and the stored report is marked
    ``statevector_storage="removed_before_storage"``. Returns the saved run; its ``id`` is
    the run id (201). Saving a job the current user already saved returns that run (200)
    and stores nothing new, renaming it when a different run_name is given; this works after
    the job has expired too. 404 if the job id is unknown or expired and not saved by this
    account; 409 if the job has not finished, failed before any runner ran, or is an
    experiment; 403 if another signed-in account started it. A job submitted without a
    sign-in can be saved by any account that holds its id."""
    def existing_run():
        existing = history_service.find_run_for_job(db, current_user.id, job_id)
        if existing is None:
            return None
        response.status_code = status.HTTP_200_OK
        if body and body.run_name and body.run_name != existing.run_name:
            existing = history_service.rename_run(db, current_user.id, existing.id, body.run_name)
        return existing

    saved = existing_run()
    if saved is not None:
        return saved
    job, report = job_with_report_or_error(job_id, "save", each_task=remove_statevectors)
    owner = job.get("owner_user_id")
    if owner is not None and owner != current_user.id:
        raise HTTPException(status_code=403, detail=(
            "This job was started by another signed-in account; only that account can save it."))
    with _job_save_lock(job_id):
        saved = existing_run()
        if saved is not None:
            return saved
        name = (body.run_name if body else None) or history_service.default_run_name(report, job_id)
        try:
            return history_service.save_run(
                db, current_user.id, {**report, "run_name": name, "job_id": job_id},
                saved_from=history_service.SAVED_FROM_JOB)
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to save run history")


@router.get("/runs", response_model=List[schemas.RunHistoryResponse])
def get_run_histories(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """List every run the current user has saved (metadata only, not the full report)."""
    return history_service.list_runs(db, current_user.id)


@router.get("/runs/{run_id}", responses={
    200: {"model": SavedRunReport, "description": "The stored report with run_id, run_name and created_at added."},
    **responses((404, _RUN_NOT_FOUND_DOC))})
def get_run_history_details(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Fetch one saved run's full report by id, with ``run_id``, ``run_name`` and
    ``created_at`` (UTC ISO 8601 ending in 'Z') added at the top level. 404 if it does not
    exist or does not belong to the current user."""
    try:
        return history_service.get_run_report_with_metadata(db, current_user.id, run_id)
    except history_service.RunNotFound:
        raise HTTPException(status_code=404, detail=_RUN_NOT_FOUND)
    except Exception:
        logger.error(f"Failed to fetch run report for run_id={run_id}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch run history details")


@router.patch("/runs/{run_id}", response_model=schemas.RunHistoryResponse,
              responses=responses((404, _RUN_NOT_FOUND_DOC)))
def update_run_name(
    run_id: str,
    update_data: schemas.RunHistoryUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Rename a saved run. 404 if it does not exist or does not belong to the current user."""
    try:
        return history_service.rename_run(db, current_user.id, run_id, update_data.run_name)
    except history_service.RunNotFound:
        raise HTTPException(status_code=404, detail=_RUN_NOT_FOUND)


@router.delete("/runs", response_model=schemas.RunHistoryBatchDeleteResponse,
               responses=responses((404, "None of the ids is a run of this account; nothing was deleted.")))
def batch_delete_runs(
    payload: schemas.RunHistoryBatchDelete,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Delete multiple saved runs (and their stored reports) by id in one request. Ids that
    do not exist or do not belong to the current user are listed in ``not_found`` and
    skipped; 404 when that is every id."""
    try:
        deleted = history_service.delete_runs(db, current_user.id, payload.run_ids)
    except Exception:
        logger.error("Failed to delete run reports from storage", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete run reports")

    if not deleted:
        raise HTTPException(status_code=404, detail="None of the given ids is a saved run of this account; nothing was deleted.")
    not_found = [run_id for run_id in dict.fromkeys(payload.run_ids) if run_id not in set(deleted)]
    return {"detail": f"Deleted {len(deleted)} run{'s' if len(deleted) != 1 else ''}",
            "deleted": deleted, "not_found": not_found}


@router.post("/runs/{run_id}/export", responses=responses(
    (400, "An export option the report cannot take (e.g. a publication view parameter)."),
    (404, _RUN_NOT_FOUND_DOC)))
def export_run_as_ro_crate(
    run_id: str,
    payload: schemas.ExportPayload | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Export a saved run as an RO-Crate ZIP bundle. The crate carries the run's current
    name; stored reports keep each statevector's sha256 and length, not the vector. The
    body is optional; every option has a default."""
    payload = payload or schemas.ExportPayload()
    try:
        report_data = history_service.get_run_report_with_metadata(db, current_user.id, run_id)
    except history_service.RunNotFound:
        raise HTTPException(status_code=404, detail=_RUN_NOT_FOUND)
    except Exception:
        logger.error(f"Failed to fetch run report for export, run_id={run_id}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch run history for export")

    ctx = build_export_context(report_data, payload, "saved_run")

    try:
        zip_bytes = build_ro_crate(ctx)
    except ParameterError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.error(f"RO-Crate export failed for run_id={run_id}", exc_info=True)
        raise HTTPException(status_code=500, detail="Export failed")

    filename = f"{crate_name(ctx)}.zip"

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
