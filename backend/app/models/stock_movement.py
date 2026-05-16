from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from sqlalchemy import Date, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin


class StockMovement(TimestampMixin, Base):
    __tablename__ = "stock_movements"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_stock_movements_idempotency_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cooperative_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("cooperatives.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("batches.id", ondelete="SET NULL"), nullable=True, index=True)
    input_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("inputs.id", ondelete="SET NULL"), nullable=True, index=True)
    workflow_step_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("process_steps.id", ondelete="SET NULL"), nullable=True, index=True)
    movement_type: Mapped[str] = mapped_column(String(16), nullable=False)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(120), nullable=False)
    quantity_kg: Mapped[float] = mapped_column(Float, nullable=False)
    movement_date: Mapped[date] = mapped_column(Date, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
