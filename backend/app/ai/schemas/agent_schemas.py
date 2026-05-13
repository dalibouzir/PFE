from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentRoute(str, Enum):
    SQL_ONLY = "SQL_ONLY"
    RAG_ONLY = "RAG_ONLY"
    ML_ONLY = "ML_ONLY"
    RECOMMENDATION_ONLY = "RECOMMENDATION_ONLY"
    HYBRID_SQL_RAG = "HYBRID_SQL_RAG"
    HYBRID_SQL_ML = "HYBRID_SQL_ML"
    HYBRID_RAG_RECOMMENDATION = "HYBRID_RAG_RECOMMENDATION"
    HYBRID_FULL = "HYBRID_FULL"
    SMALL_TALK = "SMALL_TALK"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class AgentContext(BaseModel):
    user_query: str
    language: str = "fr"
    route: AgentRoute
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    detected_entities: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)
    previous_messages: Optional[list[dict[str, Any]]] = None
    sql_results: Optional[dict[str, Any]] = None
    rag_results: Optional[list[dict[str, Any]]] = None
    ml_results: Optional[dict[str, Any]] = None
    recommendation_results: Optional[list[dict[str, Any]]] = None
    warnings: list[str] = Field(default_factory=list)


class AgentResult(BaseModel):
    agent_name: str
    route: AgentRoute
    answer_part: str
    data: dict[str, Any] = Field(default_factory=dict)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    execution_time_ms: int = 0


class FinalAgentResponse(BaseModel):
    answer: str
    route: AgentRoute
    agents_used: list[str] = Field(default_factory=list)
    response_blocks: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
