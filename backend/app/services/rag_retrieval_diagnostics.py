from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any, Sequence

_CHUNK_TYPE_ALIASES = {
    "batch": "batch_summary",
    "batches": "batch_summary",
    "process_step": "process_step_summary",
    "process_steps": "process_step_summary",
    "recommendation": "recommendation_context",
    "recommendations": "recommendation_context",
    "product_stage": "product_stage_summary",
    "lot_status": "lot_status_summary",
    "lot_recommendation": "lot_recommendation_summary",
    "operational_risk": "operational_risk_summary",
    "scoped_loss": "scoped_loss_summary",
    "anomaly_context": "anomaly_summary",
    "ml_prediction_logs": "ml_prediction_context",
    "ml_training_runs": "ml_evaluation_context",
    "commercial_orders": "commercial_context",
    "parcels": "parcel_context",
    "pre_harvest_steps": "pre_harvest_context",
    "knowledge_chunks": "agronomic_knowledge",
    "reference_metrics": "benchmark_reference",
}
_PRODUCT_CANONICAL_MAP = {
    "mango": "mango",
    "mangue": "mango",
    "mil": "millet",
    "millet": "millet",
    "arachide": "peanut",
    "peanut": "peanut",
    "bissap": "bissap",
}


def _metadata(hit: Any) -> dict[str, Any]:
    row = getattr(hit, "metadata", {}) or {}
    return row if isinstance(row, dict) else {}


def _chunk_type(hit: Any) -> str:
    metadata = _metadata(hit)
    raw = metadata.get("chunk_type") or metadata.get("entity") or getattr(hit, "source_table", None)
    value = str(raw or "unknown").strip().lower()
    value = _CHUNK_TYPE_ALIASES.get(value, value)
    return value or "unknown"


def _freshness_iso(hit: Any) -> str | None:
    metadata = _metadata(hit)
    raw = metadata.get("freshness_timestamp")
    if raw is None:
        return None
    if isinstance(raw, datetime):
        ts = raw
    else:
        try:
            ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except Exception:
            return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC).isoformat()


def summarize_filter_usage(filters: dict[str, Any]) -> dict[str, Any]:
    active = {}
    for key, value in filters.items():
        if value is None:
            continue
        if isinstance(value, (list, set, tuple)) and not value:
            continue
        active[key] = list(value) if isinstance(value, set) else value
    return {"active_filter_count": len(active), "active_filters": active}


def summarize_chunk_types(hits: Sequence[Any]) -> dict[str, Any]:
    counts = Counter(_chunk_type(hit) for hit in hits)
    return dict(counts)


