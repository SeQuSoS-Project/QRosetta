# Password hashing, JWT tokens, the rate limiter and its keys, and the get_current_user dependency.

import hmac

from slowapi import Limiter
from slowapi.util import get_remote_address

from config import settings

PROXY_CLIENT_HEADER = "x-qrosetta-client-ip"
PROXY_TOKEN_HEADER = "x-qrosetta-proxy-token"


def client_address(request) -> str:
    """Client IP for rate limits and the exclusive slot.

    A request carrying QROSETTA_PROXY_TOKEN (sent by the Cloud Run frontend) is keyed by the
    address that proxy saw (X-Qrosetta-Client-Ip). Any other is keyed by the last
    X-Forwarded-For entry, which the nearest proxy (local nginx, the OpenShift router)
    appends and a caller cannot set, else by the socket peer. X-Real-IP is not read: the
    OpenShift router passes a caller's own value through.
    """
    token = settings.PROXY_TOKEN
    if token:
        sent = request.headers.get(PROXY_TOKEN_HEADER, "")
        proxied = request.headers.get(PROXY_CLIENT_HEADER, "").strip()
        if proxied and hmac.compare_digest(sent.encode(), token.encode()):
            return proxied
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        last = forwarded.split(",")[-1].strip()
        if last:
            return last
    return get_remote_address(request)


import secrets
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt


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


RATE_KEY_STATE = "qrosetta_rate_key"


def address_key(request) -> str:
    """Rate-limit key of the client address: login, registration and share-link reads."""
    return "address:" + client_address(request)


def address_ceiling_key(request) -> str:
    """Rate-limit key of the per-address ceiling on expensive routes, counted apart from the
    address's own budget."""
    return "address-ceiling:" + client_address(request)


def _bearer_token(request) -> str:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


def _signed_account_id(token: str):
    """The ``uid`` of a token with a valid signature, ``exp``, ``iat`` and ``sub``, else None.
    The database is not read."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM],
                             options={"require": ["exp", "iat", "sub"]})
    except jwt.PyJWTError:
        return None
    uid = payload.get("uid")
    if isinstance(uid, bool) or not isinstance(uid, int):
        return None
    if not isinstance(payload.get("sub"), str):
        return None
    return uid


def rate_limit_key(request) -> str:
    """Rate-limit key: ``account:<id>`` for a bearer token signed by this server and not
    expired, ``lifecycle`` for the local lifecycle token, else ``address:<client address>``.
    A token of a deactivated or deleted account keys on its id until it expires."""
    cached = getattr(request.state, RATE_KEY_STATE, None)
    if cached:
        return cached
    key = None
    token = _bearer_token(request)
    if token:
        uid = _signed_account_id(token)
        if uid is not None:
            key = f"account:{uid}"
        else:
            from services.lifecycle_token import matches_lifecycle_token
            if matches_lifecycle_token(token):
                key = "lifecycle"
    key = key or address_key(request)
    setattr(request.state, RATE_KEY_STATE, key)
    return key


class TightestLimiter(Limiter):
    """slowapi Limiter that reports, on a request within every limit of its route, the limit
    with the fewest requests left (slowapi reports the first one evaluated). Counters are
    per route (``key_style="endpoint"``), so path parameters do not split a budget."""

    def __init__(self, **kwargs):
        super().__init__(key_style="endpoint", **kwargs)

    def _check_request_limit(self, request, endpoint_func, in_middleware=True):
        super()._check_request_limit(request, endpoint_func, in_middleware)
        if endpoint_func is None or not self.enabled:
            return
        name = f"{endpoint_func.__module__}.{endpoint_func.__name__}"
        limits = self._route_limits.get(name, [])
        if len(limits) < 2:
            return
        scope = request["path"] if self._key_style == "url" else name
        tightest = None
        for lim in limits:
            args = [lim.key_func(request), lim.scope or scope]
            if self._key_prefix:
                args = [self._key_prefix] + args
            _, remaining = self.limiter.get_window_stats(lim.limit, *args)
            if tightest is None or remaining < tightest[0]:
                tightest = (remaining, (lim.limit, args))
        request.state.view_rate_limit = tightest[1]


limiter = TightestLimiter(key_func=rate_limit_key)


def limit_with_address_ceiling(limit_value: str, ceiling: str):
    """Route decorator: ``limit_value`` per rate_limit_key and ``ceiling`` per client address
    (address_ceiling_key); a request must be within both. The key's own limit is counted
    first, so a key over its limit does not use the address's ceiling."""
    def decorate(func):
        return limiter.limit(ceiling, key_func=address_ceiling_key)(limiter.limit(limit_value)(func))
    return decorate


run_rate_limit = limit_with_address_ceiling(settings.RUN_RATE_LIMIT, settings.RUN_RATE_LIMIT_PER_ADDRESS)
render_rate_limit = limit_with_address_ceiling(settings.RENDER_RATE_LIMIT,
                                               settings.RENDER_RATE_LIMIT_PER_ADDRESS)


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
    except jwt.PyJWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None or not token_matches_account(payload, user):
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been deactivated")
    return user
