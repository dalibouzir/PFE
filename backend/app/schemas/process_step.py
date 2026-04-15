from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel


class ProcessStepCreate(BaseModel):
    batch_id: UUID
    type: str = Field(min_length=2, max_length=80)
    date: date
    qty_in: float = Field(gt=0)
    qty_out: float = Field(ge=0)
    waste_qty: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=1000)
    status: str = Field(default="pending")
    duration_minutes: Optional[int] = Field(default=None, ge=0)


class ProcessStepUpdate(BaseModel):
    type: Optional[str] = Field(default=None, min_length=2, max_length=80)
    date: Optional[date] = None
    qty_in: Optional[float] = Field(default=None, gt=0)
    qty_out: Optional[float] = Field(default=None, ge=0)
    waste_qty: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[str] = None
    duration_minutes: Optional[int] = Field(default=None, ge=0)


class ProcessStepCompleteRequest(BaseModel):
    mark_batch_completed: bool = False


class ProcessStepRead(ORMModel):
    id: UUID
    batch_id: UUID
    type: str
    date: date
    qty_in: float
    qty_out: float
    waste_qty: float
    notes: Optional[str]
    status: str
    duration_minutes: Optional[int]
    created_at: datetime
    updated_at: datetime
    loss_pct: float
    efficiency_pct: float
    warning: bool
