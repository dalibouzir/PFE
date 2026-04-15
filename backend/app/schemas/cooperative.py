from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel


class CooperativeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    region: str = Field(min_length=2, max_length=120)
    address: str = Field(min_length=2, max_length=255)
    phone: str = Field(min_length=3, max_length=32)
    status: str = Field(default="active")


class CooperativeRead(ORMModel):
    id: UUID
    name: str
    region: str
    address: str
    phone: str
    status: str
    created_at: datetime
    updated_at: datetime
