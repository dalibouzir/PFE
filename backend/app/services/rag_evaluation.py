from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

_CHUNK_TYPE_ALIASES = {
    "anomaly_context": "anomaly_summary",
    "ml_evaluation_context": "ml_training_context",
    "batch": "batch_summary",
    "process_step": "process_step_summary",
    "recommendation": "recommendation_context",
    "product_stage": "product_stage_summary",
    "lot_status": "lot_status_summary",
    "lot_recommendation": "lot_recommendation_summary",
    "operational_risk": "operational_risk_summary",
    "scoped_loss": "scoped_loss_summary",
}


@dataclass
class EvaluationScenario:
    question: str
    expected_retrieval_domains: list[str] = field(default_factory=list)
    expected_chunk_types: list[str] = field(default_factory=list)
    expected_sql_usage: bool = False
    expected_grounding_behavior: str = "balanced"


def retrieval_relevance_score(retrieval_scores: Sequence[float]) -> float:
    if not retrieval_scores:
        return 0.0
    return max(0.0, min(1.0, sum(retrieval_scores) / (len(retrieval_scores) * 0.6)))


def grounding_score(confidence_score: float, warning_count: int) -> float:
    score = float(confidence_score) - (0.08 * warning_count)
    return max(0.0, min(1.0, score))


def freshness_score(avg_freshness_minutes: float | None) -> float:
    if avg_freshness_minutes is None:
        return 0.5
    if avg_freshness_minutes <= 120:
        return 1.0
    if avg_freshness_minutes <= 24 * 60:
        return 0.8
    if avg_freshness_minutes <= 7 * 24 * 60:
        return 0.6
    return 0.35


def citation_quality_score(citation_count: int, provenance_completeness_ratio: float) -> float:
    quantity = min(1.0, citation_count / 5.0)
    return max(0.0, min(1.0, (quantity * 0.5) + (provenance_completeness_ratio * 0.5)))


def contradiction_rate(contradiction_count: int, evidence_count: int) -> float:
    if evidence_count <= 0:
        return 0.0
    return max(0.0, min(1.0, contradiction_count / evidence_count))


def sql_alignment_score(sql_used: bool, expected_sql_usage: bool, contradictions: int) -> float:
    if expected_sql_usage and not sql_used:
        return 0.2
    base = 1.0 if sql_used == expected_sql_usage else 0.7
    if contradictions > 0:
        base -= 0.2
    return max(0.0, min(1.0, base))


def chunk_diversity_score(unique_chunk_types: int, unique_source_tables: int) -> float:
    return max(0.0, min(1.0, (unique_chunk_types * 0.35) + (unique_source_tables * 0.15)))


def evaluate_scenario_result(
    *,
    scenario: EvaluationScenario,
    debug_payload: dict[str, Any],
) -> dict[str, Any]:
    hits = debug_payload.get("hits", [])
    diagnostics = debug_payload.get("retrieval_diagnostics", {})
    orchestration = debug_payload.get("orchestration", {})
    filters = debug_payload.get("filters", {})
    plan = debug_payload.get("retrieval_plan", {})

    scores = [float(item.get("retrieval_score", 0.0) or 0.0) for item in hits]
    avg_freshness = diagnostics.get("freshness", {}).get("freshness_avg_minutes")
    warnings = orchestration.get("warning_flags", []) or []
    contradictions = orchestration.get("contradictory_signals", []) or []
    confidence_score = float(orchestration.get("confidence_estimate", {}).get("score", 0.0) or 0.0)

    provenance_complete = 0
    for row in hits:
        required = ["chunk_type", "source_table", "source_record_ref", "retrieval_score", "retrieval_reason"]
        if all(row.get(key) is not None for key in required):
            provenance_complete += 1
    provenance_ratio = (provenance_complete / len(hits)) if hits else 0.0

    metrics = {
        "retrieval_relevance_score": retrieval_relevance_score(scores),
        "grounding_score": grounding_score(confidence_score, len(warnings)),
        "freshness_score": freshness_score(avg_freshness),
        "citation_quality_score": citation_quality_score(len(hits), provenance_ratio),
        "contradiction_rate": contradiction_rate(len(contradictions), max(1, len(hits))),
        "SQL_alignment_score": sql_alignment_score(
            sql_used=bool(plan.get("sql_needed")),
            expected_sql_usage=scenario.expected_sql_usage,
            contradictions=len(contradictions),
        ),
        "chunk_diversity_score": chunk_diversity_score(
            diagnostics.get("chunk_diversity", {}).get("chunk_type_unique_count", 0),
            diagnostics.get("chunk_diversity", {}).get("source_table_unique_count", 0),
        ),
    }
    scope_summary = diagnostics.get("scope", {}) if isinstance(diagnostics, dict) else {}
    contamination = orchestration.get("contamination_diagnostics", {}) if isinstance(orchestration, dict) else {}
    metrics["scope_purity_score"] = float(
        scope_summary.get("scope_purity_score", contamination.get("scope_purity_score", 0.0)) or 0.0
    )
    metrics["contamination_rate"] = float(
        scope_summary.get("contamination_rate", contamination.get("contamination_risk_score", 0.0)) or 0.0
    )
    metrics["product_alignment_score"] = float(
        scope_summary.get("product_alignment_score", contamination.get("product_alignment_score", 0.0)) or 0.0
    )
    metrics["stage_alignment_score"] = float(
        scope_summary.get("stage_alignment_score", contamination.get("stage_alignment_score", 0.0)) or 0.0
    )
    metrics["operational_priority_score"] = float(
        scope_summary.get("operational_priority_score", contamination.get("operational_priority_score", 0.0)) or 0.0
    )

    expected_chunk_types = {_normalize_chunk_type(value) for value in scenario.expected_chunk_types if value}
    got_chunk_types = {
        _normalize_chunk_type(row.get("chunk_type"))
        for row in hits
        if _normalize_chunk_type(row.get("chunk_type")) not in {"", "unknown"}
    }
    coverage = 1.0
    if expected_chunk_types:
        coverage = len(expected_chunk_types & got_chunk_types) / len(expected_chunk_types)
    metrics["expected_chunk_coverage"] = round(coverage, 4)
    metrics["expected_chunk_hits"] = sorted(expected_chunk_types & got_chunk_types)
    metrics["observed_chunk_types"] = sorted(got_chunk_types)
    metrics["filters_used_count"] = len([k for k, v in filters.items() if v not in (None, set(), [], {}, "")])
    return metrics


def _normalize_chunk_type(value: Any) -> str:
    key = str(value or "").strip().lower()
    if not key:
        return ""
    return _CHUNK_TYPE_ALIASES.get(key, key)
