"""Read-only share links to the circuit texts of a saved run.

A link belongs to the account that saved the run. Only the SHA-256 of its token is stored;
the token itself is returned once, at creation. A link resolves while it is unexpired and
unrevoked, its owner is active and the run still exists; every other case is the same
ShareNotFound, so a caller cannot tell an unknown token from an expired one.
"""

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

import db.models as models
from qrosetta_commons.helpers import get_logger
from schemas.timestamps import utc_iso
from services.circuit_texts import circuit_texts
from services.storage import fetch_run_report

logger = get_logger("rosetta-share-links")

TOKEN_BYTES = 32
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
MAX_ACTIVE_LINKS_PER_RUN = 10
MIN_EXPIRY_DAYS = 1
MAX_EXPIRY_DAYS = 90
DEFAULT_EXPIRY_DAYS = 30


class RunNotFound(LookupError):
    """No run with that id belongs to this user."""


class ShareNotFound(LookupError):
    """No usable link for this token (unknown, expired, revoked, or its run is gone)."""


class TooManyLinks(ValueError):
    """The run already has MAX_ACTIVE_LINKS_PER_RUN active links."""


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _owned_run(db: Session, user_id: int, run_id: str):
    return db.query(models.RunHistory).filter(models.RunHistory.id == run_id,
                                              models.RunHistory.user_id == user_id).first()


def is_active(link: models.ShareLink, now: datetime | None = None) -> bool:
    return link.revoked_at is None and _as_utc(link.expires_at) > (now or _now())


def _active_links(db: Session, user_id: int, run_id: str) -> list:
    now = _now()
    links = db.query(models.ShareLink).filter(models.ShareLink.user_id == user_id,
                                              models.ShareLink.run_id == run_id).all()
    return [link for link in links if is_active(link, now)]


def create_link(db: Session, user_id: int, run_id: str, expires_in_days: int, label: str = None):
    """``(link, token)`` for a new link to one of ``user_id``'s runs. RunNotFound for a run
    that is not theirs; TooManyLinks past the per-run limit."""
    if not MIN_EXPIRY_DAYS <= expires_in_days <= MAX_EXPIRY_DAYS:
        raise ValueError(f"expires_in_days must be {MIN_EXPIRY_DAYS} to {MAX_EXPIRY_DAYS}")
    if _owned_run(db, user_id, run_id) is None:
        raise RunNotFound(run_id)
    if len(_active_links(db, user_id, run_id)) >= MAX_ACTIVE_LINKS_PER_RUN:
        raise TooManyLinks(run_id)
    token = secrets.token_urlsafe(TOKEN_BYTES)
    link = models.ShareLink(token_hash=_hash(token), user_id=user_id, run_id=run_id,
                            expires_at=_now() + timedelta(days=expires_in_days), label=label)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link, token


def list_links(db: Session, user_id: int, run_id: str) -> list:
    """Every link to one of ``user_id``'s runs, newest first. RunNotFound for a run that is
    not theirs."""
    if _owned_run(db, user_id, run_id) is None:
        raise RunNotFound(run_id)
    links = db.query(models.ShareLink).filter(models.ShareLink.user_id == user_id,
                                              models.ShareLink.run_id == run_id).all()
    return sorted(links, key=lambda link: _as_utc(link.expires_at), reverse=True)


def revoke_link(db: Session, user_id: int, link_id: str) -> models.ShareLink:
    """Revoke one of ``user_id``'s links (idempotent). ShareNotFound for a link that is not
    theirs."""
    link = db.query(models.ShareLink).filter(models.ShareLink.id == link_id,
                                             models.ShareLink.user_id == user_id).first()
    if link is None:
        raise ShareNotFound(link_id)
    if link.revoked_at is None:
        link.revoked_at = _now()
        db.commit()
        db.refresh(link)
    return link


def delete_links(db: Session, run_ids: list) -> None:
    """Delete the links to ``run_ids`` (part of deleting the runs; the caller commits)."""
    if run_ids:
        db.query(models.ShareLink).filter(models.ShareLink.run_id.in_(run_ids)).delete(
            synchronize_session=False)


def resolve(db: Session, token) -> dict:
    """The circuit texts a token links to, with the run's name, save time and the link's
    expiry. ShareNotFound when the token does not resolve."""
    if not isinstance(token, str) or not TOKEN_PATTERN.match(token):
        raise ShareNotFound()
    link = db.query(models.ShareLink).filter(models.ShareLink.token_hash == _hash(token)).first()
    if link is None or not is_active(link):
        raise ShareNotFound()
    owner = db.query(models.User).filter(models.User.id == link.user_id).first()
    run = _owned_run(db, link.user_id, link.run_id)
    if owner is None or not owner.is_active or run is None:
        raise ShareNotFound()
    try:
        report = fetch_run_report(run.s3_object_key)
    except Exception:
        logger.error(f"Stored report missing for shared run {run.id}", exc_info=True)
        raise ShareNotFound()
    from schemas.benchmark import printable_name
    source = report.get("saved_from") if isinstance(report, dict) else None
    return {**circuit_texts(report), "run_name": printable_name(run.run_name, run.id[:8]),
            "report_source": source if source in ("server_job", "upload") else "not_recorded",
            "saved_at": utc_iso(run.created_at) if run.created_at else None,
            "link_expires_at": utc_iso(_as_utc(link.expires_at))}
