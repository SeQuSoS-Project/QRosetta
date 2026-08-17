# Security utilities like password hashing and JWT.

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

import secrets
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt

from config import settings


def _resolve_secret_key() -> str:
    """Return the JWT signing key, refusing to start a non-local deployment without one.

    Outside EXECUTION_MODE=local an unset SECRET_KEY is fatal: tokens signed with a
    predictable key can be forged. Local development generates a random per-process key,
    which invalidates existing sessions on restart.
    """
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

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password):
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session
from db.database import get_db
import db.models as models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
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
    if user is None:
        raise credentials_exception
    if not user.is_active:
        # A token issued before deactivation stops working immediately.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been deactivated")
    return user
