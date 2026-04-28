from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin


class ChatSession(TimestampMixin, Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    cooperative_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("cooperatives.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False, default="New conversation")

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(TimestampMixin, Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    llm_provider: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    llm_model: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    citations_json: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    context_metrics_json: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    dashboard_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    ui_blocks_json: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")
