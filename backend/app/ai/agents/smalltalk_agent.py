from __future__ import annotations

from app.ai.agents.base_agent import BaseAgent
from app.ai.schemas.agent_schemas import AgentContext, AgentResult


class SmallTalkAgent(BaseAgent):
    name = "SmallTalkAgent"
    description = "Handles greetings and minimal conversational responses."

    async def run(self, query: str, context: AgentContext) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            route=context.route,
            answer_part=(
                "Bonjour. Je peux vous aider à analyser les stocks, les lots, les pertes, "
                "l’efficacité des étapes de transformation et les recommandations de la coopérative."
            ),
            data={},
            sources=[],
            confidence=0.95,
            warnings=[],
            execution_time_ms=1,
        )
