from __future__ import annotations

from app.ai.schemas.agent_schemas import AgentContext, AgentResult


class BaseAgent:
    name: str = "BaseAgent"
    description: str = ""

    async def run(self, query: str, context: AgentContext) -> AgentResult:
        raise NotImplementedError
