from __future__ import annotations

from datetime import date as date_type
from datetime import datetime as datetime_type
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel
from app.schemas.uploaded_file import UploadedFileRead


class InputCreate(BaseModel):
    member_id: UUID
    product_id: UUID
    batch_id: Optional[UUID] = None
    field_id: Optional[UUID] = None
    date: date_type
    quantity: float = Field(gt=0)
    unit: Optional[str] = Field(default=None, min_length=1, max_length=16)
    grade: str = Field(min_length=1, max_length=40)
    estimated_value: Optional[float] = Field(default=None, ge=0)
    bl_number: Optional[str] = Field(default=None, max_length=80)
    status: str = Field(default="pending")
    source_type: Optional[str] = Field(default="manual", max_length=64)


class InputUpdate(BaseModel):
    member_id: Optional[UUID] = None
    product_id: Optional[UUID] = None
    batch_id: Optional[UUID] = None
    field_id: Optional[UUID] = None
    date: Optional[date_type] = None
    quantity: Optional[float] = Field(default=None, gt=0)
    unit: Optional[str] = Field(default=None, min_length=1, max_length=16)
    grade: Optional[str] = Field(default=None, min_length=1, max_length=40)
    estimated_value: Optional[float] = Field(default=None, ge=0)
    bl_number: Optional[str] = Field(default=None, max_length=80)
    status: Optional[str] = None
    source_type: Optional[str] = Field(default=None, max_length=64)


class InputRead(ORMModel):
    id: UUID
    cooperative_id: UUID
    member_id: UUID
    product_id: UUID
    batch_id: Optional[UUID]
    field_id: Optional[UUID]
    date: date_type
    quantity: float
    grade: str
    estimated_value: Optional[float]
    bl_number: Optional[str]
    collecte_reference: Optional[str] = None
    status: str
    source_type: str
    created_at: datetime_type
    justificatif_file: Optional[UploadedFileRead] = None
    updated_at: datetime_type
