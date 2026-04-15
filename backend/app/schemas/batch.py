from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel


class BatchCreate(BaseModel):
    product_id: UUID
    code: str = Field(min_length=2, max_length=80)
    creation_date: date
    initial_qty: float = Field(gt=0)


class BatchStatusUpdate(BaseModel):
    status: str


class BatchRead(ORMModel):
    id: UUID
    cooperative_id: UUID
    product_id: UUID
    code: str
    creation_date: date
    initial_qty: float
    current_qty: float
    status: str
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class BatchMetricsSummary(BaseModel):
    batch_id: UUID
    total_input: float
    final_output: float
    total_loss_pct: float
    total_efficiency_pct: float
    completed_steps: int
    latest_step_id: Optional[UUID] = None
