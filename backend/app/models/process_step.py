from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import ProcessStepStatus
from app.models.mixins import TimestampMixin


class ProcessStep(TimestampMixin, Base):
    __tablename__ = "process_steps"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # Stored in kg (normalized).
    qty_in: Mapped[float] = mapped_column(Float, nullable=False)
    # Stored in kg (normalized).
    qty_out: Mapped[float] = mapped_column(Float, nullable=False)
    # Stored in kg (normalized). Kept for backward compatibility with existing API fields.
    waste_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    loss_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    loss_unit: Mapped[str] = mapped_column(String(16), nullable=False, default="kg")
    normalized_loss_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ProcessStepStatus] = mapped_column(
        Enum(ProcessStepStatus, native_enum=False),
        nullable=False,
        default=ProcessStepStatus.PENDING,
    )
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[Optional[int]] = mapped_column(nullable=True)

    batch: Mapped["Batch"] = relationship(back_populates="process_steps")
