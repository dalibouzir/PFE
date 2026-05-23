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

        grounded_recommendations = [rec for rec in recommendations if _has_valid_evidence_refs(rec)]
        warnings: list[str] = []
        if grounded_recommendations and any(not _has_valid_evidence_refs(rec) for rec in recommendations):
            warnings.append("RECOMMENDATION_EVIDENCE_WEAK")
        if recommendations and not grounded_recommendations:
            warnings.append("RECOMMENDATION_WITHOUT_EVIDENCE")

        sources = []
        for rec in grounded_recommendations:
            for evidence in rec.get("evidence_refs", []):
                if not isinstance(evidence, dict):
                    continue
                ev_type = str(evidence.get("type") or "").upper()
                if ev_type == "SQL":
                    sources.append(
                        {
                            "type": "sql",
                            "table": evidence.get("table") or "operational_data",
                            "label": evidence.get("short_fact") or evidence.get("label"),
                            "source_id": evidence.get("source_id"),
                            "related_batch": evidence.get("batch_ref"),
                            "related_product": evidence.get("product"),
                        }
                    )
                elif ev_type == "RAG":
                    sources.append(
                        {
                            "type": "rag",
                            "title": evidence.get("label") or evidence.get("source_title") or "knowledge_source",
                            "chunk_id": evidence.get("chunk_id"),
                            "document_id": evidence.get("source_id"),
                            "label": evidence.get("short_fact") or evidence.get("label"),
                        }
                    )
                elif ev_type == "ML":
                    sources.append(
                        {
                            "type": "ml",
                            "model": evidence.get("source_id") or "ml_signal",
                            "result_id": evidence.get("ml_log_id"),
                            "label": evidence.get("short_fact") or evidence.get("label"),
                            "risk_level": evidence.get("metric_value") if str(evidence.get("metric_name") or "") == "risk_level" else None,
                        }
                    )
                elif ev_type == "RULE":
                    sources.append(
                        {
                            "type": "recommendation",
                            "label": evidence.get("label") or "rule_based_logic",
                            "source_id": evidence.get("source_id"),
                            "used_for": "recommendation_evidence",
                        }
                    )

        if grounded_recommendations:
            answer = "\n".join(
                f"- {item.get('title')} ({item.get('priority')}): {item.get('action')}"
                for item in grounded_recommendations[:3]
            )
            confidence_values = [float(item.get("confidence", 0.4)) for item in grounded_recommendations]
            confidence = sum(confidence_values) / max(1, len(confidence_values))
            has_global_scope = any(str(item.get("scope") or "") == "GLOBAL_COOPERATIVE" for item in grounded_recommendations)
            data_payload = {
                "recommendations": grounded_recommendations,
                "insufficient_evidence": False,
                "scope": "GLOBAL_COOPERATIVE" if has_global_scope else "ACTIVE_QUERY",
            }
        else:
            answer = "Je ne peux pas générer de recommandations fiables sans données vérifiables."
            confidence = 0.45
            data_payload = {
                "recommendations": [],
                "insufficient_evidence": True,
                "scope": "ACTIVE_QUERY",
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


def _has_valid_evidence_refs(rec: dict) -> bool:
    refs = rec.get("evidence_refs") if isinstance(rec, dict) else None
    if not isinstance(refs, list) or not refs:
        return False
    has_sql_ref = False
    has_sql_grounded_rule = False
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        ref_type = str(ref.get("type") or "").upper()
        if ref_type == "RAG" and str(ref.get("quality_status") or "").upper() in {"WEAK", "REJECTED"}:
            continue
        source_id = str(ref.get("source_id") or "").strip()
        if not source_id:
            continue
        if ref_type == "SQL":
            has_sql_ref = True
        if ref_type == "RULE":
            triggered_by_type = str(ref.get("triggered_by_type") or "").upper()
            if triggered_by_type == "SQL" or "FROM_SQL" in str(ref.get("rule_name") or "").upper():
                has_sql_grounded_rule = True
    return has_sql_ref or has_sql_grounded_rule
