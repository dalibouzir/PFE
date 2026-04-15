from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from sqlalchemy import Date, Enum, Float, ForeignKey, String, Text
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
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    qty_in: Mapped[float] = mapped_column(Float, nullable=False)
    qty_out: Mapped[float] = mapped_column(Float, nullable=False)
    waste_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ProcessStepStatus] = mapped_column(
        Enum(ProcessStepStatus, native_enum=False),
        nullable=False,
        default=ProcessStepStatus.PENDING,
    )
    duration_minutes: Mapped[Optional[int]] = mapped_column(nullable=True)

    batch: Mapped["Batch"] = relationship(back_populates="process_steps")
