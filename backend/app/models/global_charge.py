from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from sqlalchemy import Date, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin


class GlobalCharge(TimestampMixin, Base):
    __tablename__ = "global_charges"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cooperative_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cooperatives.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parcel_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("parcels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    pre_harvest_step_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("pre_harvest_steps.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    process_step_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("process_steps.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    charge_type: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_fcfa: Mapped[float] = mapped_column(Float, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    treasury_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("treasury_transactions.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )

    cooperative: Mapped["Cooperative"] = relationship(back_populates="global_charges")
    member: Mapped["Member"] = relationship(back_populates="global_charges")
    parcel: Mapped[Optional["Parcel"]] = relationship(back_populates="global_charges")
    pre_harvest_step: Mapped[Optional["PreHarvestStep"]] = relationship(back_populates="global_charges")
