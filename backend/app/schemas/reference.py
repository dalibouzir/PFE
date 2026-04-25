from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.base import ORMModel


class ReferenceMetricRead(ORMModel):
    id: UUID
    source_id: str
    country: str
    region: str
    crop: str
    metric: str
    period: str
    value: float
    unit: str
    notes: Optional[str]


class KnowledgeChunkRead(ORMModel):
    id: UUID
    source_id: str
    source_url: str
    country: str
    region: str
    crop: str
    topic: str
    content: str


class ReferenceMetricListResponse(BaseModel):
    total: int
    items: List[ReferenceMetricRead]


class KnowledgeChunkListResponse(BaseModel):
    total: int
    items: List[KnowledgeChunkRead]
