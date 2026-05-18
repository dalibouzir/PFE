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
        pure_advice_query = _is_pure_advice_query(query, detected_entities=detected_entities)
        if pure_advice_query:
            filters = {
                **filters,
                "prefer_knowledge_sources": True,
                "avoid_operational_sources": True,
            }
        candidates = self.retriever.retrieve(query=rewritten["expanded_domain_query"], filters=filters, top_k=12)
        ranked = rerank_chunks(candidates, detected_entities=detected_entities, top_k=top_k)
        if pure_advice_query:
            ranked = _prefer_advice_knowledge_chunks(ranked, top_k=top_k)
        if not ranked:
            # Controlled broadening: keep same query but remove strict entity filters.
            broad_filters = {"product": set(), "stage": set(), "language": filters.get("language"), "batch_ref": None}
            if pure_advice_query:
                broad_filters["prefer_knowledge_sources"] = True
                broad_filters["avoid_operational_sources"] = True
            broad_candidates = self.retriever.retrieve(query=rewritten["expanded_domain_query"], filters=broad_filters, top_k=12)
            ranked = rerank_chunks(broad_candidates, detected_entities={}, top_k=top_k)
            if pure_advice_query:
                ranked = _prefer_advice_knowledge_chunks(ranked, top_k=top_k)
        if not ranked:
            ranked = self._direct_keyword_fallback(
                query=rewritten["normalized_query"] or rewritten["expanded_domain_query"],
                filters=filters,
                top_k=top_k,
            )
        advice_knowledge_missing = False
        if pure_advice_query:
            ranked, advice_knowledge_missing = _strict_advice_selection(ranked, top_k=top_k)
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
        warnings = list(formatted.get("warnings", []))
        if weak:
            warnings.append("WEAK_RETRIEVAL")
        if advice_knowledge_missing:
            warnings.append("ADVICE_KNOWLEDGE_MISSING")
        return {
            "rewrite": rewritten,
            "filters": {
                key: sorted(list(value)) if isinstance(value, set) else value
                for key, value in filters.items()
            },
            "chunks": ranked,
            "formatted_chunks": formatted.get("chunks", []),
            "warnings": sorted(set(warnings)),
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
        avoid_operational = bool(filters.get("avoid_operational_sources"))

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
            if avoid_operational and _is_operational_source(str(source_type or "")):
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


def _is_pure_advice_query(query: str, *, detected_entities: dict[str, Any]) -> bool:
    lowered = str(query or "").lower()
    advice_markers = (
        "bonnes pratiques",
        "meilleures pratiques",
        "procédure",
        "procedure",
        "précaution",
        "precaution",
        "check-list",
        "checklist",
        "comment éviter",
        "comment eviter",
        "réduire",
        "reduire",
        "éviter",
        "eviter",
        "avant emballage",
        "avant l'emballage",
        "avant de conditionner",
        "conditionner",
    )
    advice_topics = ("tri", "séchage", "sechage", "stockage", "humidit", "conditionnement", "conditionner", "casse", "emballage")
    asks_current_data = any(
        token in lowered
        for token in ("dans nos données", "dans nos donnees", "ce lot", "ce produit", "actuel", "actuelle", "notre coop", "nos lots")
    )
    has_operational_entities = bool((detected_entities or {}).get("batch_ref")) or bool((detected_entities or {}).get("member_name"))
    return (
        any(marker in lowered for marker in advice_markers)
        and any(topic in lowered for topic in advice_topics)
        and not asks_current_data
        and not has_operational_entities
    )


def _is_operational_source(source_type: str) -> bool:
    lowered = source_type.lower()
    operational_markers = (
        "farmer_advances",
        "batches",
        "process_steps",
        "stocks",
        "stock_movements",
        "commercial_orders",
        "commercial_invoices",
        "treasury_transactions",
        "global_charges",
        "inputs",
        "uploaded_files",
        "members",
        "ml_prediction_logs",
        "recommendations",
        "ml_recommendation_logs",
    )
    return any(marker in lowered for marker in operational_markers)


def _prefer_advice_knowledge_chunks(items: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
    if not items:
        return []

    def is_preferred(item: dict[str, Any]) -> bool:
        source_type = str(item.get("source_type") or "").lower()
        meta = item.get("metadata") or {}
        topic = str(meta.get("topic") or meta.get("chunk_type") or "").lower()
        title = str(item.get("title") or "").lower()
        if any(token in source_type for token in ("knowledge", "reference", "guide", "best_practice")):
            return True
        if any(token in topic for token in ("best_practice", "good_practice", "guidance", "stockage", "tri", "sechage", "séchage", "humidite", "humidité", "conditionnement", "casse")):
            return True
        if any(token in title for token in ("knowledge", "référence", "reference", "bonnes pratiques")):
            return True
        return False

    preferred = [item for item in items if is_preferred(item)]
    if preferred:
        return preferred[:top_k]
    return items[:top_k]


def _strict_advice_selection(items: list[dict[str, Any]], *, top_k: int) -> tuple[list[dict[str, Any]], bool]:
    if not items:
        return [], True

    preferred = _prefer_advice_knowledge_chunks(items, top_k=top_k)
    if preferred and not any(_is_operational_source(str(item.get("source_type") or "")) for item in preferred):
        return preferred[:top_k], False

    strict: list[dict[str, Any]] = []
    for item in items:
        source_type = str(item.get("source_type") or "").lower()
        if _is_operational_source(source_type):
            continue
        strict.append(item)
        if len(strict) >= top_k:
            break

    if strict:
        return strict[:top_k], False
    return [], True
