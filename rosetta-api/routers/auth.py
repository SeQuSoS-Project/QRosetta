"""Account routes: register, token login, logout, and account deletion."""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

import db.models as models
import schemas
import services.accounts as accounts
from db.database import get_db
from services.security import create_access_token, get_current_user
from config import settings
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-auth")

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Create an account with an email and password. 400 if the email is already registered."""
    try:
        return accounts.register(db, user.email, user.password)
    except accounts.EmailAlreadyRegistered:
        raise HTTPException(status_code=400, detail="Email already registered")


@router.post("/token", response_model=schemas.Token)
def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db)
):
    """Exchange an email + password (sent as OAuth2 password-grant form fields, username =
    email) for a bearer access token. 401 on an unrecognized email or wrong password, 403 on
    a deactivated account."""
    try:
        user = accounts.authenticate(db, form_data.username, form_data.password)
    except accounts.AccountDeactivated:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated",
        )
    except accounts.InvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=schemas.UserResponse)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    """Return the account for the bearer token in the Authorization header."""
    return current_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_me(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Permanently delete the account for the bearer token in the Authorization header,
    along with its saved circuits and run history (including each run's stored report)."""
    try:
        accounts.delete_account(db, current_user)
    except accounts.StoredReportsNotDeleted:
        raise HTTPException(status_code=500, detail="Failed to delete stored run reports")
    except Exception:
        logger.error("Failed to delete account", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete account")
    return None
