from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthUserResponse(ORMModel):
    id: UUID
    full_name: str
    email: str
    phone: Optional[str]
    role: str
    status: str
    cooperative_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime
