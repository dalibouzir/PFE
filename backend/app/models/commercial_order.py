from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import CommercialOrderStatus
from app.models.mixins import TimestampMixin, current_utc


class CommercialOrder(TimestampMixin, Base):
    __tablename__ = "commercial_orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cooperative_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cooperatives.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(160), nullable=False)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    customer_email: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    customer_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[CommercialOrderStatus] = mapped_column(
        Enum(CommercialOrderStatus, native_enum=False),
        nullable=False,
        default=CommercialOrderStatus.RECEIVED,
        index=True,
    )
    subtotal_fcfa: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tax_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.18)
    tax_amount_fcfa: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_amount_fcfa: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="consumer_app")
    locked: Mapped[bool] = mapped_column(nullable=False, default=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=current_utc)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    preparing_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ready_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    refused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    refused_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    cooperative: Mapped["Cooperative"] = relationship(back_populates="commercial_orders")
    lines: Mapped[list["CommercialOrderLine"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    invoice: Mapped[Optional["CommercialInvoice"]] = relationship(back_populates="order", uselist=False)


class CommercialOrderLine(TimestampMixin, Base):
    __tablename__ = "commercial_order_lines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("commercial_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    catalog_product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("commercial_catalog_products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_name_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    unit_snapshot: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    quantity_kg: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price_fcfa: Mapped[float] = mapped_column(Float, nullable=False)
    line_total_fcfa: Mapped[float] = mapped_column(Float, nullable=False)

    order: Mapped["CommercialOrder"] = relationship(back_populates="lines")
    catalog_product: Mapped["CommercialCatalogProduct"] = relationship(back_populates="order_lines")
