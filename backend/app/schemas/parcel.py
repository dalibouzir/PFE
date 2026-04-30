from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel


class ParcelCreate(BaseModel):
    farmer_id: UUID = Field(alias="member_id")
    name: str = Field(min_length=2, max_length=180)
    surface_ha: float = Field(gt=0)
    main_culture: str = Field(min_length=2, max_length=120)
    variety: Optional[str] = Field(default=None, max_length=120)
    tree_count: Optional[int] = Field(default=None, ge=0)

    model_config = {
        "populate_by_name": True,
    }


class ParcelUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=180)
    surface_ha: Optional[float] = Field(default=None, gt=0)
    main_culture: Optional[str] = Field(default=None, min_length=2, max_length=120)
    variety: Optional[str] = Field(default=None, max_length=120)
    tree_count: Optional[int] = Field(default=None, ge=0)


class ParcelRead(ORMModel):
    id: UUID
    cooperative_id: UUID
    member_id: UUID
    name: str
    surface_ha: float
    main_culture: str
    variety: Optional[str]
    tree_count: Optional[int]
    created_at: datetime
    updated_at: datetime
