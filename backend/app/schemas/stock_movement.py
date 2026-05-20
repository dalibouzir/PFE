from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field


class StockMovementRead(BaseModel):
    id: UUID
    cooperative_id: UUID
    cooperative_name: Optional[str]
    movement_reference: str
    preharvest_reference: Optional[str] = None
    collecte_reference: Optional[str] = None
    postharvest_reference: Optional[str] = None
    movement_type: str
    action_type: str
    source: str
    source_label: str
    traceability_status: str
    product_id: UUID
    grade: str
    product_name: Optional[str]
    batch_id: Optional[UUID]
    batch_reference: Optional[str]
    input_id: Optional[UUID]
    input_reference: Optional[str]
    input_reference_bl: Optional[str]
    member_id: Optional[UUID]
    member_name: Optional[str]
    actor_name: Optional[str] = None
    process_step_id: Optional[UUID]
    process_step_type: Optional[str] = None
    workflow_step_id: Optional[UUID]
    quantity_kg: float
    movement_date: date
    notes: Optional[str]
    idempotency_key: str
    created_at: datetime
    updated_at: datetime


class StockMovementDetailRead(StockMovementRead):
    pass


class ManualStockMovementCreate(BaseModel):
    product_id: UUID
    grade: str = Field(default="Non spécifié", min_length=1, max_length=40)
    movement_type: str = Field(min_length=1, max_length=16)
    correction_direction: Optional[str] = Field(default=None, max_length=16)
    quantity_kg: float = Field(gt=0)
    notes: str = Field(min_length=1, max_length=2000)
