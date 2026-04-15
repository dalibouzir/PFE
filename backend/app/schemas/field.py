from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel


class FieldCreate(BaseModel):
    member_id: UUID
    location: str = Field(min_length=2, max_length=255)
    area: float = Field(gt=0)
    soil_type: Optional[str] = Field(default=None, max_length=120)
    irrigation_type: Optional[str] = Field(default=None, max_length=120)


class FieldUpdate(BaseModel):
    member_id: Optional[UUID] = None
    location: Optional[str] = Field(default=None, min_length=2, max_length=255)
    area: Optional[float] = Field(default=None, gt=0)
    soil_type: Optional[str] = Field(default=None, max_length=120)
    irrigation_type: Optional[str] = Field(default=None, max_length=120)


class FieldRead(ORMModel):
    id: UUID
    member_id: UUID
    cooperative_id: UUID
    location: str
    area: float
    soil_type: Optional[str]
    irrigation_type: Optional[str]
    created_at: datetime
    updated_at: datetime
