from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UserDefinedType, Uuid

from app.db.base import Base
from app.models.mixins import TimestampMixin, current_utc


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int):
        self.dimensions = dimensions

    def get_col_spec(self, **kw: Any) -> str:
        return f"vector({self.dimensions})"


class RAGDocument(TimestampMixin, Base):
    __tablename__ = "rag_documents"
    __table_args__ = (
        UniqueConstraint(
            "cooperative_id",
            "source_type",
            "source_table",
            "source_record_ref",
            name="uq_rag_documents_source_scope",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cooperative_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cooperatives.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_table: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    source_record_ref: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=current_utc)

    cooperative: Mapped["Cooperative"] = relationship()
    chunks: Mapped[list["RAGChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="RAGChunk.chunk_index",
    )


class RAGChunk(TimestampMixin, Base):
    __tablename__ = "rag_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_rag_chunks_document_chunk_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("rag_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cooperative_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("cooperatives.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[str] = mapped_column(Vector(384), nullable=False)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    document: Mapped["RAGDocument"] = relationship(back_populates="chunks")
    cooperative: Mapped["Cooperative"] = relationship()
