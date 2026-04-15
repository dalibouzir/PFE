from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from sqlalchemy import Date, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import InputStatus
from app.models.mixins import TimestampMixin


class Input(TimestampMixin, Base):
    __tablename__ = "inputs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cooperative_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cooperatives.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("members.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    field_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("fields.id", ondelete="SET NULL"), nullable=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    grade: Mapped[str] = mapped_column(String(40), nullable=False)
    estimated_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[InputStatus] = mapped_column(
        Enum(InputStatus, native_enum=False),
        nullable=False,
        default=InputStatus.PENDING,
    )

    cooperative: Mapped["Cooperative"] = relationship(back_populates="inputs")
    member: Mapped["Member"] = relationship(back_populates="inputs")
    product: Mapped["Product"] = relationship(back_populates="inputs")
    field: Mapped[Optional["Field"]] = relationship()
