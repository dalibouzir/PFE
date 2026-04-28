from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RAGReindexRequest(BaseModel):
    cooperative_id: Optional[UUID] = None
    force: bool = Field(default=False, description="Re-embed even when content hash is unchanged.")


class RAGReindexResponse(BaseModel):
    cooperative_id: UUID
    started_at: datetime
    finished_at: datetime
    documents_seen: int
    documents_created: int
    documents_updated: int
    documents_unchanged: int
    documents_deleted: int
    chunks_created: int
    chunks_deleted: int
