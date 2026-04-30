from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel


class PreHarvestStepRead(ORMModel):
    id: UUID
    cooperative_id: UUID
    parcel_id: UUID
    member_id: UUID
    step_order: int
    step_key: str
    category: str
    label: str
    icon: str
    status: str
    quantity_value: Optional[float]
    quantity_unit: Optional[str]
    operation_cost_fcfa: Optional[float]
    realization_date: Optional[date]
    observations: Optional[str]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class PreHarvestStepUpdate(BaseModel):
    quantity_value: Optional[float] = Field(default=None, ge=0)
    quantity_unit: Optional[str] = Field(default=None, max_length=32)
    operation_cost_fcfa: Optional[float] = Field(default=None, ge=0)
    realization_date: date
    observations: Optional[str] = Field(default=None, max_length=1000)


class PreHarvestInitResponse(BaseModel):
    parcel_id: UUID
    created_steps: int
