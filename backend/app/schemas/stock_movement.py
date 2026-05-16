from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class StockMovementRead(BaseModel):
    id: UUID
    cooperative_id: UUID
    cooperative_name: Optional[str]
    movement_reference: str
    movement_type: str
    action_type: str
    source: str
    source_label: str
    traceability_status: str
    product_id: UUID
    product_name: Optional[str]
    batch_id: Optional[UUID]
    batch_reference: Optional[str]
    input_id: Optional[UUID]
    input_reference: Optional[str]
    input_reference_bl: Optional[str]
    member_id: Optional[UUID]
    member_name: Optional[str]
    process_step_id: Optional[UUID]
    workflow_step_id: Optional[UUID]
    quantity_kg: float
    movement_date: date
    notes: Optional[str]
    idempotency_key: str
    created_at: datetime
    updated_at: datetime


class StockMovementDetailRead(StockMovementRead):
    pass
