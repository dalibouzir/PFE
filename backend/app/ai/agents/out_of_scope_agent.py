from __future__ import annotations

from app.ai.agents.base_agent import BaseAgent
from app.ai.schemas.agent_schemas import AgentContext, AgentResult


class OutOfScopeAgent(BaseAgent):
    name = "OutOfScopeAgent"
    description = "Politely redirects non-cooperative requests."

    async def run(self, query: str, context: AgentContext) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            route=context.route,
            answer_part=(
                "Je ne peux pas exécuter cette demande ici. "
                "Utilisez l’application pour les actions d’interface et posez une question analytique vérifiable."
            ),
            data={},
            sources=[],
            confidence=0.95,
            warnings=[],
            execution_time_ms=1,
        )
