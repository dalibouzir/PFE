from __future__ import annotations

import time

from app.ai.agents.base_agent import BaseAgent
from app.ai.schemas.agent_schemas import AgentContext, AgentResult
from app.ai.tools.recommendation_tools import RecommendationTools


class RecommendationAgent(BaseAgent):
    name = "RecommendationAgent"
    description = "Produces grounded operational recommendations from SQL/ML/RAG evidence."

    def __init__(self, recommendation_tools: RecommendationTools):
        self.recommendation_tools = recommendation_tools

    async def run(self, query: str, context: AgentContext) -> AgentResult:
        start = time.perf_counter()

        recommendations = self.recommendation_tools.build_recommendations(
            query=query,
            sql_results=context.sql_results,
            rag_results=context.rag_results,
            ml_results=context.ml_results,
            detected_entities=context.detected_entities,
        )

        grounded_recommendations = [rec for rec in recommendations if (rec.get("evidence") or [])]
        warnings: list[str] = []
        if grounded_recommendations and any(not rec.get("evidence") for rec in recommendations):
            warnings.append("RECOMMENDATION_EVIDENCE_WEAK")

        sources = []
        for rec in grounded_recommendations:
            for evidence in rec.get("evidence", []):
                if evidence.startswith("SQL:"):
                    sources.append({"type": "sql", "table": evidence.replace("SQL: ", "").split(" ")[0], "label": evidence})
                elif evidence.startswith("RAG:"):
                    sources.append({"type": "rag", "title": evidence.replace("RAG: ", "")})
                elif evidence.startswith("ML:"):
                    sources.append({"type": "ml", "model": evidence.replace("ML: ", "")})

        if grounded_recommendations:
            answer = "\n".join(
                f"- {item.get('title')} ({item.get('priority')}): {item.get('action')}"
                for item in grounded_recommendations[:3]
            )
            confidence_values = [float(item.get("confidence", 0.4)) for item in grounded_recommendations]
            confidence = sum(confidence_values) / max(1, len(confidence_values))
            data_payload = {
                "recommendations": grounded_recommendations,
                "insufficient_evidence": False,
            }
        else:
            answer = (
                "Les preuves actuelles sont insuffisantes pour recommander une action prioritaire. "
                "Complétez d’abord les mesures opérationnelles (SQL), puis confrontez-les aux signaux ML et aux bonnes pratiques RAG."
            )
            confidence = 0.45
            data_payload = {
                "recommendations": [],
                "insufficient_evidence": True,
            }

        return AgentResult(
            agent_name=self.name,
            route=context.route,
            answer_part=answer,
            data=data_payload,
            sources=sources,
            confidence=confidence,
            warnings=warnings,
            execution_time_ms=int((time.perf_counter() - start) * 1000),
        )
