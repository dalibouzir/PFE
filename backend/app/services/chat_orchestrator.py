from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

UTC = timezone.utc
import re
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.batch import Batch
from app.models.ml import MLModelRegistry, MLPredictionLog, MLRecommendationLog, MLTrainingRun
from app.models.user import User
from app.schemas.chat import ChatMetricFact
from app.services.rag_grounding import GroundingSummary, summarize_grounding_quality
from app.services.rag_retrieval_diagnostics import summarize_retrieval

_CHUNK_TYPE_ALIASES = {
    "batch": "batch_summary",
    "batches": "batch_summary",
    "process_step": "process_step_summary",
    "process_steps": "process_step_summary",
    "recommendation": "recommendation_context",
    "recommendations": "recommendation_context",
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


@dataclass
class OrchestratedContext:
    sql_context: dict[str, Any]
    rag_context: dict[str, Any]
    ml_context: dict[str, Any]
    citations: list[dict[str, Any]]
    freshness_summary: dict[str, Any]
    retrieval_summary: dict[str, Any]
    warning_flags: list[str] = field(default_factory=list)
    confidence_estimate: dict[str, Any] = field(default_factory=dict)
    grounding_notes: list[str] = field(default_factory=list)
    contradictory_signals: list[str] = field(default_factory=list)
    scope_analysis: dict[str, Any] = field(default_factory=dict)
    contamination_diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScopeAnalysis:
    scope_level: str
    lot_codes: list[str]
    products: list[str]
    stages: list[str]
    time_hints: list[str]
    benchmark_intent: bool
    comparative_intent: bool


def build_grounded_citation(
    *,
    source_type: str,
    source_table: str,
    source_row_id: str | None,
    chunk_type: str | None,
    retrieval_score: float,
    freshness_timestamp: str | None,
    evidence_snippet: str,
    evidence_reason: str,
) -> dict[str, Any]:
    grounding_confidence = _grounding_confidence_from_score_and_freshness(
        retrieval_score=retrieval_score,
        freshness_timestamp=freshness_timestamp,
    )
    return {
        "citation_id": f"{source_table}:{source_row_id or 'unknown'}:{abs(hash(evidence_snippet)) % 100000}",
        "source_type": source_type,
        "source_table": source_table,
        "source_row_id": source_row_id,
        "chunk_type": chunk_type,
        "retrieval_score": round(float(retrieval_score), 6),
        "freshness_timestamp": freshness_timestamp,
        "evidence_snippet": evidence_snippet,
        "evidence_reason": evidence_reason or "retrieved_for_relevance",
        "grounding_confidence": grounding_confidence,
    }


def orchestrate_context(
    db: Session,
    *,
    current_user: User,
    retrieval_plan: Any,
    message: str,
    retrieval_hits: Sequence[Any],
    context_metrics: Sequence[ChatMetricFact],
    retrieval_filters: dict[str, Any],
) -> OrchestratedContext:
    scope = classify_scope(message)
    sql_context = _build_sql_context(context_metrics)
    rag_context = _build_rag_context(retrieval_hits)
    ml_context = _build_ml_context(db, current_user=current_user, retrieval_hits=retrieval_hits, message=message)
    retrieval_summary = summarize_retrieval(filters=retrieval_filters, hits=retrieval_hits)
    contamination = analyze_scope_contamination(scope=scope, hits=retrieval_hits)
    retrieval_summary["scope_analysis"] = {
        "scope_level": scope.scope_level,
        "lot_codes": scope.lot_codes,
        "products": scope.products,
        "stages": scope.stages,
        "time_hints": scope.time_hints,
        "benchmark_intent": scope.benchmark_intent,
        "comparative_intent": scope.comparative_intent,
    }
    retrieval_summary["scope_contamination"] = contamination
    citations = _build_deduped_citations(retrieval_hits)

    grounding: GroundingSummary = summarize_grounding_quality(
        retrieval_summary=retrieval_summary,
        sql_context=sql_context,
        rag_context=rag_context,
        ml_context=ml_context,
    )
    grounding_notes = list(grounding.grounding_notes)
    if grounding.contradictory_signals and sql_context.get("metrics"):
        grounding_notes.append("Conflicts detected: prioritize SQL operational facts over stale semantic values.")
        if scope.products:
            product_text = ", ".join(scope.products)
            stage_text = ", ".join(scope.stages) if scope.stages else "all stages"
            grounding_notes.append(
                f"Scope clarification: interpret contradictions within {product_text} / {stage_text} first; "
                "cooperative-wide aggregates can include other products and distort product-level reasoning."
            )
    if contamination.get("contamination_risk_score", 0.0) >= 0.3:
        grounding_notes.append("Scope contamination risk detected: unrelated product evidence was deprioritized.")
        grounding.warning_flags = sorted(set([*grounding.warning_flags, "SCOPE_CONTAMINATION_RISK"]))

    return OrchestratedContext(
        sql_context=sql_context,
        rag_context=rag_context,
        ml_context=ml_context,
        citations=citations,
        freshness_summary=retrieval_summary.get("freshness", {}),
        retrieval_summary=retrieval_summary,
        warning_flags=grounding.warning_flags,
        confidence_estimate={"label": grounding.confidence_label, "score": grounding.confidence_score},
        grounding_notes=grounding_notes,
        contradictory_signals=grounding.contradictory_signals,
        scope_analysis=retrieval_summary.get("scope_analysis", {}),
        contamination_diagnostics=contamination,
    )


def _build_sql_context(metrics: Sequence[ChatMetricFact]) -> dict[str, Any]:
    metric_map: dict[str, float] = {}
    for metric in metrics:
        if metric.metric.startswith("retrieval_plan.") or metric.metric.startswith("retrieval_diagnostics."):
            continue
        metric_map[metric.metric] = metric.value
    return {"metrics": metric_map, "metric_count": len(metric_map)}


def _build_rag_context(hits: Sequence[Any]) -> dict[str, Any]:
    loss_values: list[float] = []
    chunk_types: dict[str, int] = {}
    for hit in hits:
        metadata = getattr(hit, "metadata", {}) or {}
        chunk_type = _resolve_chunk_type(metadata=metadata, source_table=str(getattr(hit, "source_table", "unknown")))
        chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
        loss_pct = metadata.get("loss_pct")
        try:
            if loss_pct is not None:
                loss_values.append(float(loss_pct))
        except Exception:
            pass
    return {
        "hit_count": len(hits),
        "chunk_type_counts": chunk_types,
        "loss_pct_values": loss_values,
    }


def _build_ml_context(
    db: Session,
    *,
    current_user: User,
    retrieval_hits: Sequence[Any],
    message: str,
) -> dict[str, Any]:
    batch_ids = _extract_batch_ids(retrieval_hits)
    items: list[dict[str, Any]] = []
    ml_query_error = False
    lowered = message.lower()
    ml_focus = any(
        token in lowered
        for token in ("risk", "risky", "anomaly", "recommendation", "predict", "prediction", "ml", "model", "loss risk")
    )
    model_focus = any(token in lowered for token in ("model", "training", "version", "registry"))

    try:
        if batch_ids:
            prediction_rows = db.scalars(
                select(MLPredictionLog)
                .where(MLPredictionLog.batch_id.in_(list(batch_ids)))
                .order_by(MLPredictionLog.created_at.desc())
                .limit(5)
            ).all()
        else:
            prediction_rows = db.scalars(
                select(MLPredictionLog).order_by(MLPredictionLog.created_at.desc()).limit(5 if ml_focus else 3)
            ).all()
    except Exception:
        prediction_rows = []
        ml_query_error = True

    for row in prediction_rows:
        items.append(
            {
                "batch_id": str(row.batch_id) if row.batch_id else None,
                "predicted_loss_pct": row.predicted_loss_pct,
                "expected_efficiency_pct": row.expected_efficiency_pct,
                "risk_level": row.risk_level.value.upper() if row.risk_level else None,
                "critical_stage": row.critical_stage,
                "anomaly_score": row.anomaly_score,
                "is_anomalous": row.is_anomalous,
                "model_version": row.model_version,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )

    try:
        recommendation_rows = db.scalars(
            select(MLRecommendationLog).order_by(MLRecommendationLog.created_at.desc()).limit(5 if ml_focus else 3)
        ).all()
    except Exception:
        recommendation_rows = []
        ml_query_error = True
    recommendations: list[dict[str, Any]] = []
    for row in recommendation_rows:
        structured = row.structured_recommendation if isinstance(row.structured_recommendation, dict) else {}
        recommendations.append(
            {
                "batch_id": str(row.batch_id) if row.batch_id else None,
                "actions": structured.get("recommended_actions") or [],
                "risk_level": structured.get("risk_level"),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )

    training_runs: list[dict[str, Any]] = []
    if model_focus:
        try:
            run_rows = db.scalars(select(MLTrainingRun).order_by(MLTrainingRun.started_at.desc()).limit(3)).all()
        except Exception:
            run_rows = []
            ml_query_error = True
        for row in run_rows:
            metrics = row.metrics if isinstance(row.metrics, dict) else {}
            training_runs.append(
                {
                    "run_name": row.run_name,
                    "status": row.status,
                    "dataset_rows": row.dataset_rows,
                    "started_at": row.started_at.isoformat() if row.started_at else None,
                    "model_version": metrics.get("model_version"),
                }
            )

    registry_rows: list[dict[str, Any]] = []
    if model_focus:
        try:
            model_rows = db.scalars(select(MLModelRegistry).order_by(MLModelRegistry.created_at.desc()).limit(3)).all()
        except Exception:
            model_rows = []
            ml_query_error = True
        for row in model_rows:
            registry_rows.append(
                {
                    "model_name": row.model_name,
                    "version": row.version,
                    "is_active": row.is_active,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
            )

    primary_pred = items[0] if items else {}
    has_ml_records = bool(items or recommendations or training_runs or registry_rows)
    ml_status = "error" if ml_query_error else ("available" if has_ml_records else "empty")
    return {
        "items": items,
        "recommendations": recommendations,
        "training_runs": training_runs,
        "model_registry": registry_rows,
        "predicted_loss_pct": primary_pred.get("predicted_loss_pct"),
        "risk_level": primary_pred.get("risk_level"),
        "ml_status": ml_status,
        "ml_focus": ml_focus,
        "model_focus": model_focus,
    }


def _extract_batch_ids(hits: Sequence[Any]) -> set[UUID]:
    values: set[UUID] = set()
    for hit in hits:
        metadata = getattr(hit, "metadata", {}) or {}
        raw = metadata.get("batch_id")
        if raw:
            try:
                values.add(UUID(str(raw)))
            except Exception:
                continue
        else:
            ref = str(getattr(hit, "source_record_ref", ""))
            if ref.startswith("batch:"):
                try:
                    values.add(UUID(ref.split(":", 1)[1]))
                except Exception:
                    continue
    return values


def _build_deduped_citations(hits: Sequence[Any]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hit in hits:
        metadata = getattr(hit, "metadata", {}) or {}
        source_table = str(getattr(hit, "source_table", "source"))
        source_row_id = str(metadata.get("source_row_id") or getattr(hit, "source_record_ref", "unknown"))
        freshness_timestamp = _safe_freshness_value(metadata.get("freshness_timestamp"))
        snippet = str(getattr(hit, "content", ""))[:220]
        row = build_grounded_citation(
            source_type="rag_chunk",
            source_table=source_table,
            source_row_id=source_row_id,
            chunk_type=_resolve_chunk_type(metadata=metadata, source_table=source_table),
            retrieval_score=float(getattr(hit, "rerank_score", 0.0)),
            freshness_timestamp=freshness_timestamp,
            evidence_snippet=snippet,
            evidence_reason=str(getattr(hit, "retrieval_reason", "base_rank")),
        )
        dedupe_key = f"{row['source_table']}|{row['source_row_id']}|{row['chunk_type']}|{row['evidence_snippet']}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        citations.append(row)
    return citations


def _grounding_confidence_from_score_and_freshness(*, retrieval_score: float, freshness_timestamp: str | None) -> str:
    score = float(retrieval_score or 0.0)
    if freshness_timestamp:
        try:
            ts = datetime.fromisoformat(str(freshness_timestamp).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            age_hours = (datetime.now(UTC) - ts.astimezone(UTC)).total_seconds() / 3600.0
            if age_hours <= 6:
                score += 0.05
            elif age_hours > 48:
                score -= 0.08
        except Exception:
            pass

    if score >= 0.42:
        return "HIGH"
    if score >= 0.2:
        return "MEDIUM"
    return "LOW"


def _resolve_chunk_type(*, metadata: dict[str, Any], source_table: str) -> str:
    value = str(metadata.get("chunk_type") or metadata.get("entity") or source_table or "unknown").strip().lower()
    value = _CHUNK_TYPE_ALIASES.get(value, value)
    return value or "unknown"


def _safe_freshness_value(raw_value: Any) -> str | None:
    if raw_value is None:
        return None
    try:
        if isinstance(raw_value, datetime):
            ts = raw_value
        else:
            ts = datetime.fromisoformat(str(raw_value).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        return ts.astimezone(UTC).isoformat()
    except Exception:
        return None


def classify_scope(message: str) -> ScopeAnalysis:
    lowered = message.lower()
    tokens = set(re.findall(r"[a-zA-Z0-9_\-']+", lowered))
    lot_codes = sorted({code.upper() for code in re.findall(r"\b(?:LOT|BATCH|DEMO-ML|BENCH-ML)[-_][A-Z0-9\-_]+\b", message, flags=re.IGNORECASE)})
    products = sorted(
        {
            _normalize_product_name(item)
            for key, item in {
                "mangue": "mangue",
                "mango": "mango",
                "mil": "mil",
                "millet": "millet",
                "arachide": "arachide",
                "peanut": "peanut",
                "bissap": "bissap",
            }.items()
            if key in lowered
        }
        - {""}
    )
    stages = sorted(
        {
            item
            for key, item in {
                "drying": "drying",
                "sechage": "drying",
                "séchage": "drying",
                "sorting": "sorting",
                "tri": "sorting",
                "cleaning": "cleaning",
                "nettoyage": "cleaning",
                "packaging": "packaging",
                "emballage": "packaging",
                "storage": "storage",
                "stockage": "storage",
            }.items()
            if key in lowered
        }
    )
    time_hints = sorted(
        hint
        for hint in ("today", "this week", "this month", "yesterday", "latest", "current", "ce mois", "cette semaine")
        if hint in lowered
    )
    benchmark_intent = any(token in lowered for token in ("benchmark", "reference", "literature", "aphlis", "fao", "best practices", "agronomic"))
    comparative_intent = any(token in tokens for token in ("compare", "comparison", "versus", "vs")) or "compared" in lowered

    if lot_codes:
        scope_level = "LOT"
    elif products and stages:
        scope_level = "PRODUCT_STAGE"
    elif products:
        scope_level = "PRODUCT"
    elif benchmark_intent:
        scope_level = "BENCHMARK"
    elif comparative_intent:
        scope_level = "COMPARATIVE"
    else:
        scope_level = "COOPERATIVE"

    return ScopeAnalysis(
        scope_level=scope_level,
        lot_codes=lot_codes,
        products=products,
        stages=stages,
        time_hints=time_hints,
        benchmark_intent=benchmark_intent,
        comparative_intent=comparative_intent,
    )


def analyze_scope_contamination(*, scope: ScopeAnalysis, hits: Sequence[Any]) -> dict[str, Any]:
    if not hits:
        return {
            "unrelated_product_evidence_count": 0,
            "unrelated_scope_penalty": 0.0,
            "contamination_risk_score": 0.0,
            "scope_purity_score": 1.0,
            "product_alignment_score": 0.0,
            "stage_alignment_score": 0.0,
            "operational_priority_score": 0.0,
        }

    benchmark_chunks = {"benchmark_reference", "agronomic_knowledge"}
    unrelated_product = 0
    product_match = 0
    stage_match = 0
    operational_hits = 0

    scope_products = {_normalize_product_name(item) for item in scope.products if item}
    scope_stages = {item.lower() for item in scope.stages}

    for hit in hits:
        metadata = getattr(hit, "metadata", {}) or {}
        chunk_type = _resolve_chunk_type(metadata=metadata, source_table=str(getattr(hit, "source_table", "")))
        if chunk_type not in benchmark_chunks:
            operational_hits += 1

        product_name = _normalize_product_name(str(metadata.get("product_name") or metadata.get("crop") or ""))
        if scope_products and product_name:
            if product_name in scope_products:
                product_match += 1
            else:
                unrelated_product += 1

        stage_value = str(metadata.get("stage_canonical") or metadata.get("stage") or "").lower().strip()
        if scope_stages and stage_value and stage_value in scope_stages:
            stage_match += 1

    hit_count = max(1, len(hits))
    contamination_risk = unrelated_product / hit_count
    unrelated_scope_penalty = round(min(0.45, contamination_risk * 0.6), 4)
    return {
        "unrelated_product_evidence_count": unrelated_product,
        "unrelated_scope_penalty": unrelated_scope_penalty,
        "contamination_risk_score": round(contamination_risk, 4),
        "scope_purity_score": round(max(0.0, 1.0 - contamination_risk), 4),
        "product_alignment_score": round(product_match / hit_count, 4),
        "stage_alignment_score": round(stage_match / hit_count, 4),
        "operational_priority_score": round(operational_hits / hit_count, 4),
    }


def _normalize_product_name(raw: str) -> str:
    value = str(raw or "").lower().strip()
    if not value:
        return ""
    for key, canonical in _PRODUCT_CANONICAL_MAP.items():
        if key in value:
            return canonical
    return value
