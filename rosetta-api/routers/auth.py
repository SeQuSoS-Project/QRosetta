# FastAPI router endpoints for auth.

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

import db.models as models
import schemas
from db.database import get_db
from services.security import verify_password, get_password_hash, create_access_token, get_current_user
from services.storage import delete_run_reports
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
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user.password)
    new_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        auth_provider="local"
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/token", response_model=schemas.Token)
def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db)
):
    """Exchange an email + password (sent as OAuth2 password-grant form fields, username =
    email) for a bearer access token. 401 on an unrecognized email, a wrong password, or a
    deactivated account."""

    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated",
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
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
    run_records = db.query(models.RunHistory).filter(models.RunHistory.user_id == current_user.id).all()
    s3_keys = [r.s3_object_key for r in run_records]

    if s3_keys:
        try:
            delete_run_reports(s3_keys)
        except Exception:
            logger.error("Failed to delete stored run reports during account deletion", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to delete stored run reports")

    try:
        for run in run_records:
            db.delete(run)

        circuits = db.query(models.SavedCircuit).filter(models.SavedCircuit.user_id == current_user.id).all()
        for circuit in circuits:
            db.delete(circuit)

        db.delete(current_user)
        db.commit()
    except Exception:
        db.rollback()
        logger.error("Failed to delete account", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete account")
    return None
