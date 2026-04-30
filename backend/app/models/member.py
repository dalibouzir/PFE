import uuid
from datetime import date
import re
from typing import List, Optional

from sqlalchemy import Date, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import MemberStatus
from app.models.mixins import TimestampMixin


class Member(TimestampMixin, Base):
    __tablename__ = "members"
    __table_args__ = (
        UniqueConstraint("cooperative_id", "code", name="uq_members_cooperative_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cooperative_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cooperatives.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    village: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    main_product: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    secondary_products: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    parcel_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    area_hectares: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    join_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    specialty: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[MemberStatus] = mapped_column(
        Enum(MemberStatus, native_enum=False),
        nullable=False,
        default=MemberStatus.ACTIVE,
    )

    cooperative: Mapped["Cooperative"] = relationship(back_populates="members")
    fields: Mapped[List["Field"]] = relationship(back_populates="member", cascade="all, delete-orphan")
    parcels: Mapped[List["Parcel"]] = relationship(back_populates="member", cascade="all, delete-orphan")
    pre_harvest_steps: Mapped[List["PreHarvestStep"]] = relationship(back_populates="member", cascade="all, delete-orphan")
    global_charges: Mapped[List["GlobalCharge"]] = relationship(back_populates="member", cascade="all, delete-orphan")
    inputs: Mapped[List["Input"]] = relationship(back_populates="member")
    farmer_advances: Mapped[List["FarmerAdvance"]] = relationship(back_populates="farmer")
    treasury_transactions: Mapped[List["TreasuryTransaction"]] = relationship(back_populates="farmer")

    @property
    def products(self) -> list[str]:
        raw_values = [self.main_product, self.secondary_products, self.specialty]
        merged: list[str] = []
        seen = set()
        for raw in raw_values:
            if not raw:
                continue
            tokens = [token.strip() for token in re.split(r"[;,/|]+", raw) if token.strip()]
            for token in tokens:
                lowered = token.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                merged.append(token)
        return merged

    @property
    def internal_code(self) -> str:
        return self.code
