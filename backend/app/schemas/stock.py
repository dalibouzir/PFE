from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel


class StockCreate(BaseModel):
    product_id: UUID
    quantity: float = Field(default=0, ge=0)
    threshold: float = Field(ge=0)
    unit: str = Field(default="kg", min_length=1, max_length=40)


class StockUpdate(BaseModel):
    threshold: Optional[float] = Field(default=None, ge=0)
    unit: Optional[str] = Field(default=None, min_length=1, max_length=40)


class StockAdjustment(BaseModel):
    amount: float = Field(gt=0)


class StockRead(ORMModel):
    id: UUID
    cooperative_id: UUID
    product_id: UUID
    quantity: float
    threshold: float
    total_stock: float
    available_stock: float
    reserved_in_lots: float
    processed_output: float
    total_stock_kg: float
    available_stock_kg: float
    reserved_in_lots_kg: float
    processed_output_kg: float
    threshold_kg: float
    unit: str
    last_updated: datetime
    created_at: datetime
    updated_at: datetime


class StockAlertRead(BaseModel):
    stock_id: UUID
    product_id: UUID
    quantity: float
    threshold: float
    unit: str
    deficit: float
    deficit_kg: float
