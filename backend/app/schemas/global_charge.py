from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel


class GlobalChargeCreate(BaseModel):
    farmer_id: UUID = Field(alias="member_id")
    parcel_id: Optional[UUID] = None
    charge_type: str = Field(min_length=2, max_length=80)
    label: str = Field(min_length=2, max_length=255)
    amount_fcfa: float = Field(gt=0)
    date: date
    notes: Optional[str] = Field(default=None, max_length=1000)

    model_config = {
        "populate_by_name": True,
    }


class GlobalChargeUpdate(BaseModel):
    parcel_id: Optional[UUID] = None
    charge_type: Optional[str] = Field(default=None, min_length=2, max_length=80)
    label: Optional[str] = Field(default=None, min_length=2, max_length=255)
    amount_fcfa: Optional[float] = Field(default=None, gt=0)
    date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class GlobalChargeRead(ORMModel):
    id: UUID
    cooperative_id: UUID
    member_id: UUID
    parcel_id: Optional[UUID]
    pre_harvest_step_id: Optional[UUID]
    batch_id: Optional[UUID]
    process_step_id: Optional[UUID]
    charge_type: str
    label: str
    amount_fcfa: float
    date: date
    notes: Optional[str]
    source_type: str
    treasury_transaction_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime


class FarmerChargesResponse(BaseModel):
    total_amount_fcfa: float
    items: list[GlobalChargeRead]
