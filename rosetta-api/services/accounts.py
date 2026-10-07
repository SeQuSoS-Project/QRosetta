"""Account registration, authentication and deletion.

Raises the exceptions below; routers/auth.py maps them to HTTP status codes.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

import db.models as models
from qrosetta_commons.helpers import get_logger
from services.security import get_password_hash, verify_password
from services.share_links import delete_links
from services.storage import delete_run_reports

logger = get_logger("rosetta-accounts")


class EmailAlreadyRegistered(ValueError):
    """An account already exists for this email."""


class InvalidCredentials(ValueError):
    """Unknown email, or the password did not match."""


class AccountDeactivated(ValueError):
    """The account exists but has been deactivated."""


class StoredReportsNotDeleted(RuntimeError):
    """The account's stored run reports could not be removed, so nothing was deleted."""


def _find_by_email(db: Session, email: str):
    """Account whose email matches case-insensitively."""
    return db.query(models.User).filter(
        func.lower(models.User.email) == email.strip().lower()).first()


def register(db: Session, email: str, password: str) -> models.User:
    """Create a local account; the email is stored lower-cased."""
    email = email.strip().lower()
    if _find_by_email(db, email):
        raise EmailAlreadyRegistered(email)

    user = models.User(
        email=email,
        hashed_password=get_password_hash(password),
        auth_provider="local",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> models.User:
    """Return the user for these credentials.

    Unknown email and wrong password raise the same InvalidCredentials, so the response
    does not reveal which addresses are registered. The email matches case-insensitively.
    """
    user = _find_by_email(db, email)
    if not user or not user.hashed_password:
        raise InvalidCredentials(email)
    if not verify_password(password, user.hashed_password):
        raise InvalidCredentials(email)
    if not user.is_active:
        raise AccountDeactivated(email)
    return user


def delete_account(db: Session, user: models.User) -> None:
    """Delete the account, its saved circuits, and its run history.

    The rows are deleted and flushed first, then the stored reports, then the transaction
    is committed: if either step fails it is rolled back and nothing is deleted from the
    database. Child rows are deleted explicitly because the foreign keys have no ON DELETE
    CASCADE; another account's run that names one of these circuits loses the link.
    """
    runs = db.query(models.RunHistory).filter(models.RunHistory.user_id == user.id).all()
    s3_keys = [r.s3_object_key for r in runs]

    try:
        delete_links(db, [r.id for r in runs])
        for run in runs:
            db.delete(run)

        circuits = db.query(models.SavedCircuit).filter(
            models.SavedCircuit.user_id == user.id).all()
        if circuits:
            db.query(models.RunHistory).filter(
                models.RunHistory.circuit_id.in_([c.id for c in circuits])).update(
                {models.RunHistory.circuit_id: None}, synchronize_session=False)
        for circuit in circuits:
            db.delete(circuit)

        db.delete(user)
        db.flush()
    except Exception:
        db.rollback()
        logger.error("Failed to delete account", exc_info=True)
        raise

    try:
        delete_run_reports(s3_keys)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to delete stored run reports during account deletion",
                     exc_info=True)
        raise StoredReportsNotDeleted(str(exc)) from exc

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.error("Failed to delete account", exc_info=True)
        raise
