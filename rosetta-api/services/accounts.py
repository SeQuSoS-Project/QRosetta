"""Account registration, authentication and deletion.

Raises the exceptions below; routers/auth.py maps them to HTTP status codes.
"""

from sqlalchemy.orm import Session

import db.models as models
from qrosetta_commons.helpers import get_logger
from services.security import get_password_hash, verify_password
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


def register(db: Session, email: str, password: str) -> models.User:
    if db.query(models.User).filter(models.User.email == email).first():
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
    does not reveal which addresses are registered.
    """
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not user.hashed_password:
        raise InvalidCredentials(email)
    if not verify_password(password, user.hashed_password):
        raise InvalidCredentials(email)
    if not user.is_active:
        raise AccountDeactivated(email)
    return user


def delete_account(db: Session, user: models.User) -> None:
    """Delete the account, its saved circuits, and its run history.

    Stored reports are deleted first; if that fails nothing else is deleted. Child rows
    are deleted explicitly because the foreign keys have no ON DELETE CASCADE.
    """
    runs = db.query(models.RunHistory).filter(models.RunHistory.user_id == user.id).all()
    s3_keys = [r.s3_object_key for r in runs]

    if s3_keys:
        try:
            delete_run_reports(s3_keys)
        except Exception as exc:
            logger.error("Failed to delete stored run reports during account deletion",
                         exc_info=True)
            raise StoredReportsNotDeleted(str(exc)) from exc

    try:
        for run in runs:
            db.delete(run)

        circuits = db.query(models.SavedCircuit).filter(
            models.SavedCircuit.user_id == user.id).all()
        for circuit in circuits:
            db.delete(circuit)

        db.delete(user)
        db.commit()
    except Exception:
        db.rollback()
        logger.error("Failed to delete account", exc_info=True)
        raise
