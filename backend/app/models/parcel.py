from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Parcel(TimestampMixin, Base):
    __tablename__ = "parcels"

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
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    surface_ha: Mapped[float] = mapped_column(Float, nullable=False)
    main_culture: Mapped[str] = mapped_column(String(120), nullable=False)
    variety: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    tree_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    cooperative: Mapped["Cooperative"] = relationship(back_populates="parcels")
    member: Mapped["Member"] = relationship(back_populates="parcels")
    pre_harvest_steps: Mapped[List["PreHarvestStep"]] = relationship(
        back_populates="parcel",
        cascade="all, delete-orphan",
        order_by="PreHarvestStep.step_order",
    )
    global_charges: Mapped[List["GlobalCharge"]] = relationship(back_populates="parcel")
