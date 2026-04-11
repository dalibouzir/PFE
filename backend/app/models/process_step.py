import uuid
from datetime import datetime
from sqlalchemy import String, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class ProcessStep(Base):
    __tablename__ = "process_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)
    input_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("inputs.id"), nullable=True)
    step_name: Mapped[str] = mapped_column(String(80), nullable=False)
    input_kg: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    output_kg: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    duration_hours: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    performed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
