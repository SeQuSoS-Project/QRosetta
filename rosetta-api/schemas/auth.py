# Pydantic request/response models for the /auth endpoints.

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from schemas.timestamps import UtcDatetime

EMAIL_MAX_LENGTH = 254
PASSWORD_MIN_CHARS = 8
PASSWORD_MAX_BYTES = 72

_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}"
    r"@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def normalize_email(email: str) -> str:
    """Trimmed, lower-cased email, the form accounts are stored and looked up by."""
    return email.strip().lower()


def password_too_long(password: str) -> bool:
    """True when the UTF-8 password exceeds bcrypt's 72-byte input limit."""
    return len(password.encode("utf-8")) > PASSWORD_MAX_BYTES


class UserCreate(BaseModel):
    """Request body for POST /auth/register."""
    model_config = ConfigDict(extra="forbid")

    email: str = Field(..., description=f"Account email, at most {EMAIL_MAX_LENGTH} characters; also the login username. Stored lower-cased, so addresses differing only in case are the same account.")
    password: str = Field(..., description=f"Account password, at least {PASSWORD_MIN_CHARS} characters and at most {PASSWORD_MAX_BYTES} bytes as UTF-8; stored only as a bcrypt hash.")

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        email = normalize_email(value)
        if len(email) > EMAIL_MAX_LENGTH:
            raise ValueError(f"email must be at most {EMAIL_MAX_LENGTH} characters")
        if not _EMAIL_RE.match(email):
            raise ValueError("email must be a valid address such as name@example.org")
        return email

    @field_validator("password")
    @classmethod
    def _valid_password(cls, value: str) -> str:
        if len(value) < PASSWORD_MIN_CHARS:
            raise ValueError(f"password must be at least {PASSWORD_MIN_CHARS} characters")
        if password_too_long(value):
            raise ValueError(f"password must be at most {PASSWORD_MAX_BYTES} bytes (UTF-8)")
        return value

class UserResponse(BaseModel):
    """An account, as returned by /auth/register and GET /auth/me."""
    id: int = Field(..., description="Unique account id.")
    email: str = Field(..., description="Account email.")
    auth_provider: str = Field(..., description="How the account authenticates, e.g. 'local' for email+password.")
    is_active: bool = Field(..., description="Whether the account is active.")
    created_at: UtcDatetime = Field(..., description="When the account was created, UTC ISO 8601 ending in 'Z'.")

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    """Response body for POST /auth/token."""
    access_token: str = Field(..., description="Bearer token to send as 'Authorization: Bearer <token>' on authenticated requests.")
    token_type: str = Field(..., description="Always 'bearer'.")
