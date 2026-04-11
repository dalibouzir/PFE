import uuid
from datetime import date
from sqlalchemy import Numeric, Boolean, Text, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    loss_pct: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    efficiency_score: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    anomaly_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
