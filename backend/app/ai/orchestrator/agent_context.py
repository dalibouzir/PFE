from __future__ import annotations

from app.ai.schemas.agent_schemas import AgentContext
from app.ai.orchestrator.agent_types import IntentRouteDecision


def build_agent_context(
    *,
    query: str,
    language: str,
    decision: IntentRouteDecision,
    conversation_id: str | None,
    user_id: str | None,
    previous_messages: list[dict] | None,
) -> AgentContext:
    return AgentContext(
        user_query=query,
        language=language,
        route=decision.route,
        conversation_id=conversation_id,
        user_id=user_id,
        detected_entities=decision.detected_entities,
        filters={},
        previous_messages=previous_messages,
    )
