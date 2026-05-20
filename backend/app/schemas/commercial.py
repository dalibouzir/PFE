from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


CatalogStatusLiteral = Literal["active", "hidden"]
OrderStatusLiteral = Literal["received", "confirmed", "preparing", "ready", "delivered", "paid", "refused"]
InvoiceStatusLiteral = Literal["pending", "paid"]


class CatalogProductCreate(BaseModel):
    source_product_id: UUID
    source_grade: str = Field(default="Non spécifié", min_length=1, max_length=40)
    name: str = Field(min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=2000)
    category: str = Field(min_length=2, max_length=120)
    sale_unit: str = Field(default="kg", min_length=1, max_length=40)
    icon: Optional[str] = Field(default=None, max_length=32)
    sale_price_fcfa: float = Field(gt=0)
    cost_price_fcfa: float = Field(ge=0)
    min_order_qty: float = Field(gt=0)
    allocated_quantity: float = Field(gt=0)


class CatalogProductUpdate(BaseModel):
    source_grade: Optional[str] = Field(default=None, min_length=1, max_length=40)
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    description: Optional[str] = Field(default=None, max_length=2000)
    category: Optional[str] = Field(default=None, min_length=2, max_length=120)
    sale_unit: Optional[str] = Field(default=None, min_length=1, max_length=40)
    icon: Optional[str] = Field(default=None, max_length=32)
    sale_price_fcfa: Optional[float] = Field(default=None, gt=0)
    cost_price_fcfa: Optional[float] = Field(default=None, ge=0)
    min_order_qty: Optional[float] = Field(default=None, gt=0)


class CatalogProductRead(BaseModel):
    id: UUID
    cooperative_id: UUID
    source_product_id: Optional[UUID]
    source_product_name: Optional[str]
    source_grade: str
    name: str
    description: Optional[str]
    category: str
    sale_unit: str
    icon: Optional[str]
    sale_price_fcfa: float
    cost_price_fcfa: float
    min_order_qty: float
    total_stock: float
    reserved_stock: float
    available_stock: float
    total_stock_kg: float
    reserved_stock_kg: float
    available_stock_kg: float
    margin_percent: float
    status: CatalogStatusLiteral
    low_stock: bool
    created_at: datetime
    updated_at: datetime


class OrderLineCreate(BaseModel):
    catalog_product_id: UUID
    grade: Optional[str] = Field(default=None, min_length=1, max_length=40)
    quantity: float = Field(gt=0)


class CommercialOrderIntake(BaseModel):
    customer_name: str = Field(min_length=2, max_length=160)
    customer_phone: Optional[str] = Field(default=None, max_length=32)
    customer_email: Optional[str] = Field(default=None, max_length=160)
    customer_address: Optional[str] = Field(default=None, max_length=255)
    payment_method: Optional[str] = Field(default=None, max_length=40)
    notes: Optional[str] = Field(default=None, max_length=2000)
    lines: list[OrderLineCreate] = Field(min_length=1)


class CommercialOrderStatusUpdate(BaseModel):
    status: OrderStatusLiteral
    refused_reason: Optional[str] = Field(default=None, max_length=2000)


class CommercialOrderLineRead(BaseModel):
    id: UUID
    catalog_product_id: UUID
    grade: str
    product_name: str
    unit: str
    quantity: float
    unit_price_fcfa: float
    line_total_fcfa: float


class CommercialOrderRead(BaseModel):
    id: UUID
    cooperative_id: UUID
    order_number: str
    customer_name: str
    customer_phone: Optional[str]
    customer_email: Optional[str]
    customer_address: Optional[str]
    payment_method: Optional[str]
    notes: Optional[str]
    status: OrderStatusLiteral
    subtotal_fcfa: float
    tax_rate: float
    tax_amount_fcfa: float
    total_amount_fcfa: float
    source: str
    locked: bool
    received_at: datetime
    confirmed_at: Optional[datetime]
    preparing_at: Optional[datetime]
    ready_at: Optional[datetime]
    delivered_at: Optional[datetime]
    paid_at: Optional[datetime]
    refused_at: Optional[datetime]
    refused_reason: Optional[str]
    lines: list[CommercialOrderLineRead]
    created_at: datetime
    updated_at: datetime


class CommercialOrderStats(BaseModel):
    total: int
    received: int
    confirmed: int
    preparing: int
    ready: int
    delivered: int
    paid: int
    refused: int
    new_count: int
    in_progress_count: int
    paid_this_month_fcfa: float


class CommercialOrderListResponse(BaseModel):
    items: list[CommercialOrderRead]
    page: int
    page_size: int
    total: int
    total_pages: int


class CommercialInvoiceLineRead(BaseModel):
    id: UUID
    description: str
    unit: str
    quantity: float
    unit_price_fcfa: float
    line_total_fcfa: float


class CommercialInvoiceRead(BaseModel):
    id: UUID
    cooperative_id: UUID
    order_id: UUID
    order_number: str
    invoice_number: str
    issue_date: date
    due_date: Optional[date]
    status: InvoiceStatusLiteral
    customer_name: str
    customer_phone: Optional[str]
    customer_email: Optional[str]
    customer_address: Optional[str]
    subtotal_fcfa: float
    tax_rate: float
    tax_amount_fcfa: float
    total_amount_fcfa: float
    paid_at: Optional[datetime]
    lines: list[CommercialInvoiceLineRead]
    created_at: datetime
    updated_at: datetime


class CommercialInvoiceStats(BaseModel):
    total_invoiced_fcfa: float
    paid_fcfa: float
    pending_fcfa: float
    paid_rate_percent: float
