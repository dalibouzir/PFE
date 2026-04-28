from __future__ import annotations

from datetime import datetime
from typing import Any, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import ORMModel


class ChatRequest(BaseModel):
    session_id: Optional[UUID] = None
    message: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=4, ge=1, le=8)


class ChatCitation(BaseModel):
    source_id: str
    source_url: str
    region: str
    crop: str
    topic: str
    excerpt: str


class ChatMetricFact(BaseModel):
    source_id: str
    region: str
    crop: str
    metric: str
    period: str
    value: float
    unit: str
    notes: Optional[str] = None


class ChatDashboardSnapshot(BaseModel):
    cooperative_name: Optional[str] = None
    region: Optional[str] = None
    total_production: float
    loss_rate: float
    efficiency_rate: float
    number_of_active_batches: int
    stock_alerts: int


class ChatUIBlock(BaseModel):
    type: str
    title: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    success: bool
    session_id: UUID
    user_message_id: Optional[UUID] = None
    assistant_message_id: Optional[UUID] = None
    message: str
    grounded: bool
    mode: str
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    citations: List[ChatCitation]
    context_metrics: List[ChatMetricFact]
    dashboard: Optional[ChatDashboardSnapshot] = None
    ui_blocks: List[ChatUIBlock] = Field(default_factory=list)


class ChatSessionCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=180)


class ChatSessionRead(ORMModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    last_message_preview: Optional[str] = None
    last_message_at: Optional[datetime] = None


class ChatMessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class ChatMessageRead(ORMModel):
    id: UUID
    session_id: UUID
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime
    mode: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    citations: List[ChatCitation] = Field(default_factory=list)
    context_metrics: List[ChatMetricFact] = Field(default_factory=list)
    dashboard: Optional[ChatDashboardSnapshot] = None
    ui_blocks: List[ChatUIBlock] = Field(default_factory=list)
