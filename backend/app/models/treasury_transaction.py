from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from sqlalchemy import Date, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import TreasuryTransactionStatus, TreasuryTransactionType
from app.models.mixins import TimestampMixin


class TreasuryTransaction(TimestampMixin, Base):
    __tablename__ = "treasury_transactions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cooperative_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cooperatives.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reference: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    type: Mapped[TreasuryTransactionType] = mapped_column(
        Enum(TreasuryTransactionType, native_enum=False),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_fcfa: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[TreasuryTransactionStatus] = mapped_column(
        Enum(TreasuryTransactionStatus, native_enum=False),
        nullable=False,
        default=TreasuryTransactionStatus.RECORDED,
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="manual", index=True)
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True, index=True)
    farmer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    cooperative: Mapped["Cooperative"] = relationship(back_populates="treasury_transactions")
    farmer: Mapped[Optional["Member"]] = relationship(back_populates="treasury_transactions", foreign_keys=[farmer_id])
    farmer_advance: Mapped[Optional["FarmerAdvance"]] = relationship(back_populates="treasury_transaction", uselist=False)
