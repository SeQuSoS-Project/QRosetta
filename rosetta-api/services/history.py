"""Saved circuits and run history: database access and report storage.

Every lookup filters by user_id. A missing or foreign run raises RunNotFound (a
ValueError), which the router turns into a 404.
"""

import uuid

from sqlalchemy.orm import Session

import db.models as models
from qrosetta_commons.helpers import get_logger
from schemas.timestamps import utc_iso
from services.share_links import delete_links
from services.storage import delete_run_reports, fetch_run_report, save_run_report

logger = get_logger("rosetta-history")


class RunNotFound(ValueError):
    """No run with that id belongs to this user."""


def create_circuit(db: Session, user_id: int, name: str, qasm_string: str) -> models.SavedCircuit:
    """Store a named circuit for ``user_id``."""
    circuit = models.SavedCircuit(user_id=user_id, name=name, qasm_string=qasm_string)
    db.add(circuit)
    db.commit()
    db.refresh(circuit)
    return circuit


def list_circuits(db: Session, user_id: int) -> list:
    """All circuits saved by ``user_id``."""
    return db.query(models.SavedCircuit).filter(models.SavedCircuit.user_id == user_id).all()


def _owned_run(db: Session, user_id: int, run_id: str) -> models.RunHistory:
    run = db.query(models.RunHistory).filter(
        models.RunHistory.id == run_id,
        models.RunHistory.user_id == user_id,
    ).first()
    if not run:
        raise RunNotFound(run_id)
    return run


def find_run(db: Session, user_id: int, run_id: str | None):
    """``user_id``'s run with ``run_id``, or None when there is none."""
    if not run_id:
        return None
    try:
        return _owned_run(db, user_id, run_id)
    except RunNotFound:
        return None


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
    """All runs saved by ``user_id`` (metadata rows)."""
    return db.query(models.RunHistory).filter(models.RunHistory.user_id == user_id).all()


def get_run_report(db: Session, user_id: int, run_id: str) -> dict:
    """The stored report of one of ``user_id``'s runs."""
    run = _owned_run(db, user_id, run_id)
    return fetch_run_report(run.s3_object_key)


def get_run_report_with_metadata(db: Session, user_id: int, run_id: str) -> dict:
    """The stored report with ``run_id``, ``run_name`` and ``created_at`` (UTC, 'Z') added."""
    run = _owned_run(db, user_id, run_id)
    report = fetch_run_report(run.s3_object_key)
    if not isinstance(report, dict):
        return report
    return {**report, "run_id": run.id, "run_name": run.run_name,
            "created_at": utc_iso(run.created_at) if run.created_at else None}


def _single_report_problems(report, where: str) -> list:
    if not isinstance(report, dict):
        return [(where, "must be an object")]
    problems = []
    raw = report.get("raw_results")
    if raw is None and "error" not in report:
        problems.append((where + ["raw_results"], "a single-circuit report needs raw_results (a list of runner results) or a top-level error"))
    elif raw is not None:
        if not isinstance(raw, list):
            problems.append((where + ["raw_results"], "must be a list of runner results"))
        elif not all(isinstance(r, dict) for r in raw):
            problems.append((where + ["raw_results"], "every runner result must be an object"))
    for key in ("divergence_report", "performance_report", "resource_report"):
        if key in report and not isinstance(report[key], dict):
            problems.append((where + [key], "must be an object"))
    return problems


def report_structure_problems(report) -> list:
    """``[(loc, msg)]`` for a report that is neither a single-circuit report (``raw_results``
    list, optional ``divergence_report`` object) nor a batch report (``benchmark_summary``
    list of single-circuit reports or task errors). Empty when the structure is valid."""
    if not isinstance(report, dict):
        return [(["body"], "the report must be a JSON object")]
    if "benchmark_summary" in report:
        tasks = report["benchmark_summary"]
        if not isinstance(tasks, list):
            return [(["body", "benchmark_summary"], "must be a list of task reports")]
        problems = []
        for i, task in enumerate(tasks):
            problems += _single_report_problems(task, ["body", "benchmark_summary", i])
        return problems
    if "raw_results" not in report and "divergence_report" not in report:
        return [(["body"], "not a run report: expected raw_results (single circuit) or benchmark_summary (batch)")]
    return _single_report_problems(report, ["body"])


def default_run_name(report: dict, job_id: str) -> str:
    """``"<mode> run <job id prefix>"``, with mode batch, measured or statevector."""
    if isinstance(report, dict) and "benchmark_summary" in report:
        mode = f"{report.get('mode', '')} batch".strip()
    elif isinstance(report, dict) and "n_shots" in report:
        mode = "measured"
    else:
        mode = "statevector"
    return f"{mode} run {job_id[:8]}"


def rename_run(db: Session, user_id: int, run_id: str, run_name: str) -> models.RunHistory:
    """Rename one of ``user_id``'s runs."""
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
    delete_links(db, [run.id for run in runs])
    for run in runs:
        db.delete(run)
    db.commit()
    return len(runs)
