from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel


class InputCreate(BaseModel):
    member_id: UUID
    product_id: UUID
    field_id: Optional[UUID] = None
    date: date
    quantity: float = Field(gt=0)
    grade: str = Field(min_length=1, max_length=40)
    estimated_value: Optional[float] = Field(default=None, ge=0)
    status: str = Field(default="pending")


class InputRead(ORMModel):
    id: UUID
    cooperative_id: UUID
    member_id: UUID
    product_id: UUID
    field_id: Optional[UUID]
    date: date
    quantity: float
    grade: str
    estimated_value: Optional[float]
    status: str
    created_at: datetime
    updated_at: datetime
