# Password hashing, JWT tokens, the rate limiter and the get_current_user dependency.

from slowapi import Limiter
from slowapi.util import get_remote_address


def client_address(request) -> str:
    """Client IP as recorded by the nearest proxy (X-Real-IP, else last X-Forwarded-For hop)."""
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=client_address)

import secrets
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt

from config import settings


def _resolve_secret_key() -> str:
    """Return SECRET_KEY; raise outside local mode if unset, else generate a per-process key."""
    if settings.SECRET_KEY:
        return settings.SECRET_KEY
    if settings.EXECUTION_MODE != "local":
        raise RuntimeError(
            "SECRET_KEY is required when EXECUTION_MODE is not 'local'. "
            "Set the SECRET_KEY environment variable before deploying."
        )
    import logging as _logging
    _logging.getLogger("rosetta-security").warning(
        "SECRET_KEY is unset; generating an ephemeral key for local development. "
        "Sessions will not survive a restart."
    )
    return secrets.token_urlsafe(64)


SECRET_KEY = _resolve_secret_key()

ALGORITHM = "HS256"

BCRYPT_MAX_PASSWORD_BYTES = 72


def verify_password(plain_password, hashed_password):
    """False for a wrong password, including one longer than bcrypt's 72-byte limit."""
    encoded = plain_password.encode('utf-8')
    if len(encoded) > BCRYPT_MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(encoded, hashed_password.encode('utf-8'))

def get_password_hash(password):
    """bcrypt hash; ValueError for a password longer than 72 bytes (UTF-8)."""
    if len(password.encode('utf-8')) > BCRYPT_MAX_PASSWORD_BYTES:
        raise ValueError(f"password must be at most {BCRYPT_MAX_PASSWORD_BYTES} bytes (UTF-8)")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Signed JWT carrying ``data`` plus ``iat`` (issue time, integer seconds) and ``exp``
    (default 15 minutes after issue)."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    to_encode.update({"iat": int(now.timestamp()),
                      "exp": now + (expires_delta or timedelta(minutes=15))})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def access_token_for(user, expires_delta: timedelta | None = None) -> str:
    """Access token bound to ``user``: ``sub`` is the email and ``uid`` the account id."""
    return create_access_token({"sub": user.email, "uid": user.id}, expires_delta)


TOKEN_CLOCK_TOLERANCE_SEC = 2


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def token_matches_account(payload: dict, user) -> bool:
    """True when the token's ``uid`` is ``user.id`` and the account existed when the token
    was issued (``created_at`` at most TOKEN_CLOCK_TOLERANCE_SEC after ``iat``). A token
    without ``uid`` or ``iat`` does not match."""
    uid, iat = payload.get("uid"), payload.get("iat")
    if isinstance(uid, bool) or not isinstance(uid, int) or uid != user.id:
        return False
    if isinstance(iat, bool) or not isinstance(iat, (int, float)):
        return False
    created = getattr(user, "created_at", None)
    if created is None:
        return True
    return _as_utc(created).timestamp() <= iat + TOKEN_CLOCK_TOLERANCE_SEC

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session
from db.database import get_db
import db.models as models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

_optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token", auto_error=False)


def get_optional_user(token: str | None = Depends(_optional_oauth2_scheme), db: Session = Depends(get_db)):
    """The signed-in account when the request carries a valid bearer token, else None (an
    absent, invalid or expired token makes the request anonymous rather than failing it)."""
    if not token:
        return None
    try:
        return get_current_user(token, db)
    except HTTPException:
        return None


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """The account a bearer token was issued to. 401 for an invalid or expired token, one
    whose ``uid`` is not the account now registered under its email, or one issued before
    that account was created; 403 for a deactivated account."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None or not token_matches_account(payload, user):
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been deactivated")
    return user
