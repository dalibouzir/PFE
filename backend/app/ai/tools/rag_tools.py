from __future__ import annotations

import re
import time
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

_RAG_ADVICE_CACHE_TTL_SECONDS = 90
_RAG_ADVICE_CACHE_MAX = 128
_RAG_ADVICE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


class RAGTools:
    def __init__(self, db: Session, current_user: User):
        self.current_user = current_user
        self.retriever = HybridRetriever(db, current_user)

    def search(self, *, query: str, detected_entities: dict, top_k: int = 5) -> dict[str, Any]:
        total_started = time.perf_counter()
        rewrite_started = time.perf_counter()
        rewritten = rewrite_query(query)
        rewrite_ms = int((time.perf_counter() - rewrite_started) * 1000)
        filters_started = time.perf_counter()
        filters = build_retrieval_filters(detected_entities)
        filters_ms = int((time.perf_counter() - filters_started) * 1000)
        pure_advice_query = _is_pure_advice_query(query, detected_entities=detected_entities)
        cache_key = ""
        if pure_advice_query and not filters.get("batch_ref"):
            cache_key = self._advice_cache_key(query=rewritten["expanded_domain_query"], filters=filters, top_k=top_k)
            cached = _RAG_ADVICE_CACHE.get(cache_key)
            if cached and cached[0] > time.time():
                payload = dict(cached[1])
                timing = dict(payload.get("timing_ms", {}))
                timing["cache_hit"] = True
                timing["total_search_ms"] = int((time.perf_counter() - total_started) * 1000)
                payload["timing_ms"] = timing
                return payload
        if pure_advice_query:
            filters = {
                **filters,
                "prefer_knowledge_sources": True,
                "avoid_operational_sources": True,
            }
        retrieve_started = time.perf_counter()
        retrieval = self.retriever.retrieve_with_diagnostics(query=rewritten["expanded_domain_query"], filters=filters, top_k=12)
        retrieve_ms = int((time.perf_counter() - retrieve_started) * 1000)
        candidates = retrieval.get("results", [])
        retrieval_timing = retrieval.get("timing_ms", {})
        ranked = rerank_chunks(candidates, detected_entities=detected_entities, top_k=top_k)
        rerank_ms = max(0, retrieve_ms - int(retrieval_timing.get("total_retrieval_ms", 0) or 0))
        if pure_advice_query:
            ranked = _prefer_advice_knowledge_chunks(ranked, top_k=top_k)
        if not ranked:
            # Controlled broadening: keep same query but remove strict entity filters.
            broad_filters = {"product": set(), "stage": set(), "language": filters.get("language"), "batch_ref": None}
            if pure_advice_query:
                broad_filters["prefer_knowledge_sources"] = True
                broad_filters["avoid_operational_sources"] = True
            broad = self.retriever.retrieve_with_diagnostics(query=rewritten["expanded_domain_query"], filters=broad_filters, top_k=12)
            broad_candidates = broad.get("results", [])
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
        assessed_items = _assess_rag_evidence_items(
            query=query,
            detected_entities=detected_entities,
            items=ranked,
        )
        usable_items = [item for item in assessed_items if str(item.get("quality_status")) in {"STRONG", "PARTIAL"}][:top_k]
        if pure_advice_query and not usable_items and ranked:
            # Keep guidance available for advice-only prompts when strict quality gates reject
            # otherwise relevant knowledge chunks; final composer still applies safety wording.
            usable_items = ranked[:top_k]
        formatted = format_chunks_for_llm(usable_items)

        sources = [
            {
                "type": "rag",
                "source_id": item.get("source_id"),
                "document_id": item.get("document_id"),
                "chunk_id": item.get("chunk_id"),
                "title": item.get("title"),
                "score": round(float(item.get("relevance_score") or item.get("final_score") or item.get("hybrid_score") or 0.0), 4),
                "topic": (item.get("metadata") or {}).get("topic") or (item.get("metadata") or {}).get("chunk_type"),
                "source_type": item.get("source_type"),
                "product_tags": item.get("product_tags"),
                "stage_tags": item.get("stage_tags"),
                "usable_for": item.get("usable_for"),
                "quality_status": item.get("quality_status"),
                "content_excerpt": item.get("content_excerpt"),
            }
            for item in usable_items
        ]

        weak = not usable_items or float(usable_items[0].get("relevance_score") or 0.0) < 0.42
        warnings = list(formatted.get("warnings", []))
        if any(str(item.get("quality_status")) == "REJECTED" for item in assessed_items):
            warnings.append("RAG_EVIDENCE_REJECTED")
        if weak:
            warnings.append("WEAK_RETRIEVAL")
        if advice_knowledge_missing:
            warnings.append("ADVICE_KNOWLEDGE_MISSING")
        if not usable_items and assessed_items:
            warnings.append("RAG_QUALITY_INSUFFICIENT")
        payload = {
            "rewrite": rewritten,
            "filters": {
                key: sorted(list(value)) if isinstance(value, set) else value
                for key, value in filters.items()
            },
            "chunks": usable_items,
            "all_chunks_assessed": assessed_items,
            "formatted_chunks": formatted.get("chunks", []),
            "warnings": sorted(set(warnings)),
            "weak_retrieval": weak,
            "sources": sources,
            "timing_ms": {
                "query_rewrite_ms": rewrite_ms,
                "filter_build_ms": filters_ms,
                "embedding_ms": int(retrieval_timing.get("embedding_ms", 0) or 0),
                "vector_search_ms": int(retrieval_timing.get("vector_search_ms", 0) or 0),
                "metadata_filter_ms": int(retrieval_timing.get("metadata_filter_ms", 0) or 0),
                "context_build_ms": int(retrieval_timing.get("merge_rank_ms", 0) or 0),
                "rerank_ms": rerank_ms,
                "retrieval_total_ms": int(retrieval_timing.get("total_retrieval_ms", 0) or 0),
                "quality_filter_ms": int(
                    max(
                        0,
                        (time.perf_counter() - total_started) * 1000
                        - rewrite_ms
                        - filters_ms
                        - int(retrieval_timing.get("total_retrieval_ms", 0) or 0),
                    )
                ),
                "cache_hit": False,
                "total_search_ms": int((time.perf_counter() - total_started) * 1000),
            },
            "counts": retrieval.get("counts", {}),
        }
        if cache_key:
            self._set_advice_cache(cache_key, payload)
        return payload

    def _advice_cache_key(self, *, query: str, filters: dict[str, Any], top_k: int) -> str:
        products = ",".join(sorted(str(v) for v in (filters.get("product") or set())))
        stages = ",".join(sorted(str(v) for v in (filters.get("stage") or set())))
        language = str(filters.get("language") or "fr")
        coop = str(self.current_user.cooperative_id or "")
        return f"{coop}|{language}|{products}|{stages}|{top_k}|{query.strip().lower()}"

    def _set_advice_cache(self, key: str, payload: dict[str, Any]) -> None:
        if len(_RAG_ADVICE_CACHE) >= _RAG_ADVICE_CACHE_MAX:
            oldest_key = min(_RAG_ADVICE_CACHE, key=lambda k: _RAG_ADVICE_CACHE[k][0])
            _RAG_ADVICE_CACHE.pop(oldest_key, None)
        _RAG_ADVICE_CACHE[key] = (time.time() + _RAG_ADVICE_CACHE_TTL_SECONDS, payload)

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
                "source_id": item.get("source_id"),
                "document_id": item.get("document_id"),
                "chunk_id": item.get("chunk_id"),
                "title": item.get("title"),
                "content_excerpt": item.get("content_excerpt"),
                "sanitized_summary": item.get("sanitized_summary"),
                "metadata": item.get("metadata") or {},
                "score": float(item.get("relevance_score") or item.get("final_score") or item.get("hybrid_score") or 0.0),
                "usable_for": item.get("usable_for"),
                "quality_status": item.get("quality_status"),
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


