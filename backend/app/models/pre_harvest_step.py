from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import PreHarvestStepStatus
from app.models.mixins import TimestampMixin


class PreHarvestStep(TimestampMixin, Base):
    __tablename__ = "pre_harvest_steps"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cooperative_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cooperatives.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parcel_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("parcels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_key: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(180), nullable=False)
    icon: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[PreHarvestStepStatus] = mapped_column(
        Enum(PreHarvestStepStatus, native_enum=False),
        nullable=False,
        default=PreHarvestStepStatus.PENDING,
    )
    quantity_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quantity_unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # Operation cost is stored directly on the step and aggregated in analytics.
    # We intentionally avoid auto-creating GlobalCharge rows from this field to prevent double counting.
    operation_cost_fcfa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    realization_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    observations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    cooperative: Mapped["Cooperative"] = relationship(back_populates="pre_harvest_steps")
    parcel: Mapped["Parcel"] = relationship(back_populates="pre_harvest_steps")
    member: Mapped["Member"] = relationship(back_populates="pre_harvest_steps")
    global_charges: Mapped[list["GlobalCharge"]] = relationship(back_populates="pre_harvest_step")
