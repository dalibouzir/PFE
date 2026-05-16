from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel


class FarmerAdvanceCreate(BaseModel):
    farmer_id: UUID
    batch_id: Optional[UUID] = None
    parcel_id: Optional[UUID] = None
    product_id: Optional[UUID] = None
    source_type: Optional[str] = Field(default="manual", max_length=64)
    amount_fcfa: float = Field(gt=0)
    reason: str = Field(min_length=1, max_length=255)
    advance_date: date
    note: Optional[str] = Field(default=None, max_length=2000)


class FarmerAdvanceUpdate(BaseModel):
    farmer_id: Optional[UUID] = None
    amount_fcfa: Optional[float] = Field(default=None, gt=0)
    reason: Optional[str] = Field(default=None, min_length=1, max_length=255)
    advance_date: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=2000)


class FarmerAdvanceRead(ORMModel):
    id: UUID
    cooperative_id: UUID
    farmer_id: UUID
    batch_id: Optional[UUID]
    parcel_id: Optional[UUID]
    product_id: Optional[UUID]
    amount_fcfa: float
    reason: str
    advance_date: date
    note: Optional[str]
    status: str
    source_type: str
    treasury_transaction_id: Optional[UUID]
    batch_code: Optional[str] = None
    product_name: Optional[str] = None
    confirmed_weight_kg: Optional[float] = None
    preharvest_completed_at: Optional[datetime] = None
    collecte_created: bool = False
    stock_in_created: bool = False
    return_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class FarmerAdvanceSummaryRow(BaseModel):
    farmer_id: UUID
    farmer_name: str
    total_collected_quantity: float
    total_amount_given: float
    cost_per_kg: Optional[float]
    last_modified: datetime
    number_of_advances: int


class FarmerAdvanceSummaryStats(BaseModel):
    total_advanced: float
    total_advances_count: int
    affected_farmers_count: int
    average_cost_per_kg: Optional[float]


class FarmerAdvanceSummaryResponse(BaseModel):
    items: List[FarmerAdvanceSummaryRow]
    stats: FarmerAdvanceSummaryStats


class FarmerAdvanceFarmerSummary(BaseModel):
    farmer_id: UUID
    farmer_name: str
    total_collected_quantity: float
    total_amount_given: float
    cost_per_kg: Optional[float]
    last_modified: datetime
    number_of_advances: int


class FarmerAdvanceFarmerDetailResponse(BaseModel):
    summary: FarmerAdvanceFarmerSummary
    advances: List[FarmerAdvanceRead]
