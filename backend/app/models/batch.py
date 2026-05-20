import uuid
from datetime import date, datetime
from typing import List

from sqlalchemy import JSON, Date, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import BatchStatus
from app.models.mixins import TimestampMixin


class Batch(TimestampMixin, Base):
    __tablename__ = "batches"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cooperative_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cooperatives.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    member_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("members.id", ondelete="SET NULL"), nullable=True, index=True)
    parcel_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("parcels.id", ondelete="SET NULL"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    postharvest_reference: Mapped[str | None] = mapped_column(String(80), nullable=True, unique=True, index=True)
    creation_date: Mapped[date] = mapped_column(Date, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False, default="kg")
    ordered_process_steps: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    # Stored in kg (normalized).
    initial_qty: Mapped[float] = mapped_column(Float, nullable=False)
    # Stored in kg (normalized).
    current_qty: Mapped[float] = mapped_column(Float, nullable=False)
    surface_ha: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_yield_kg_per_ha: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_losses_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_qty_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_qty_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_charge_fcfa: Mapped[float | None] = mapped_column(Float, nullable=True)
    charge_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    charge_approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    preharvest_activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    preharvest_step_statuses: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    preharvest_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    postharvest_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[BatchStatus] = mapped_column(
        Enum(BatchStatus, native_enum=False),
        nullable=False,
        default=BatchStatus.CREATED,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    cooperative: Mapped["Cooperative"] = relationship(back_populates="batches")
    product: Mapped["Product"] = relationship(back_populates="batches")
    created_by_user: Mapped["User"] = relationship(back_populates="created_batches", foreign_keys=[created_by_user_id])
    process_steps: Mapped[List["ProcessStep"]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="ProcessStep.date",
    )
    recommendation: Mapped["Recommendation"] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
        uselist=False,
    )
