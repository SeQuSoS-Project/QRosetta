# Pydantic request/response models for the /auth endpoints.

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime

class UserCreate(BaseModel):
    """Request body for POST /auth/register."""
    email: str = Field(..., description="Account email; also used as the login username.")
    password: str = Field(..., description="Account password, stored only as a hash.")

class UserResponse(BaseModel):
    """An account, as returned by /auth/register and GET /auth/me."""
    id: int = Field(..., description="Unique account id.")
    email: str = Field(..., description="Account email.")
    auth_provider: str = Field(..., description="How the account authenticates, e.g. 'local' for email+password.")
    is_active: bool = Field(..., description="Whether the account is active.")
    created_at: datetime = Field(..., description="When the account was created.")

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    """Response body for POST /auth/token."""
    access_token: str = Field(..., description="Bearer token to send as 'Authorization: Bearer <token>' on authenticated requests.")
    token_type: str = Field(..., description="Always 'bearer'.")
