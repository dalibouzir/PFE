from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.tools.app_data_tools import source, tool_response, warnings_for_empty
from app.ai.retrieval.chunk_formatter import format_chunks_for_llm
from app.ai.retrieval.hybrid_retriever import HybridRetriever
from app.ai.retrieval.query_rewriter import rewrite_query
from app.ai.retrieval.reranker import rerank_chunks
from app.ai.retrieval.retrieval_filters import build_retrieval_filters
from app.models.rag import RAGChunk, RAGDocument
from app.models.user import User


class RAGTools:
    def __init__(self, db: Session, current_user: User):
        self.retriever = HybridRetriever(db, current_user)

    def search(self, *, query: str, detected_entities: dict, top_k: int = 5) -> dict[str, Any]:
        rewritten = rewrite_query(query)
        filters = build_retrieval_filters(detected_entities)
        candidates = self.retriever.retrieve(query=rewritten["expanded_domain_query"], filters=filters, top_k=12)
        ranked = rerank_chunks(candidates, detected_entities=detected_entities, top_k=top_k)
        if not ranked:
            # Controlled broadening: keep same query but remove strict entity filters.
            broad_filters = {"product": set(), "stage": set(), "language": filters.get("language"), "batch_ref": None}
            broad_candidates = self.retriever.retrieve(query=rewritten["expanded_domain_query"], filters=broad_filters, top_k=12)
            ranked = rerank_chunks(broad_candidates, detected_entities={}, top_k=top_k)
        if not ranked:
            ranked = self._direct_keyword_fallback(
                query=rewritten["normalized_query"] or rewritten["expanded_domain_query"],
                filters=filters,
                top_k=top_k,
            )
        formatted = format_chunks_for_llm(ranked)

        sources = [
            {
                "type": "rag",
                "document_id": item.get("document_id"),
                "chunk_id": item.get("chunk_id"),
                "title": item.get("title"),
                "score": round(float(item.get("final_score") or item.get("hybrid_score") or 0.0), 4),
                "topic": (item.get("metadata") or {}).get("topic") or (item.get("metadata") or {}).get("chunk_type"),
            }
            for item in ranked
        ]

        weak = not ranked or float(ranked[0].get("final_score") or 0.0) < 0.35
        return {
            "rewrite": rewritten,
            "filters": {
                key: sorted(list(value)) if isinstance(value, set) else value
                for key, value in filters.items()
            },
            "chunks": ranked,
            "formatted_chunks": formatted.get("chunks", []),
            "warnings": sorted(set(formatted.get("warnings", []) + (["WEAK_RETRIEVAL"] if weak else []))),
            "weak_retrieval": weak,
            "sources": sources,
        }

    def _direct_keyword_fallback(self, *, query: str, filters: dict[str, Any], top_k: int) -> list[dict[str, Any]]:
        terms = [token.strip().lower() for token in str(query or "").replace("?", " ").split() if len(token.strip()) > 2][:8]
        if not terms:
            return []

        stmt = (
            select(
                RAGChunk.id,
                RAGChunk.document_id,
                RAGChunk.content,
                RAGChunk.metadata_json,
                RAGDocument.title,
                RAGDocument.source_table,
                RAGDocument.metadata_json,
            )
            .join(RAGDocument, RAGDocument.id == RAGChunk.document_id)
            .where(RAGChunk.cooperative_id == self.retriever.current_user.cooperative_id)
            .order_by(RAGChunk.created_at.desc())
        )
        rows = self.retriever.db.execute(stmt).all()

        product_filters = {str(item).lower() for item in (filters.get("product") or set()) if str(item).strip()}
        stage_filters = {str(item).lower() for item in (filters.get("stage") or set()) if str(item).strip()}

        result: list[dict[str, Any]] = []
        for chunk_id, document_id, content, chunk_meta, title, source_type, doc_meta in rows:
            content_text = str(content or "").strip()
            lowered = content_text.lower()
            if not content_text:
                continue
            if not any(term in lowered for term in terms):
                continue

            metadata: dict[str, Any] = {}
            if isinstance(doc_meta, dict):
                metadata.update(doc_meta)
            if isinstance(chunk_meta, dict):
                metadata.update(chunk_meta)

            if product_filters:
                meta_product = str(metadata.get("product") or metadata.get("product_name") or metadata.get("crop") or "").lower()
                if meta_product and meta_product not in product_filters:
                    continue
            if stage_filters:
                meta_stage = str(metadata.get("stage") or metadata.get("stage_canonical") or "").lower()
                if meta_stage and meta_stage not in stage_filters:
                    continue

            overlap = sum(1 for term in terms if term in lowered)
            score = min(1.0, overlap / max(1.0, len(terms)))
            result.append(
                {
                    "document_id": str(document_id),
                    "chunk_id": str(chunk_id),
                    "title": str(title or "Source"),
                    "content": content_text,
                    "metadata": metadata,
                    "source_type": str(source_type or "knowledge_chunks"),
                    "hybrid_score": score,
                    "final_score": score,
                }
            )
            if len(result) >= top_k:
                break
        return result[:top_k]

    def retrieve_knowledge(self, query: str, product: str | None = None, stage: str | None = None, topic: str | None = None) -> dict[str, Any]:
        detected_entities = {
            "product": [product] if product else [],
            "stage": [stage] if stage else [],
            "metric": [topic] if topic else [],
            "language": "fr",
        }
        result = self.search(query=query, detected_entities=detected_entities, top_k=5)
        data = [
            {
                "document_id": item.get("document_id"),
                "chunk_id": item.get("chunk_id"),
                "title": item.get("title"),
                "content": item.get("content"),
                "metadata": item.get("metadata") or {},
                "score": float(item.get("final_score") or item.get("hybrid_score") or 0.0),
            }
            for item in result.get("chunks", [])
        ]
        return tool_response(
            ok=True,
            data=data,
            sources=[source(table="rag_chunks,rag_documents", label="Connaissances récupérées", record_count=len(data), source_type="rag")],
            warnings=warnings_for_empty(data) + [warning for warning in result.get("warnings", []) if warning != "WEAK_RETRIEVAL"],
        )

    def retrieve_best_practices(self, product: str | None = None, stage: str | None = None) -> dict[str, Any]:
        query_parts = ["bonnes pratiques post-récolte réduction pertes"]
        if product:
            query_parts.append(product)
        if stage:
            query_parts.append(stage)
        return self.retrieve_knowledge(" ".join(query_parts), product=product, stage=stage, topic="best_practices")

    def retrieve_material_balance_knowledge(self) -> dict[str, Any]:
        return self.retrieve_knowledge("bilan matière entrée sortie pertes efficacité traçabilité", topic="material_balance")
