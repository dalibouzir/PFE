from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import JSON, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin


class AIChatAuditLog(TimestampMixin, Base):
    __tablename__ = "ai_chat_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    cooperative_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True, index=True)
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    detected_language: Mapped[str] = mapped_column(String(16), nullable=False, default="fr")
    detected_entities: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    selected_route: Mapped[str] = mapped_column(String(48), nullable=False)
    route_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    agents_used: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    sql_sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    rag_sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    ml_sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    final_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    response_preview: Mapped[str] = mapped_column(Text, nullable=False)
    execution_time_ms: Mapped[int] = mapped_column(nullable=False, default=0)
