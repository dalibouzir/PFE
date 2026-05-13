from __future__ import annotations

from pydantic import BaseModel, Field

from app.ai.schemas.agent_schemas import AgentRoute


class IntentRouteDecision(BaseModel):
    route: AgentRoute
    confidence: float = 0.0
    detected_entities: dict = Field(default_factory=dict)
    required_agents: list[str] = Field(default_factory=list)
    explanation: str = ""
