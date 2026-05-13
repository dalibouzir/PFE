from __future__ import annotations

from statistics import fmean

from app.ai.schemas.agent_schemas import AgentResult


def compute_final_confidence(
    *,
    agent_results: list[AgentResult],
    route_confidence: float,
    missing_expected_source: bool,
    weak_retrieval: bool,
    incomplete_sql: bool,
    contradiction: bool,
    weak_ml_confidence: bool,
) -> float:
    scores = [max(0.0, min(1.0, float(item.confidence))) for item in agent_results]
    base = fmean(scores) if scores else route_confidence
    penalty = 0.0
    if missing_expected_source:
        penalty += 0.15
    if weak_retrieval:
        penalty += 0.10
    if incomplete_sql:
        penalty += 0.15
    if contradiction:
        penalty += 0.20
    if weak_ml_confidence:
        penalty += 0.10
    return max(0.0, min(1.0, base - penalty))
