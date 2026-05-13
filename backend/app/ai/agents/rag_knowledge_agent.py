from __future__ import annotations

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

        if not chunks:
            answer = "Aucune source de connaissance exploitable n’a été récupérée pour cette question."
            confidence = 0.35
            warnings = sorted(set([*warnings, "NO_RAG_RESULTS"]))
        else:
            answer = "\n\n".join(chunks[:2])
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
