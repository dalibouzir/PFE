from __future__ import annotations

from app.ai.orchestrator.module_registry import ModuleRegistry
from app.ai.agents.base_agent import BaseAgent
from app.ai.schemas.agent_schemas import AgentContext, AgentResult
from app.ml.llm.provider import get_llm_client
from app.utils.exceptions import ValidationError


class SmallTalkAgent(BaseAgent):
    name = "SmallTalkAgent"
    description = "Handles greetings and minimal conversational responses."

    def __init__(self):
        self.module_registry = ModuleRegistry()

    async def run(self, query: str, context: AgentContext) -> AgentResult:
        lowered = " ".join(str(query or "").lower().split())
        answer = self._build_response(lowered)

        return AgentResult(
            agent_name=self.name,
            route=context.route,
            answer_part=answer,
            data={},
            sources=[],
            confidence=0.95,
            warnings=[],
            execution_time_ms=1,
        )

    def _build_response(self, lowered_query: str) -> str:
        if self.module_registry.is_capability_question(lowered_query):
            labels = self.module_registry.labels_for_supported_modules()
            core = ", ".join(labels[:8])
            return (
                "Oui, je peux t’aider. Je peux analyser les données de la coopérative sur "
                f"{core}, et aussi donner des explications, prioriser des actions et comparer les risques."
            )
        if "merci" in lowered_query or "thanks" in lowered_query:
            return "Avec plaisir. Si tu veux, on peut continuer avec une question sur tes lots, pertes, stocks ou recommandations."
        if any(token in lowered_query for token in ("salut", "bonjour", "hello", "hi", "bonsoir", "coucou", "ca va", "ça va")):
            llm_text = self._try_llm_smalltalk(lowered_query)
            if llm_text:
                return llm_text
            return "Salut, ça va bien. Je suis là pour t’aider sur les données de ta coopérative."
        return "Je suis là pour t’aider. Pose-moi une question sur les opérations de la coopérative et je te réponds."

    def _try_llm_smalltalk(self, lowered_query: str) -> str | None:
        try:
            client = get_llm_client()
            response = client.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "Tu es un assistant conversationnel francophone. "
                            "Réponds en 1-2 phrases naturelles, chaleureuses, sans données chiffrées."
                        ),
                    },
                    {
                        "role": "user",
                        "content": lowered_query or "salut",
                    },
                ]
            )
            text = str(response.content or "").strip()
            return text or None
        except ValidationError:
            return None
        except Exception:
            return None