def summarize_freshness_distribution(hits: Sequence[Any]) -> dict[str, Any]:
    ages: list[float] = []
    for hit in hits:
        freshness = _freshness_iso(hit)
        if not freshness:
            continue
        try:
            ts = datetime.fromisoformat(str(freshness).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            age_minutes = max(0.0, (datetime.now(UTC) - ts.astimezone(UTC)).total_seconds() / 60.0)
            ages.append(age_minutes)
        except Exception:
            continue

    if not ages:
        return {"freshness_count": 0}
    return {
        "freshness_count": len(ages),
        "freshness_min_minutes": round(min(ages), 2),
        "freshness_max_minutes": round(max(ages), 2),
        "freshness_avg_minutes": round(sum(ages) / len(ages), 2),
    }


def summarize_retrieval(*, filters: dict[str, Any], hits: Sequence[Any]) -> dict[str, Any]:
    relevance = summarize_retrieval_relevance(hits)
    diversity = summarize_chunk_diversity(hits)
    freshness = summarize_freshness_distribution(hits)
    freshness_quality = summarize_freshness_quality(freshness)
    contradiction = summarize_contradiction_summary()
    sql_rag_agreement = summarize_sql_rag_agreement()
    scope = summarize_scope_purity(filters=filters, hits=hits)
    return {
        "filters": summarize_filter_usage(filters),
        "chunk_types": summarize_chunk_types(hits),
        "freshness": freshness,
        "relevance": relevance,
        "chunk_diversity": diversity,
        "scope": scope,
        "freshness_quality": freshness_quality,
        "contradiction_summary": contradiction,
        "sql_rag_agreement": sql_rag_agreement,
        "hit_count": len(hits),
    }


def summarize_retrieval_relevance(hits: Sequence[Any]) -> dict[str, Any]:
    scores = [float(getattr(hit, "rerank_score", 0.0) or 0.0) for hit in hits]
    if not scores:
        return {"avg_score": 0.0, "max_score": 0.0}
    return {
        "avg_score": round(sum(scores) / len(scores), 6),
        "max_score": round(max(scores), 6),
    }


def summarize_chunk_diversity(hits: Sequence[Any]) -> dict[str, Any]:
    chunk_types = [_chunk_type(hit) for hit in hits]
    source_tables = [str(getattr(hit, "source_table", "unknown")) for hit in hits]
    return {
        "chunk_type_unique_count": len(set(chunk_types)),
        "source_table_unique_count": len(set(source_tables)),
    }


def summarize_freshness_quality(freshness_summary: dict[str, Any]) -> dict[str, Any]:
    avg = float(freshness_summary.get("freshness_avg_minutes", 0.0) or 0.0)
    if avg <= 0:
        score = 0.5
    elif avg <= 120:
        score = 0.95
    elif avg <= 24 * 60:
        score = 0.75
    elif avg <= 7 * 24 * 60:
        score = 0.5
    else:
        score = 0.3
    return {"freshness_quality_score": round(score, 4)}


def summarize_grounding_confidence_summary(confidence_score: float, warning_flags: Sequence[str]) -> dict[str, Any]:
    level = "HIGH" if confidence_score >= 0.78 else "MEDIUM" if confidence_score >= 0.52 else "LOW"
    return {
        "confidence_score": round(float(confidence_score), 4),
        "confidence_level": level,
        "warning_count": len(list(warning_flags)),
    }


def summarize_contradiction_summary(contradictions: Sequence[str] | None = None) -> dict[str, Any]:
    contradictions = list(contradictions or [])
    return {
        "contradiction_count": len(contradictions),
        "contradictions": contradictions[:3],
    }


def summarize_sql_rag_agreement(sql_available: bool = True, rag_available: bool = True, contradictory: bool = False) -> dict[str, Any]:
    if not sql_available and not rag_available:
        alignment = "none"
    elif contradictory:
        alignment = "conflict"
    elif sql_available and rag_available:
        alignment = "aligned"
    else:
        alignment = "partial"
    return {"alignment": alignment}


def summarize_scope_purity(*, filters: dict[str, Any], hits: Sequence[Any]) -> dict[str, Any]:
    product_filters = {_normalize_product_name(str(item)) for item in (filters.get("product_name") or set()) if str(item).strip()}
    stage_filters = {str(item).lower() for item in (filters.get("stage_canonical") or set())}
    chunk_type_filters = {str(item).lower() for item in (filters.get("chunk_type") or set())}
    source_filters = {str(item).lower() for item in (filters.get("source_table") or set())}
    benchmark_chunks = {"benchmark_reference", "agronomic_knowledge"}
    benchmark_tables = {"reference_metrics", "knowledge_chunks"}
    benchmark_only_intent = bool(
        (chunk_type_filters and chunk_type_filters.issubset(benchmark_chunks))
        or (source_filters and source_filters.issubset(benchmark_tables))
    )

    if not hits:
        return {
            "scope_purity_score": 1.0,
            "contamination_rate": 0.0,
            "product_alignment_score": 0.0,
            "stage_alignment_score": 0.0,
            "operational_priority_score": 0.0,
            "unrelated_product_evidence_count": 0,
            "unrelated_scope_penalty": 0.0,
            "contamination_risk_score": 0.0,
        }

    unrelated_product_count = 0
    product_match_count = 0
    stage_match_count = 0
    operational_count = 0

    for hit in hits:
        metadata = _metadata(hit)
        chunk_type = _chunk_type(hit)
        if chunk_type not in benchmark_chunks:
            operational_count += 1

        product_name = _normalize_product_name(str(metadata.get("product_name") or metadata.get("crop") or ""))
        if product_filters and product_name:
            if product_name in product_filters:
                product_match_count += 1
            else:
                unrelated_product_count += 1

        stage_name = str(metadata.get("stage_canonical") or metadata.get("stage") or "").lower().strip()
        if stage_filters and stage_name and stage_name in stage_filters:
            stage_match_count += 1

    hit_count = max(1, len(hits))
    contamination_rate = unrelated_product_count / hit_count
    operational_priority_score = operational_count / hit_count if not benchmark_only_intent else (1.0 - (operational_count / hit_count))
    return {
        "scope_purity_score": round(max(0.0, 1.0 - contamination_rate), 4),
        "contamination_rate": round(contamination_rate, 4),
        "product_alignment_score": round(product_match_count / hit_count, 4),
        "stage_alignment_score": round(stage_match_count / hit_count, 4),
        "operational_priority_score": round(max(0.0, min(1.0, operational_priority_score)), 4),
        "unrelated_product_evidence_count": unrelated_product_count,
        "unrelated_scope_penalty": round(min(0.45, contamination_rate * 0.6), 4),
        "contamination_risk_score": round(contamination_rate, 4),
    }


def _normalize_product_name(raw: str) -> str:
    value = str(raw or "").lower().strip()
    if not value:
        return ""
    for key, canonical in _PRODUCT_CANONICAL_MAP.items():
        if key in value:
            return canonical
    return value
