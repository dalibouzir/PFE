import uuid
from typing import Optional

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Field(TimestampMixin, Base):
    __tablename__ = "fields"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    member_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("members.id", ondelete="CASCADE"), nullable=False)
    cooperative_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cooperatives.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    area: Mapped[float] = mapped_column(Float, nullable=False)
    soil_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    irrigation_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    member: Mapped["Member"] = relationship(back_populates="fields")
    cooperative: Mapped["Cooperative"] = relationship(back_populates="fields")
