import uuid
from datetime import date
from typing import List

from sqlalchemy import Date, Enum, Float, ForeignKey, String
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
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    creation_date: Mapped[date] = mapped_column(Date, nullable=False)
    initial_qty: Mapped[float] = mapped_column(Float, nullable=False)
    current_qty: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[BatchStatus] = mapped_column(
        Enum(BatchStatus, native_enum=False),
        nullable=False,
        default=BatchStatus.CREATED,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    cooperative: Mapped["Cooperative"] = relationship(back_populates="batches")
    product: Mapped["Product"] = relationship(back_populates="batches")
    created_by_user: Mapped["User"] = relationship(back_populates="created_batches")
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
