"""Auth-related schemas."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from models.user import Role


class LoginRequest(BaseModel):
    email: str = Field(..., description="User email")
    password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    tenant_id: str
    expires_in: int = 3600  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class UserCreate(BaseModel):
    email: str
    password: str = Field(..., min_length=8)
    full_name: str
    role: Role = Role.EMPLOYEE
    department: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: Role
    department: Optional[str]
    tenant_id: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
