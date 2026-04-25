from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from sqlalchemy import Date, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import FarmerAdvanceStatus
from app.models.mixins import TimestampMixin


class FarmerAdvance(TimestampMixin, Base):
    __tablename__ = "farmer_advances"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cooperative_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cooperatives.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    farmer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True)
    amount_fcfa: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    advance_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[FarmerAdvanceStatus] = mapped_column(
        Enum(FarmerAdvanceStatus, native_enum=False),
        nullable=False,
        default=FarmerAdvanceStatus.ACTIVE,
    )
    treasury_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("treasury_transactions.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )

    cooperative: Mapped["Cooperative"] = relationship(back_populates="farmer_advances")
    farmer: Mapped["Member"] = relationship(back_populates="farmer_advances", foreign_keys=[farmer_id])
    treasury_transaction: Mapped[Optional["TreasuryTransaction"]] = relationship(
        back_populates="farmer_advance",
        foreign_keys=[treasury_transaction_id],
        uselist=False,
    )
