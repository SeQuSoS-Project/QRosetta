# FastAPI router endpoints for history.

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

import db.models as models
import schemas
import services.history as history_service
from db.database import get_db
from services.security import get_current_user
from services.exporter import build_export_context, build_ro_crate
from qrosetta_commons.helpers import get_logger
from fastapi.responses import StreamingResponse
import io

logger = get_logger("rosetta-history")

router = APIRouter(
    prefix="/history",
    tags=["history"],
)


@router.post("/circuits", response_model=schemas.SavedCircuitResponse, status_code=status.HTTP_201_CREATED)
def create_saved_circuit(
    circuit: schemas.SavedCircuitCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Save a named QASM circuit to the current user's account, for later reuse."""
    return history_service.create_circuit(
        db, current_user.id, circuit.name, circuit.qasm_string)


@router.get("/circuits", response_model=List[schemas.SavedCircuitResponse])
def get_saved_circuits(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """List every circuit the current user has saved."""
    return history_service.list_circuits(db, current_user.id)


@router.post("/runs", response_model=schemas.RunHistoryResponse, status_code=status.HTTP_201_CREATED)
def save_run(
    run_payload: dict,
    circuit_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Save a completed run's full report to the current user's history. The report body
    (run_payload) is stripped of statevectors and stored to local disk or S3 (depending on
    the server's STORAGE_MODE); only a reference is kept in the database. Optionally link it
    to a previously-saved circuit via circuit_id."""
    try:
        return history_service.save_run(db, current_user.id, run_payload, circuit_id)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save run history")


@router.get("/runs", response_model=List[schemas.RunHistoryResponse])
def get_run_histories(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """List every run the current user has saved (metadata only, not the full report)."""
    return history_service.list_runs(db, current_user.id)


@router.get("/runs/{run_id}")
def get_run_history_details(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Fetch one saved run's full report by id. 404 if it does not exist or does not belong
    to the current user."""
    try:
        return history_service.get_run_report(db, current_user.id, run_id)
    except history_service.RunNotFound:
        raise HTTPException(status_code=404, detail="Run history not found")
    except Exception:
        logger.error(f"Failed to fetch run report for run_id={run_id}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch run history details")


@router.patch("/runs/{run_id}", response_model=schemas.RunHistoryResponse)
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
        raise HTTPException(status_code=404, detail="Run history not found")


@router.delete("/runs")
def batch_delete_runs(
    payload: schemas.RunHistoryBatchDelete,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Delete multiple saved runs (and their stored reports) by id in one request. Ids that
    do not exist or do not belong to the current user are silently skipped."""
    try:
        deleted = history_service.delete_runs(db, current_user.id, payload.run_ids)
    except Exception:
        logger.error("Failed to delete run reports from storage", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete run reports")

    if deleted == 0:
        return {"detail": "No valid runs found to delete"}
    return {"detail": f"Successfully deleted {deleted} runs"}


@router.post("/runs/{run_id}/export")
def export_run_as_ro_crate(
    run_id: str,
    payload: schemas.ExportPayload,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Export a saved run history as a FAIR-compliant RO-Crate ZIP bundle."""
    try:
        report_data = history_service.get_run_report(db, current_user.id, run_id)
    except history_service.RunNotFound:
        raise HTTPException(status_code=404, detail="Run history not found")
    except Exception:
        logger.error(f"Failed to fetch run report for export, run_id={run_id}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch run history for export")

    ctx = build_export_context(report_data, payload)

    try:
        zip_bytes = build_ro_crate(ctx)
    except Exception:
        logger.error(f"RO-Crate export failed for run_id={run_id}", exc_info=True)
        raise HTTPException(status_code=500, detail="Export failed")

    ts_slug = ctx.timestamp.replace(":", "-").replace("+", "p")
    filename = f"rosetta-export-{ts_slug}.zip"

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