def _assess_rag_evidence_items(*, query: str, detected_entities: dict[str, Any], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assessed: list[dict[str, Any]] = []
    normalized_query = _normalize_text(query)
    expects_operational_fact = any(token in normalized_query for token in ("stock", "lots disponibles", "combien", "quantite", "quantité", "écart", "ecart", "entrée", "entree", "sortie"))
    query_tokens = {token for token in normalized_query.split() if len(token) >= 4}
    for idx, item in enumerate(items):
        content = str(item.get("content") or "")
        sanitized = _sanitize_chunk_text(content)
        score = float(item.get("final_score") or item.get("hybrid_score") or 0.0)
        metadata = item.get("metadata") or {}
        source_type = str(item.get("source_type") or metadata.get("source_table") or "")
        overlap = _token_overlap_ratio(query_tokens, _normalize_text(sanitized))
        is_noise = _looks_like_raw_noise(sanitized)
        operational_like = _is_operational_source(source_type)
        quality_status = "STRONG"
        reasons: list[str] = []
        if score < 0.25 or overlap < 0.08 or is_noise:
            quality_status = "REJECTED"
            reasons.append("low_relevance_or_noise")
        elif score < 0.42 or overlap < 0.14:
            quality_status = "WEAK"
            reasons.append("weak_relevance")
        elif score < 0.58:
            quality_status = "PARTIAL"
            reasons.append("partial_relevance")
        if expects_operational_fact and operational_like:
            # prevent RAG from appearing as operational source-of-truth for fact queries
            quality_status = "REJECTED"
            reasons.append("operational_sql_required")

        usable_for = _derive_usable_for(query=normalized_query, metadata=metadata, sanitized=sanitized)
        assessed.append(
            {
                **item,
                "source_id": str(item.get("document_id") or item.get("chunk_id") or f"rag:{idx}"),
                "content_excerpt": _compact(sanitized, 180),
                "sanitized_summary": _compact(sanitized, 280),
                "relevance_score": round(score, 4),
                "source_type": source_type or "knowledge_chunks",
                "product_tags": _listify_tags(metadata.get("product"), metadata.get("product_name"), metadata.get("crop")),
                "stage_tags": _listify_tags(metadata.get("stage"), metadata.get("stage_canonical")),
                "usable_for": usable_for,
                "quality_status": quality_status,
                "quality_reasons": reasons,
            }
        )
    return assessed


def _sanitize_chunk_text(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"```.*?```", " ", value, flags=re.DOTALL)
    value = re.sub(r"^\s*#{1,6}\s+.*$", " ", value, flags=re.MULTILINE)
    value = re.sub(r"\[[^\]]*\]\(([^)]+)\)", " ", value)
    value = re.sub(r"(source|file|path|document|url)\s*[:=]\s*\S+", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\|\s*[-:]+\s*\|", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _looks_like_raw_noise(text: str) -> bool:
    lowered = str(text or "").lower()
    if not lowered or len(lowered) < 25:
        return True
    noisy_markers = ("chapter", "table of contents", "copyright", "all rights reserved", "http://", "https://", "source:", "file:")
    if any(marker in lowered for marker in noisy_markers):
        return True
    alpha_chars = sum(1 for ch in lowered if ch.isalpha())
    return alpha_chars < max(20, int(len(lowered) * 0.35))


def _normalize_text(value: str) -> str:
    lowered = str(value or "").lower()
    lowered = lowered.replace("’", "'")
    lowered = lowered.replace("é", "e").replace("è", "e").replace("ê", "e").replace("à", "a").replace("ù", "u").replace("î", "i").replace("ô", "o")
    lowered = re.sub(r"[^a-z0-9\\s-]", " ", lowered)
    return " ".join(lowered.split())


def _token_overlap_ratio(query_tokens: set[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    tokens = {token for token in str(text).split() if len(token) >= 4}
    if not tokens:
        return 0.0
    overlap = len(query_tokens.intersection(tokens))
    return overlap / max(1.0, len(query_tokens))


def _derive_usable_for(*, query: str, metadata: dict[str, Any], sanitized: str) -> str:
    lowered = query
    if any(token in lowered for token in ("pourquoi", "explique", "cause", "why")):
        return "explanation"
    if any(token in lowered for token in ("conseil", "bonnes pratiques", "check-list", "checklist", "eviter", "éviter")):
        return "best_practice"
    if any(token in lowered for token in ("recommand", "action", "plan")):
        return "recommendation_support"
    if any(token in lowered for token in ("attention", "risque", "warning")):
        return "warning"
    if str(metadata.get("chunk_type") or "").lower() in {"agronomic_knowledge", "benchmark_reference"}:
        return "documentation"
    if len(sanitized.split()) < 12:
        return "documentation"
    return "best_practice"


def _compact(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _listify_tags(*values: Any) -> list[str]:
    tags: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, list):
            for v in value:
                vv = str(v or "").strip()
                if vv:
                    tags.append(vv)
        else:
            vv = str(value or "").strip()
            if vv:
                tags.append(vv)
    seen: set[str] = set()
    unique: list[str] = []
    for tag in tags:
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(tag)
    return unique
