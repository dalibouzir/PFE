from __future__ import annotations

from datetime import date as date_type, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel


class ProcessStepCreate(BaseModel):
    batch_id: UUID
    type: Optional[str] = Field(default=None, min_length=2, max_length=80)
    date: Optional[date_type] = None
    loss_value: float = Field(ge=0)
    loss_unit: str = Field(default="kg", min_length=1, max_length=16)
    notes: Optional[str] = Field(default=None, max_length=1000)
    duration_minutes: Optional[int] = Field(default=None, ge=0)


class ProcessStepUpdate(BaseModel):
    date: Optional[date_type] = None
    loss_value: Optional[float] = Field(default=None, ge=0)
    loss_unit: Optional[str] = Field(default=None, min_length=1, max_length=16)
    notes: Optional[str] = Field(default=None, max_length=1000)
    duration_minutes: Optional[int] = Field(default=None, ge=0)


class ProcessStepCompleteRequest(BaseModel):
    mark_batch_completed: bool = False


class ProcessStepRead(ORMModel):
    id: UUID
    batch_id: UUID
    sequence_order: int
    type: str
    date: date_type
    loss_value: float
    loss_unit: str
    normalized_loss_value: float
    qty_in: float
    qty_out: float
    waste_qty: float
    notes: Optional[str]
    status: str
    executed_at: Optional[datetime]
    duration_minutes: Optional[int]
    created_at: datetime
    updated_at: datetime
    loss_pct: float
    efficiency_pct: float
    warning: bool
