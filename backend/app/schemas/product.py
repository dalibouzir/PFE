from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel


class ProductCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=120)
    unit: str = Field(min_length=1, max_length=40)
    quality_grade: Optional[str] = Field(default=None, max_length=40)


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    category: Optional[str] = Field(default=None, min_length=2, max_length=120)
    unit: Optional[str] = Field(default=None, min_length=1, max_length=40)
    quality_grade: Optional[str] = Field(default=None, max_length=40)


class ProductRead(ORMModel):
    id: UUID
    cooperative_id: UUID
    name: str
    category: str
    unit: str
    quality_grade: Optional[str]
    created_at: datetime
    updated_at: datetime
