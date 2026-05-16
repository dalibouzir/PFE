from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel


class CooperativeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    region: str = Field(min_length=2, max_length=120)
    address: str = Field(min_length=2, max_length=255)
    phone: str = Field(min_length=3, max_length=32)
    status: str = Field(default="active")
    institution_id: Optional[UUID] = None


class CooperativeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    region: Optional[str] = Field(default=None, min_length=2, max_length=120)
    address: Optional[str] = Field(default=None, min_length=2, max_length=255)
    phone: Optional[str] = Field(default=None, min_length=3, max_length=32)
    status: Optional[str] = None
    institution_id: Optional[UUID] = None


class CooperativeRead(ORMModel):
    id: UUID
    name: str
    region: str
    address: str
    phone: str
    status: str
    institution_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime
