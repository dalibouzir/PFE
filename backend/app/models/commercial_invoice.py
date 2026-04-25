from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import InvoiceStatus
from app.models.mixins import TimestampMixin


class CommercialInvoice(TimestampMixin, Base):
    __tablename__ = "commercial_invoices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cooperative_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cooperatives.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("commercial_orders.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    invoice_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, native_enum=False),
        nullable=False,
        default=InvoiceStatus.PENDING,
        index=True,
    )
    customer_name_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    customer_phone_snapshot: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    customer_email_snapshot: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    customer_address_snapshot: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subtotal_fcfa: Mapped[float] = mapped_column(Float, nullable=False)
    tax_rate: Mapped[float] = mapped_column(Float, nullable=False)
    tax_amount_fcfa: Mapped[float] = mapped_column(Float, nullable=False)
    total_amount_fcfa: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    cooperative: Mapped["Cooperative"] = relationship(back_populates="commercial_invoices")
    order: Mapped["CommercialOrder"] = relationship(back_populates="invoice")
    lines: Mapped[list["CommercialInvoiceLine"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")


class CommercialInvoiceLine(TimestampMixin, Base):
    __tablename__ = "commercial_invoice_lines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("commercial_invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(String(120), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price_fcfa: Mapped[float] = mapped_column(Float, nullable=False)
    line_total_fcfa: Mapped[float] = mapped_column(Float, nullable=False)

    invoice: Mapped["CommercialInvoice"] = relationship(back_populates="lines")
