"""Account routes: register, token login, sign-out, password change, and account deletion."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

import db.models as models
import schemas
import services.accounts as accounts
from db.database import get_db
from services.security import access_token_for, address_key, get_current_user, limiter, rate_limit_key
from config import settings
from routers.errors import responses
from services.security_events import email_digest, security_event
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-auth")

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED,
             responses=responses((400, "The email is already registered (compared case-insensitively)."), 422))
@limiter.limit(settings.REGISTER_RATE_LIMIT, key_func=address_key)
def register(request: Request, user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Create an account with an email and password. 422 for an invalid email (format, over
    254 characters) or password (under 8 characters, over 72 bytes); 400 if the email is
    already registered, compared case-insensitively. Limited per client address
    (``limits.register_rate_limit`` in GET /config, 5 a minute by default)."""
    try:
        created = accounts.register(db, user.email, user.password)
    except accounts.EmailAlreadyRegistered:
        security_event("auth.register_refused", request, reason="email_registered",
                       email_sha256=email_digest(user.email))
        raise HTTPException(status_code=400, detail="Email already registered")
    security_event("auth.register", request, user_id=created.id)
    return created


@router.post("/token", response_model=schemas.Token, responses=responses(
    (400, "Password over 72 bytes (UTF-8), or a form of more than 1,000 fields."),
    (401, "Unrecognised email or wrong password. Sent with WWW-Authenticate: Bearer."),
    (403, "The account is deactivated."), 422))
@limiter.limit(settings.LOGIN_RATE_LIMIT, key_func=address_key)
def login_for_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db)
):
    """Exchange an email + password (sent as OAuth2 password-grant form fields, username =
    email, matched case-insensitively) for a bearer access token valid for ``expires_in``
    seconds (1800 by default); there is no refresh token. 400 for a password over
    72 bytes or a form of more than 1,000 fields, 401 on an unrecognized email or wrong
    password, 403 on a deactivated account. Empty fields count as missing (422).
    Limited per client address, whatever bearer token the request carries
    (``limits.login_rate_limit`` in GET /config, 10 a minute by default); every attempt that
    passes form validation counts, successful or not."""
    if schemas.password_too_long(form_data.password):
        security_event("auth.login_failed", request, reason="password_too_long",
                       email_sha256=email_digest(form_data.username))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at most {schemas.PASSWORD_MAX_BYTES} bytes (UTF-8)",
        )
    try:
        user = accounts.authenticate(db, form_data.username, form_data.password)
    except accounts.AccountDeactivated:
        security_event("auth.login_failed", request, reason="deactivated",
                       email_sha256=email_digest(form_data.username))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated",
        )
    except accounts.InvalidCredentials:
        security_event("auth.login_failed", request, reason="credentials",
                       email_sha256=email_digest(form_data.username))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    security_event("auth.login", request, user_id=user.id)
    return _token_response(user)


def _token_response(user) -> dict:
    access_token = access_token_for(
        user, expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    return {"access_token": access_token, "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, responses=responses(
    (401, "The token is invalid, expired, or was issued before the account's last sign-out or password change."),
    (403, "The account is deactivated.")))
@limiter.limit(settings.LOGIN_RATE_LIMIT, key_func=rate_limit_key)
def logout(request: Request, current_user: models.User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    """Sign the account out everywhere: every access token issued to it until now, on any
    browser or command line, is refused from now on (401). Signing in again issues a new token.
    Limited per account at the sign-in rate (``limits.login_rate_limit``)."""
    accounts.sign_out(db, current_user)
    security_event("auth.logout", request, user_id=current_user.id)
    return None


@router.post("/password", response_model=schemas.Token, responses=responses(
    (401, "The token is invalid, expired, or was issued before the account's last sign-out or password change."),
    (403, "The current password does not match, or the account is deactivated."), 422))
@limiter.limit(settings.LOGIN_RATE_LIMIT, key_func=rate_limit_key)
def change_password(request: Request, body: schemas.PasswordChange,
                    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Replace the account's password. The body carries the current password (403 when it does
    not match, nothing changed) and the new one (422 under 8 characters or over 72 bytes).
    Every access token issued before the change is refused from then on; the answer carries a
    new token for the caller. Limited per account at the sign-in rate
    (``limits.login_rate_limit``); every attempt counts."""
    try:
        accounts.change_password(db, current_user, body.current_password, body.new_password)
    except accounts.InvalidCredentials:
        security_event("auth.password_change_failed", request, user_id=current_user.id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incorrect password")
    security_event("auth.password_changed", request, user_id=current_user.id)
    return _token_response(current_user)


@router.get("/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    """Return the account for the bearer token in the Authorization header."""
    return current_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, responses=responses(
    (403, "The password does not match the account's."), 422))
@limiter.limit(settings.LOGIN_RATE_LIMIT, key_func=rate_limit_key)
def delete_user_me(request: Request, body: schemas.AccountDeletion,
                   current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Permanently delete the account for the bearer token in the Authorization header,
    along with its saved circuits and run history (including each run's stored report).
    The body carries the account's current password; 403 when it does not match, and
    nothing is deleted. Limited per account at the sign-in rate
    (``limits.login_rate_limit``); every attempt counts."""
    try:
        accounts.confirm_password(current_user, body.password)
    except accounts.InvalidCredentials:
        security_event("auth.account_delete_failed", request, user_id=current_user.id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incorrect password")
    user_id = current_user.id
    try:
        accounts.delete_account(db, current_user)
    except accounts.StoredReportsNotDeleted:
        raise HTTPException(status_code=500, detail="Failed to delete stored run reports")
    except Exception:
        logger.error("Failed to delete account", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete account")
    security_event("auth.account_deleted", request, user_id=user_id)
    return None
