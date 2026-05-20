from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.uploaded_file import UploadedFileRead


class TreasuryTransactionCreate(BaseModel):
    transaction_date: date
    type: str = Field(min_length=1, max_length=16)
    category: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=255)
    amount_fcfa: float = Field(gt=0)
    note: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[str] = Field(default=None, min_length=1, max_length=64)
    receipt_reference: Optional[str] = Field(default=None, max_length=120)
    source_type: str = Field(default="manual", min_length=1, max_length=64)
    farmer_id: Optional[UUID] = None


class TreasuryTransactionUpdate(BaseModel):
    transaction_date: Optional[date] = None
    type: Optional[str] = Field(default=None, min_length=1, max_length=16)
    category: Optional[str] = Field(default=None, min_length=1, max_length=80)
    label: Optional[str] = Field(default=None, min_length=1, max_length=255)
    amount_fcfa: Optional[float] = Field(default=None, gt=0)
    note: Optional[str] = Field(default=None, max_length=2000)
    source_type: Optional[str] = Field(default=None, min_length=1, max_length=64)
    farmer_id: Optional[UUID] = None
    status: Optional[str] = Field(default=None, min_length=1, max_length=64)
    receipt_reference: Optional[str] = Field(default=None, max_length=120)


class TreasuryTransactionRead(BaseModel):
    id: UUID
    cooperative_id: UUID
    reference: str
    transaction_date: date
    type: str
    category: str
    label: str
    amount_fcfa: float
    note: Optional[str]
    receipt_reference: Optional[str]
    status: str
    is_locked: bool
    justificatif_status: str
    justificatif_file: Optional[UploadedFileRead]
    source_type: str
    source_id: Optional[UUID]
    linked_farmer_advance_id: Optional[UUID] = None
    linked_advance_devis_file: Optional[UploadedFileRead] = None
    farmer_id: Optional[UUID]
    farmer_name: Optional[str]
    created_at: datetime
    updated_at: datetime


class TreasuryStatsRead(BaseModel):
    total_given: float
    total_expenses: float
    total_income: float
    current_balance: float
