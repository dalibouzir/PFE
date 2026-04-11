import uuid
from datetime import datetime
from sqlalchemy import String, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class Input(Base):
    __tablename__ = "inputs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)
    product_type: Mapped[str] = mapped_column(String(80), nullable=False)
    quantity_kg: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    quality_grade: Mapped[str | None] = mapped_column(String(20), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
