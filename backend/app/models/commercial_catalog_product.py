from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Enum, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.enums import CommercialCatalogStatus
from app.models.mixins import TimestampMixin


class CommercialCatalogProduct(TimestampMixin, Base):
    __tablename__ = "commercial_catalog_products"
    __table_args__ = (
        UniqueConstraint("cooperative_id", "name", name="uq_catalog_product_name_per_cooperative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cooperative_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cooperatives.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    sale_unit: Mapped[str] = mapped_column(String(40), nullable=False, default="kg")
    icon: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    sale_price_fcfa: Mapped[float] = mapped_column(Float, nullable=False)
    cost_price_fcfa: Mapped[float] = mapped_column(Float, nullable=False)
    min_order_qty: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    total_stock_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reserved_stock_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[CommercialCatalogStatus] = mapped_column(
        Enum(CommercialCatalogStatus, native_enum=False),
        nullable=False,
        default=CommercialCatalogStatus.ACTIVE,
    )

    cooperative: Mapped["Cooperative"] = relationship(back_populates="catalog_products")
    source_product: Mapped[Optional["Product"]] = relationship()
    order_lines: Mapped[list["CommercialOrderLine"]] = relationship(back_populates="catalog_product")
