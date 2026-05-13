from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def rerank_chunks(candidates: list[dict[str, Any]], *, detected_entities: dict, top_k: int = 5) -> list[dict[str, Any]]:
    products = {str(p).lower() for p in (detected_entities.get("product") or [])}
    stages = {str(s).lower() for s in (detected_entities.get("stage") or [])}
    topics = {str(t).lower() for t in (detected_entities.get("metric") or [])}

    for item in candidates:
        metadata = item.get("metadata") or {}
        hybrid_score = float(item.get("hybrid_score") or 0.0)

        stage_match = 1.0 if _meta_value(metadata, ("stage", "stage_canonical")) in stages else 0.0
        product_match = 1.0 if _meta_value(metadata, ("product", "product_name", "crop")) in products else 0.0
        topic_match = 1.0 if _meta_topic(metadata) in topics else 0.0
        recency_score = _recency_score(metadata)
        knowledge_match = _knowledge_source_score(item)

        final = (
            0.45 * hybrid_score
            + 0.20 * stage_match
            + 0.15 * product_match
            + 0.10 * topic_match
            + 0.05 * recency_score
            + 0.05 * knowledge_match
        )
        item["final_score"] = final

    ranked = sorted(candidates, key=lambda row: float(row.get("final_score", 0.0)), reverse=True)
    return ranked[:top_k]


def _meta_value(metadata: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(metadata.get(key) or "").lower().strip()
        if value:
            return value
    return ""


def _meta_topic(metadata: dict[str, Any]) -> str:
    return str(metadata.get("topic") or metadata.get("chunk_type") or "").lower().strip()


def _recency_score(metadata: dict[str, Any]) -> float:
    raw = metadata.get("updated_at") or metadata.get("created_at") or metadata.get("freshness_timestamp")
    if not raw:
        return 0.4
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return 0.4
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 3600.0)
    if age_hours <= 24:
        return 1.0
    if age_hours <= 24 * 7:
        return 0.8
    if age_hours <= 24 * 30:
        return 0.6
    return 0.3


def _knowledge_source_score(item: dict[str, Any]) -> float:
    source_type = str(item.get("source_type") or "").lower()
    metadata = item.get("metadata") or {}
    chunk_type = str(metadata.get("chunk_type") or metadata.get("topic") or "").lower()
    title = str(item.get("title") or "").lower()
    if source_type in {"knowledge_chunks", "reference_metrics"}:
        return 1.0
    if chunk_type in {"agronomic_knowledge", "benchmark_reference"}:
        return 1.0
    if title.startswith("knowledge "):
        return 1.0
    if source_type in {"ml_recommendation_logs", "ml_prediction_logs"}:
        return -1.0
    return 0.0
