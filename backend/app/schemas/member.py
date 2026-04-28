from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel


class MemberCreate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=2, max_length=64)
    full_name: str = Field(min_length=2, max_length=160)
    phone: str = Field(min_length=3, max_length=32)
    village: Optional[str] = Field(default=None, max_length=120)
    main_product: Optional[str] = Field(default=None, max_length=120)
    secondary_products: Optional[str] = Field(default=None, max_length=500)
    parcel_count: int = Field(default=0, ge=0)
    area_hectares: float = Field(default=0, ge=0)
    join_date: Optional[date] = None
    specialty: Optional[str] = Field(default=None, max_length=120)
    status: str = Field(default="active")


class MemberUpdate(BaseModel):
    code: Optional[str] = Field(default=None, min_length=2, max_length=64)
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    phone: Optional[str] = Field(default=None, min_length=3, max_length=32)
    village: Optional[str] = Field(default=None, max_length=120)
    main_product: Optional[str] = Field(default=None, max_length=120)
    secondary_products: Optional[str] = Field(default=None, max_length=500)
    parcel_count: Optional[int] = Field(default=None, ge=0)
    area_hectares: Optional[float] = Field(default=None, ge=0)
    join_date: Optional[date] = None
    specialty: Optional[str] = Field(default=None, max_length=120)
    status: Optional[str] = None


class ContactMemberRequest(BaseModel):
    channel: str = Field(default="phone", min_length=2, max_length=40)
    message: str = Field(min_length=5, max_length=500)


class ContactMemberResponse(BaseModel):
    success: bool
    member_id: UUID
    channel: str
    message: str


class MemberRead(ORMModel):
    id: UUID
    cooperative_id: UUID
    code: str
    full_name: str
    phone: str
    village: Optional[str]
    main_product: Optional[str]
    secondary_products: Optional[str]
    parcel_count: int
    area_hectares: float
    join_date: Optional[date]
    specialty: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
