from __future__ import annotations

import json
import math
import re
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.rag import RAGChunk, RAGDocument
from app.models.user import User
from app.services.rag_embeddings import embed_texts


class HybridRetriever:
    """Hybrid SQL/RAG retrieval with controlled fallback for SQLite and missing embeddings."""

    def __init__(self, db: Session, current_user: User):
        self.db = db
        self.current_user = current_user

    def retrieve(self, *, query: str, filters: dict, top_k: int = 12) -> list[dict[str, Any]]:
        diagnostics = self.retrieve_with_diagnostics(query=query, filters=filters, top_k=top_k)
        return diagnostics.get("results", [])

    def retrieve_with_diagnostics(self, *, query: str, filters: dict, top_k: int = 12) -> dict[str, Any]:
        if not settings.rag_enabled or not self.current_user.cooperative_id:
            return {
                "results": [],
                "timing_ms": {
                    "embedding_ms": 0,
                    "vector_search_ms": 0,
                    "keyword_search_ms": 0,
                    "metadata_filter_ms": 0,
                    "merge_rank_ms": 0,
                    "total_retrieval_ms": 0,
                },
                "counts": {"vector_candidates": 0, "keyword_candidates": 0, "merged_candidates": 0},
            }

        total_started = time.perf_counter()
        vector_rows, vector_debug = self._vector_candidates_with_timing(query=query, k=max(24, top_k * 2))
        keyword_rows, keyword_debug = self._keyword_candidates_with_timing(query=query, k=max(24, top_k * 2))

        merged: dict[str, dict[str, Any]] = {}
        merge_started = time.perf_counter()

        for idx, row in enumerate(vector_rows, start=1):
            chunk_id = str(row.get("chunk_id"))
            item = _normalize_row(row)
            vector_distance = float(row.get("distance") or 1.0)
            item["vector_score"] = max(0.0, 1.0 - min(vector_distance, 1.0))
            item["keyword_score"] = 0.0
            item["hybrid_score"] = 0.70 * item["vector_score"]
            item["vector_rank"] = idx
            merged[chunk_id] = item

        for idx, row in enumerate(keyword_rows, start=1):
            chunk_id = str(row.get("chunk_id"))
            kw_score = float(row.get("keyword_score") or 0.0)
            if chunk_id in merged:
                merged[chunk_id]["keyword_score"] = kw_score
                merged[chunk_id]["hybrid_score"] = 0.70 * float(merged[chunk_id]["vector_score"]) + 0.30 * kw_score
                merged[chunk_id]["keyword_rank"] = idx
                continue
            item = _normalize_row(row)
            item["vector_score"] = _token_overlap_score(query, item.get("content", ""))
            item["keyword_score"] = kw_score
            item["hybrid_score"] = 0.70 * item["vector_score"] + 0.30 * kw_score
            item["keyword_rank"] = idx
            merged[chunk_id] = item

        merge_rank_ms = int((time.perf_counter() - merge_started) * 1000)
        filter_started = time.perf_counter()
        filtered = _apply_soft_filters(list(merged.values()), filters=filters)
        metadata_filter_ms = int((time.perf_counter() - filter_started) * 1000)
        filtered.sort(key=lambda it: float(it.get("hybrid_score", 0.0)), reverse=True)
        return {
            "results": filtered[:top_k],
            "timing_ms": {
                "embedding_ms": int(vector_debug.get("embedding_ms", 0) or 0),
                "vector_search_ms": int(vector_debug.get("vector_search_ms", 0) or 0),
                "keyword_search_ms": int(keyword_debug.get("keyword_search_ms", 0) or 0),
                "metadata_filter_ms": metadata_filter_ms,
                "merge_rank_ms": merge_rank_ms,
                "total_retrieval_ms": int((time.perf_counter() - total_started) * 1000),
            },
            "counts": {
                "vector_candidates": len(vector_rows),
                "keyword_candidates": len(keyword_rows),
                "merged_candidates": len(merged),
            },
        }

    def _vector_candidates(self, *, query: str, k: int) -> list[dict[str, Any]]:
        rows, _ = self._vector_candidates_with_timing(query=query, k=k)
        return rows

    def _vector_candidates_with_timing(self, *, query: str, k: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
        bind = self.db.get_bind()
        if bind is None:
            return [], {"embedding_ms": 0, "vector_search_ms": 0}
        if bind.dialect.name != "postgresql":
            return [], {"embedding_ms": 0, "vector_search_ms": 0}

        try:
            embed_started = time.perf_counter()
            embedding = embed_texts([query])[0]
            embedding_ms = int((time.perf_counter() - embed_started) * 1000)
            vector_literal = "[" + ",".join(f"{float(value):.8f}" for value in embedding) + "]"
            stmt = text(
                """
                SELECT
                    c.id AS chunk_id,
                    d.id AS document_id,
                    COALESCE(d.title, d.source_table) AS title,
                    c.content AS content,
                    c.metadata_json AS chunk_metadata_json,
                    d.metadata_json AS doc_metadata_json,
                    d.source_table AS source_type,
                    (c.embedding <=> CAST(:embedding AS vector)) AS distance
                FROM rag_chunks c
                JOIN rag_documents d ON d.id = c.document_id
                WHERE c.cooperative_id = :cooperative_id
                ORDER BY c.embedding <=> CAST(:embedding AS vector)
                LIMIT :k
                """
            )
            query_started = time.perf_counter()
            rows = self.db.execute(
                stmt,
                {
                    "cooperative_id": self.current_user.cooperative_id,
                    "embedding": vector_literal,
                    "k": k,
                },
            ).mappings().all()
            vector_search_ms = int((time.perf_counter() - query_started) * 1000)
            return rows, {"embedding_ms": embedding_ms, "vector_search_ms": vector_search_ms}
        except Exception:
            return [], {"embedding_ms": 0, "vector_search_ms": 0}

    def _keyword_candidates(self, *, query: str, k: int) -> list[dict[str, Any]]:
        rows, _ = self._keyword_candidates_with_timing(query=query, k=k)
        return rows

    def _keyword_candidates_with_timing(self, *, query: str, k: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
        bind = self.db.get_bind()
        if bind is None:
            return [], {"keyword_search_ms": 0}

        if bind.dialect.name == "postgresql":
            try:
                stmt = text(
                    """
                    SELECT
                        c.id AS chunk_id,
                        d.id AS document_id,
                        COALESCE(d.title, d.source_table) AS title,
                        c.content AS content,
                        c.metadata_json AS chunk_metadata_json,
                        d.metadata_json AS doc_metadata_json,
                        d.source_table AS source_type,
                        ts_rank_cd(to_tsvector('simple', c.content), websearch_to_tsquery('simple', :query)) AS keyword_score
                    FROM rag_chunks c
                    JOIN rag_documents d ON d.id = c.document_id
                    WHERE c.cooperative_id = :cooperative_id
                      AND to_tsvector('simple', c.content) @@ websearch_to_tsquery('simple', :query)
                    ORDER BY keyword_score DESC
                    LIMIT :k
                    """
                )
                started = time.perf_counter()
                rows = self.db.execute(
                    stmt,
                    {
                        "cooperative_id": self.current_user.cooperative_id,
                        "query": query,
                        "k": k,
                    },
                ).mappings().all()
                if rows:
                    return rows, {"keyword_search_ms": int((time.perf_counter() - started) * 1000)}
            except Exception:
                pass

        return self._keyword_scan_candidates_with_timing(query=query, k=k)

    def _keyword_scan_candidates(self, *, query: str, k: int) -> list[dict[str, Any]]:
        rows, _ = self._keyword_scan_candidates_with_timing(query=query, k=k)
        return rows

    def _keyword_scan_candidates_with_timing(self, *, query: str, k: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
        try:
            started = time.perf_counter()
            rows = self.db.execute(
                text(
                    """
                    SELECT
                        c.id AS chunk_id,
                        d.id AS document_id,
                        COALESCE(d.title, d.source_table) AS title,
                        c.content AS content,
                        c.metadata_json AS chunk_metadata_json,
                        d.metadata_json AS doc_metadata_json,
                        d.source_table AS source_type
                    FROM rag_chunks c
                    JOIN rag_documents d ON d.id = c.document_id
                    WHERE c.cooperative_id = :cooperative_id
                    LIMIT :scan_k
                    """
                ),
                {
                    "cooperative_id": self.current_user.cooperative_id,
                    "scan_k": max(k * 50, 1000),
                },
            ).mappings().all()
        except Exception:
            return [], {"keyword_search_ms": 0}

        items = []
        for row in rows:
            as_dict = dict(row)
            as_dict["keyword_score"] = _token_overlap_score(query, str(as_dict.get("content") or ""))
            if as_dict["keyword_score"] > 0:
                items.append(as_dict)
        items.sort(key=lambda item: float(item.get("keyword_score", 0.0)), reverse=True)
        return items[:k], {"keyword_search_ms": int((time.perf_counter() - started) * 1000)}


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    chunk_meta = _to_dict(row.get("chunk_metadata_json"))
    doc_meta = _to_dict(row.get("doc_metadata_json"))
    metadata = {**doc_meta, **chunk_meta}
    return {
        "document_id": str(row.get("document_id")),
        "chunk_id": str(row.get("chunk_id")),
        "title": str(row.get("title") or "Document"),
        "content": str(row.get("content") or ""),
        "metadata": metadata,
        "source_type": str(row.get("source_type") or "rag_chunks"),
    }


def _to_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _apply_soft_filters(items: list[dict[str, Any]], *, filters: dict) -> list[dict[str, Any]]:
    if not items:
        return []
    products = {str(p).lower() for p in (filters.get("product") or set())}
    stages = {str(s).lower() for s in (filters.get("stage") or set())}
    batch_ref = str(filters.get("batch_ref") or "").upper()
    prefer_knowledge_sources = bool(filters.get("prefer_knowledge_sources"))
    avoid_operational_sources = bool(filters.get("avoid_operational_sources"))

    for item in items:
        meta = item.get("metadata") or {}
        boost = 0.0

        if products:
            meta_product = str(meta.get("product") or meta.get("product_name") or meta.get("crop") or "").lower()
            if meta_product in products:
                boost += 0.2

        if stages:
            meta_stage = str(meta.get("stage") or meta.get("stage_canonical") or "").lower()
            if meta_stage in stages:
                boost += 0.2

        if batch_ref:
            meta_batch = str(meta.get("batch_code") or meta.get("batch_ref") or "").upper()
            if meta_batch == batch_ref:
                boost += 0.2

        if prefer_knowledge_sources:
            source_type = str(item.get("source_type") or "").lower()
            topic = str(meta.get("topic") or meta.get("chunk_type") or "").lower()
            if any(token in source_type for token in ("knowledge", "reference", "guide", "best_practice")) or any(
                token in topic for token in ("best_practice", "good_practice", "guidance", "stockage", "tri", "sechage", "séchage", "humidite", "humidité", "conditionnement", "casse")
            ):
                boost += 0.25
            elif avoid_operational_sources and any(
                token in source_type
                for token in (
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
                )
            ):
                boost -= 0.2

        item["hybrid_score"] = min(1.0, float(item.get("hybrid_score", 0.0)) + boost)

    return items


def _token_overlap_score(query: str, content: str) -> float:
    q_tokens = [token for token in re.findall(r"[\w\-]+", str(query).lower()) if len(token) > 2]
    c_tokens = set(token for token in re.findall(r"[\w\-]+", str(content).lower()) if len(token) > 2)
    if not q_tokens:
        return 0.0
    hit = sum(1 for token in q_tokens if token in c_tokens)
    return hit / max(1, len(q_tokens))
