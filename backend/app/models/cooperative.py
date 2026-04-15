import uuid
from typing import List

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import CooperativeStatus
from app.models.mixins import TimestampMixin


class Cooperative(TimestampMixin, Base):
    __tablename__ = "cooperatives"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    region: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[CooperativeStatus] = mapped_column(
        Enum(CooperativeStatus, native_enum=False),
        nullable=False,
        default=CooperativeStatus.ACTIVE,
    )

    users: Mapped[List["User"]] = relationship(back_populates="cooperative")
    members: Mapped[List["Member"]] = relationship(back_populates="cooperative", cascade="all, delete-orphan")
    fields: Mapped[List["Field"]] = relationship(back_populates="cooperative", cascade="all, delete-orphan")
    products: Mapped[List["Product"]] = relationship(back_populates="cooperative", cascade="all, delete-orphan")
    inputs: Mapped[List["Input"]] = relationship(back_populates="cooperative", cascade="all, delete-orphan")
    stocks: Mapped[List["Stock"]] = relationship(back_populates="cooperative", cascade="all, delete-orphan")
    batches: Mapped[List["Batch"]] = relationship(back_populates="cooperative", cascade="all, delete-orphan")
