import uuid
from typing import List, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cooperative_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cooperatives.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    quality_grade: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    cooperative: Mapped["Cooperative"] = relationship(back_populates="products")
    inputs: Mapped[List["Input"]] = relationship(back_populates="product")
    stocks: Mapped[List["Stock"]] = relationship(back_populates="product")
    batches: Mapped[List["Batch"]] = relationship(back_populates="product")
