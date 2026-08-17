"""Saved circuits and run history: database access and report storage.

The router used to hold this directly — SQLAlchemy queries, commits, rollbacks and S3
calls inline in six of its seven endpoints, plus its own copy of the RO-Crate
ExportContext assembly. That second copy is how routers/export.py and routers/history.py
drifted apart until one of them silently dropped publication_artifacts.

Every lookup filters by user_id, so a caller can only reach their own rows. Functions
raise ValueError for "not found"; the router turns that into a 404.
"""

import uuid

from sqlalchemy.orm import Session

import db.models as models
from qrosetta_commons.helpers import get_logger
from services.storage import delete_run_reports, fetch_run_report, save_run_report

logger = get_logger("rosetta-history")


class RunNotFound(ValueError):
    """No run with that id belongs to this user."""


# --- Saved circuits ---

def create_circuit(db: Session, user_id: int, name: str, qasm_string: str) -> models.SavedCircuit:
    circuit = models.SavedCircuit(user_id=user_id, name=name, qasm_string=qasm_string)
    db.add(circuit)
    db.commit()
    db.refresh(circuit)
    return circuit


def list_circuits(db: Session, user_id: int) -> list:
    return db.query(models.SavedCircuit).filter(models.SavedCircuit.user_id == user_id).all()


# --- Run history ---

def _owned_run(db: Session, user_id: int, run_id: str) -> models.RunHistory:
    run = db.query(models.RunHistory).filter(
        models.RunHistory.id == run_id,
        models.RunHistory.user_id == user_id,
    ).first()
    if not run:
        raise RunNotFound(run_id)
    return run


def save_run(db: Session, user_id: int, run_payload: dict,
             circuit_id: str | None = None) -> models.RunHistory:
    """Store the report, then record it. The row is only committed once the report is
    stored, so history never references a report that does not exist."""
    run_id = str(uuid.uuid4())
    run_name = run_payload.get("run_name", run_id[:8])
    try:
        s3_key = save_run_report(user_id, run_id, run_payload)
        run = models.RunHistory(
            id=run_id,
            user_id=user_id,
            circuit_id=circuit_id,
            s3_object_key=s3_key,
            run_name=run_name,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
    except Exception:
        db.rollback()
        logger.error("Failed to save run history", exc_info=True)
        raise


def list_runs(db: Session, user_id: int) -> list:
    return db.query(models.RunHistory).filter(models.RunHistory.user_id == user_id).all()


def get_run_report(db: Session, user_id: int, run_id: str) -> dict:
    run = _owned_run(db, user_id, run_id)
    return fetch_run_report(run.s3_object_key)


def rename_run(db: Session, user_id: int, run_id: str, run_name: str) -> models.RunHistory:
    run = _owned_run(db, user_id, run_id)
    run.run_name = run_name
    db.commit()
    db.refresh(run)
    return run


def delete_runs(db: Session, user_id: int, run_ids: list) -> int:
    """Delete the stored reports first, then the rows. Returns how many were deleted."""
    runs = db.query(models.RunHistory).filter(
        models.RunHistory.id.in_(run_ids),
        models.RunHistory.user_id == user_id,
    ).all()
    if not runs:
        return 0

    delete_run_reports([run.s3_object_key for run in runs])
    for run in runs:
        db.delete(run)
    db.commit()
    return len(runs)
