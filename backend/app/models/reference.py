from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin


class ReferenceMetric(TimestampMixin, Base):
    __tablename__ = "reference_metrics"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    crop: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    metric: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(40), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class KnowledgeChunk(TimestampMixin, Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    crop: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
