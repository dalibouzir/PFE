from __future__ import annotations

import re
import time

from app.ai.agents.base_agent import BaseAgent
from app.ai.schemas.agent_schemas import AgentContext, AgentResult
from app.ai.tools.rag_tools import RAGTools


class RAGKnowledgeAgent(BaseAgent):
    name = "RAGKnowledgeAgent"
    description = "Retrieves and explains post-harvest domain knowledge with hybrid retrieval."

    def __init__(self, rag_tools: RAGTools):
        self.rag_tools = rag_tools

    async def run(self, query: str, context: AgentContext) -> AgentResult:
        start = time.perf_counter()
        payload = self.rag_tools.search(query=query, detected_entities=context.detected_entities, top_k=5)
        chunks = payload.get("formatted_chunks", [])
        if not chunks:
            raw_chunks = payload.get("chunks", []) or []
            for chunk in raw_chunks[:3]:
                content = str((chunk or {}).get("content") or "").strip()
                if not content:
                    continue
                title = str((chunk or {}).get("title") or "Source")
                chunks.append(f"[Source: {title}]\n{content}")
        warnings = payload.get("warnings", [])
        if "ADVICE_KNOWLEDGE_MISSING" in warnings:
            answer = "Le contexte documentaire disponible est insuffisant pour répondre précisément avec des bonnes pratiques fiables."
            return AgentResult(
                agent_name=self.name,
                route=context.route,
                answer_part=answer,
                data={
                    "rewrite": payload.get("rewrite"),
                    "filters": payload.get("filters"),
                    "chunks": payload.get("chunks", []),
                    "weak_retrieval": payload.get("weak_retrieval", False),
                },
                sources=payload.get("sources", []),
                confidence=0.42,
                warnings=warnings,
                execution_time_ms=int((time.perf_counter() - start) * 1000),
            )

        if not chunks:
            answer = (
                "RAG indisponible actuellement: aucun chunk indexé n’est disponible pour cette coopérative. "
                "Les réponses peuvent seulement s’appuyer sur SQL/ML/recommandations."
            )
            confidence = 0.35
            warnings = sorted(set([*warnings, "NO_RAG_RESULTS"]))
        else:
            answer = _compose_practical_advice(raw_query=query, chunks=payload.get("chunks", []), weak_retrieval="WEAK_RETRIEVAL" in warnings)
            confidence = 0.82 if "WEAK_RETRIEVAL" not in warnings else 0.55

        return AgentResult(
            agent_name=self.name,
            route=context.route,
            answer_part=answer,
            data={
                "rewrite": payload.get("rewrite"),
                "filters": payload.get("filters"),
                "chunks": payload.get("chunks", []),
                "weak_retrieval": payload.get("weak_retrieval", False),
            },
            sources=payload.get("sources", []),
            confidence=confidence,
            warnings=warnings,
            execution_time_ms=int((time.perf_counter() - start) * 1000),
        )


def _compose_practical_advice(*, raw_query: str, chunks: list[dict], weak_retrieval: bool) -> str:
    direct = _build_direct_answer(raw_query)
    practices = _extract_practices(chunks, limit=5)
    if not practices:
        practices = [
            "Stabiliser le taux d’humidité avant stockage et emballage.",
            "Utiliser des contenants propres, secs et adaptés au produit.",
            "Limiter les manipulations et les chocs pendant tri/conditionnement.",
        ]
    vigilance = _extract_vigilance(chunks) or "Surveiller régulièrement humidité, température et intégrité des emballages."

    lines = [direct, "", "Bonnes pratiques:"]
    for item in practices[:5]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append(f"Point de vigilance: {vigilance}")
    if weak_retrieval:
        lines.append("Limitation: les sources récupérées sont partielles pour cette question.")
    return "\n".join(lines).strip()


def _build_direct_answer(query: str) -> str:
    lowered = str(query or "").lower()
    if "humidit" in lowered and ("séchage" in lowered or "sechage" in lowered):
        return "Après séchage, il faut surtout empêcher la reprise d’humidité par contrôle du séchage final, emballage sec et stockage ventilé."
    if "tri" in lowered:
        return "Pour réduire les pertes au tri, standardisez les critères de tri et réduisez les manipulations agressives."
    if "stockage" in lowered:
        return "Un stockage sec, ventilé et protégé des variations d’humidité est la base pour limiter les pertes."
    if "conditionnement" in lowered or "emballage" in lowered or "casse" in lowered:
        return "Avant emballage, sécurisez l’état du produit, le choix du contenant et les conditions de manutention."
    return "Voici les bonnes pratiques opérationnelles les plus utiles pour cette situation."


def _extract_practices(chunks: list[dict], *, limit: int) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()
    for chunk in chunks[:5]:
        content = str((chunk or {}).get("content") or "")
        for sentence in re.split(r"[.\n;]", content):
            line = " ".join(sentence.strip().split())
            if len(line) < 24 or len(line) > 180:
                continue
            lowered = line.lower()
            if not any(token in lowered for token in ("doit", "éviter", "eviter", "contrôl", "control", "stocker", "sécher", "secher", "trier", "emballer", "conditionner", "humidité", "humidite", "casse")):
                continue
            key = lowered
            if key in seen:
                continue
            seen.add(key)
            cleaned = line[0].upper() + line[1:] if line else line
            candidates.append(cleaned)
            if len(candidates) >= limit:
                return candidates
    return candidates


def _extract_vigilance(chunks: list[dict]) -> str | None:
    for chunk in chunks[:4]:
        content = str((chunk or {}).get("content") or "").lower()
        if "humidit" in content:
            return "Le principal risque est la reprise d’humidité après séchage et pendant stockage."
        if "casse" in content:
            return "Le principal risque est la casse pendant manutention et empilage."
    return None
