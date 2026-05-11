from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


WARNING_STALE_CONTEXT = "STALE_CONTEXT"
WARNING_LOW_GROUNDING_CONFIDENCE = "LOW_GROUNDING_CONFIDENCE"
WARNING_CONTRADICTORY_EVIDENCE = "CONTRADICTORY_EVIDENCE"
WARNING_LIMITED_EVIDENCE = "LIMITED_EVIDENCE"
WARNING_SQL_CONTEXT_MISSING = "SQL_CONTEXT_MISSING"
WARNING_ML_CONTEXT_MISSING = "ML_CONTEXT_MISSING"
WARNING_ML_LOGS_EMPTY = "ML_LOGS_EMPTY"
WARNING_SCOPE_CONTAMINATION_RISK = "SCOPE_CONTAMINATION_RISK"
WARNING_OPERATIONAL_EVIDENCE_SPARSE = "OPERATIONAL_EVIDENCE_SPARSE"
WARNING_BENCHMARK_ONLY_EVIDENCE = "BENCHMARK_ONLY_EVIDENCE"


@dataclass
class GroundingSummary:
    warning_flags: list[str]
    grounding_notes: list[str]
    contradictory_signals: list[str]
    confidence_label: str
    confidence_score: float


def detect_contradictions(
    *,
    sql_context: dict[str, Any],
    rag_context: dict[str, Any],
    ml_context: dict[str, Any],
) -> list[str]:
    contradictions: list[str] = []
    sql_metrics = sql_context.get("metrics", {}) if isinstance(sql_context, dict) else {}
    rag_loss_values = rag_context.get("loss_pct_values", []) if isinstance(rag_context, dict) else []
    ml_prediction_loss = ml_context.get("predicted_loss_pct") if isinstance(ml_context, dict) else None

    sql_avg_loss = _as_float(sql_metrics.get("avg_batch_loss_pct"))
    if sql_avg_loss is not None and rag_loss_values:
        rag_avg = sum(rag_loss_values) / max(1, len(rag_loss_values))
        if abs(sql_avg_loss - rag_avg) >= 15.0:
            contradictions.append(
                f"SQL avg loss ({round(sql_avg_loss,2)}%) conflicts with RAG avg loss ({round(rag_avg,2)}%)."
            )

    if sql_avg_loss is not None and ml_prediction_loss is not None:
        ml_loss = _as_float(ml_prediction_loss)
        if ml_loss is not None and abs(sql_avg_loss - ml_loss) >= 18.0:
            contradictions.append(
                f"SQL avg loss ({round(sql_avg_loss,2)}%) conflicts with ML predicted loss ({round(ml_loss,2)}%)."
            )
    return contradictions


def detect_low_confidence_context(
    *,
    retrieval_summary: dict[str, Any],
    sql_context: dict[str, Any],
    rag_context: dict[str, Any],
    ml_context: dict[str, Any],
    contradictions: Sequence[str],
) -> list[str]:
    warnings: list[str] = []
    hit_count = int(retrieval_summary.get("hit_count", 0) or 0)
    freshness = retrieval_summary.get("freshness", {})
    freshness_avg = _as_float(freshness.get("freshness_avg_minutes"))
    has_sql = bool(sql_context.get("metrics"))
    ml_status = str(ml_context.get("ml_status") or "").lower() if isinstance(ml_context, dict) else ""
    has_ml = bool(ml_context.get("items")) if isinstance(ml_context, dict) else False
    scope_info = retrieval_summary.get("scope_contamination", {}) if isinstance(retrieval_summary, dict) else {}
    contamination_risk = _as_float(scope_info.get("contamination_risk_score")) or 0.0
    operational_priority = _as_float(scope_info.get("operational_priority_score")) or 0.0
    benchmark_only = bool((retrieval_summary.get("chunk_types") or {}).keys()) and operational_priority < 0.25

    if hit_count <= 1:
        warnings.append(WARNING_LIMITED_EVIDENCE)
    if freshness_avg is not None and freshness_avg > 24 * 60:
        warnings.append(WARNING_STALE_CONTEXT)
    if contradictions:
        warnings.append(WARNING_CONTRADICTORY_EVIDENCE)
    if not has_sql:
        warnings.append(WARNING_SQL_CONTEXT_MISSING)
    if ml_status == "empty":
        warnings.append(WARNING_ML_LOGS_EMPTY)
    elif not has_ml:
        warnings.append(WARNING_ML_CONTEXT_MISSING)
    if contamination_risk >= 0.3:
        warnings.append(WARNING_SCOPE_CONTAMINATION_RISK)
    if operational_priority < 0.25 and hit_count > 0:
        warnings.append(WARNING_OPERATIONAL_EVIDENCE_SPARSE)
    if benchmark_only:
        warnings.append(WARNING_BENCHMARK_ONLY_EVIDENCE)

    if hit_count <= 1 or contradictions or not has_sql or contamination_risk >= 0.3:
        warnings.append(WARNING_LOW_GROUNDING_CONFIDENCE)
    return sorted(set(warnings))


def summarize_grounding_quality(
    *,
    retrieval_summary: dict[str, Any],
    sql_context: dict[str, Any],
    rag_context: dict[str, Any],
    ml_context: dict[str, Any],
) -> GroundingSummary:
    contradictions = detect_contradictions(sql_context=sql_context, rag_context=rag_context, ml_context=ml_context)
    warnings = detect_low_confidence_context(
        retrieval_summary=retrieval_summary,
        sql_context=sql_context,
        rag_context=rag_context,
        ml_context=ml_context,
        contradictions=contradictions,
    )

    score = 0.75
    score += min(0.15, (int(retrieval_summary.get("hit_count", 0) or 0) * 0.02))
    if retrieval_summary.get("freshness", {}).get("freshness_avg_minutes") is not None:
        avg = _as_float(retrieval_summary["freshness"]["freshness_avg_minutes"]) or 0.0
        if avg <= 120:
            score += 0.08
        elif avg > 24 * 60:
            score -= 0.1
    if contradictions:
        score -= 0.25
    if WARNING_SQL_CONTEXT_MISSING in warnings:
        score -= 0.12
    if WARNING_LIMITED_EVIDENCE in warnings:
        score -= 0.08
    if WARNING_ML_CONTEXT_MISSING in warnings:
        score -= 0.04
    if WARNING_ML_LOGS_EMPTY in warnings:
        score -= 0.02
    if WARNING_SCOPE_CONTAMINATION_RISK in warnings:
        score -= 0.14
    if WARNING_OPERATIONAL_EVIDENCE_SPARSE in warnings:
        score -= 0.08
    if WARNING_BENCHMARK_ONLY_EVIDENCE in warnings:
        score -= 0.06
    score = max(0.0, min(1.0, score))

    if score >= 0.78:
        label = "HIGH"
    elif score >= 0.52:
        label = "MEDIUM"
    else:
        label = "LOW"

    notes: list[str] = []
    if contradictions:
        notes.append("Contradictory evidence detected across SQL/RAG/ML signals.")
    if retrieval_summary.get("hit_count", 0) == 0:
        notes.append("No semantic retrieval evidence available.")
    if not sql_context.get("metrics"):
        notes.append("No SQL metrics were available for grounding.")
    if not notes:
        notes.append("Grounding quality is consistent with available retrieval evidence.")

    return GroundingSummary(
        warning_flags=warnings,
        grounding_notes=notes,
        contradictory_signals=list(contradictions),
        confidence_label=label,
        confidence_score=round(score, 4),
    )


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None
