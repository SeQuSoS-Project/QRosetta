# FastAPI router endpoints for history.

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid

import db.models as models
import schemas
from db.database import get_db
from services.security import get_current_user
from services.storage import save_run_report, fetch_run_report, delete_run_reports
from services.exporter import ExportContext, build_ro_crate
from config import settings
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
    new_circuit = models.SavedCircuit(
        user_id=current_user.id,
        name=circuit.name,
        qasm_string=circuit.qasm_string
    )
    db.add(new_circuit)
    db.commit()
    db.refresh(new_circuit)
    return new_circuit

@router.get("/circuits", response_model=List[schemas.SavedCircuitResponse])
def get_saved_circuits(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    circuits = db.query(models.SavedCircuit).filter(models.SavedCircuit.user_id == current_user.id).all()
    return circuits

@router.post("/runs", response_model=schemas.RunHistoryResponse, status_code=status.HTTP_201_CREATED)
def save_run(
    run_payload: dict,
    circuit_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    run_id = str(uuid.uuid4())
    run_name = run_payload.get("run_name", run_id[:8])

    try:

        s3_key = save_run_report(current_user.id, run_id, run_payload)

        new_run = models.RunHistory(
            id=run_id,
            user_id=current_user.id,
            circuit_id=circuit_id,
            s3_object_key=s3_key,
            run_name=run_name
        )
        db.add(new_run)
        db.commit()
        db.refresh(new_run)
        return new_run
    except Exception as e:
        db.rollback()
        logger.error("Failed to save run history", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save run history")

@router.get("/runs", response_model=List[schemas.RunHistoryResponse])
def get_run_histories(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    runs = db.query(models.RunHistory).filter(models.RunHistory.user_id == current_user.id).all()
    return runs

@router.get("/runs/{run_id}")
def get_run_history_details(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    run_record = db.query(models.RunHistory).filter(
        models.RunHistory.id == run_id,
        models.RunHistory.user_id == current_user.id
    ).first()

    if not run_record:
        raise HTTPException(status_code=404, detail="Run history not found")

    try:
        report_data = fetch_run_report(run_record.s3_object_key)
        return report_data
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
    run_record = db.query(models.RunHistory).filter(
        models.RunHistory.id == run_id,
        models.RunHistory.user_id == current_user.id
    ).first()

    if not run_record:
        raise HTTPException(status_code=404, detail="Run history not found")

    run_record.run_name = update_data.run_name
    db.commit()
    db.refresh(run_record)
    return run_record

@router.delete("/runs")
def batch_delete_runs(
    payload: schemas.RunHistoryBatchDelete,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    run_records = db.query(models.RunHistory).filter(
        models.RunHistory.id.in_(payload.run_ids),
        models.RunHistory.user_id == current_user.id
    ).all()

    if not run_records:
        return {"detail": "No valid runs found to delete"}

    s3_keys_to_delete = [run.s3_object_key for run in run_records]

    try:
        delete_run_reports(s3_keys_to_delete)
    except Exception:
        logger.error("Failed to delete run reports from storage", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete run reports")

    for run in run_records:
        db.delete(run)
    db.commit()
    return {"detail": f"Successfully deleted {len(run_records)} runs"}

@router.post("/runs/{run_id}/export")
def export_run_as_ro_crate(
    run_id: str,
    payload: schemas.ExportPayload,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Export a saved run history as a FAIR-compliant RO-Crate ZIP bundle."""
    run_record = db.query(models.RunHistory).filter(
        models.RunHistory.id == run_id,
        models.RunHistory.user_id == current_user.id
    ).first()

    if not run_record:
        raise HTTPException(status_code=404, detail="Run history not found")

    try:
        report_data = fetch_run_report(run_record.s3_object_key)
    except Exception:
        logger.error(f"Failed to fetch run report for export, run_id={run_id}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch run history for export")

    mode = "measured" if "n_shots" in report_data else "statevector"
    qasm_string = report_data.get("input_qasm", report_data.get("qasm_string", ""))

    ctx = ExportContext(
        qasm_string=qasm_string,
        results=report_data,
        mode=mode,
        runner_services=settings.get_runner_services(),
        include_statevectors=payload.include_statevectors,
        author_name=payload.author_name,
        author_affiliation=payload.author_affiliation,
    )

    try:
        zip_bytes = build_ro_crate(ctx)
    except Exception as e:
        logger.error(f"RO-Crate export failed for run_id={run_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Export failed")

    ts_slug = ctx.timestamp.replace(":", "-").replace("+", "p")
    filename = f"rosetta-export-{ts_slug}.zip"

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

