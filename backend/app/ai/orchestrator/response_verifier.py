from __future__ import annotations

import re
from dataclasses import dataclass

from app.ai.schemas.agent_schemas import AgentContext, AgentResult, AgentRoute

NUMBER_PATTERN = re.compile(r"\b\d+(?:[\.,]\d+)?\b")
OPERATIONAL_NUMBER_PATTERN = re.compile(
    r"\b\d+(?:[\.,]\d+)?\s*(?:%|kg|tonnes?|t|fcfa|xof)\b|"
    r"\b(?:stock|quantit[eé]|perte|efficacit[eé]|risque|collecte|lot|batch)\b[^.\n]{0,80}\b\d+(?:[\.,]\d+)?\b",
    re.IGNORECASE,
)
PROMPT_INJECTION_MARKERS = (
    "ignore previous instructions",
    "reveal secrets",
    "change system behavior",
)


@dataclass
class VerificationResult:
    grounded: bool
    warnings: list[str]
    missing_expected_source: bool
    weak_retrieval: bool
    incomplete_sql: bool
    contradiction: bool
    weak_ml_confidence: bool


class ResponseVerifier:
    """Response verification for grounded response generation and auditability."""

    def verify(
        self,
        *,
        context: AgentContext,
        answer: str,
        route: AgentRoute,
        results: list[AgentResult],
    ) -> VerificationResult:
        warnings: list[str] = [warning for res in results for warning in res.warnings]
        source_types = {src.get("type") for res in results for src in res.sources}
        has_sql = "sql" in source_types
        has_rag = "rag" in source_types
        has_ml = "ml" in source_types
        has_recommendation_agent = any(res.agent_name == "RecommendationAgent" for res in results)

        numeric_claim = _has_operational_numeric_claim(answer or "")
        if numeric_claim and not (has_sql or has_ml or (route == AgentRoute.RAG_ONLY and has_rag)):
            warnings.append("NUMERIC_CLAIMS_NOT_GROUNDED")

        rag_needed = route in {
            AgentRoute.RAG_ONLY,
            AgentRoute.HYBRID_SQL_RAG,
            AgentRoute.HYBRID_RAG_RECOMMENDATION,
            AgentRoute.HYBRID_FULL,
        }
        if rag_needed and not has_rag:
            warnings.append("MISSING_RAG_SOURCE")

        recommends = any(token in (answer or "").lower() for token in ("recommand", "action", "priorit"))
        if recommends:
            for res in results:
                if res.agent_name == "RecommendationAgent":
                    recs = res.data.get("recommendations") or []
                    if any(not (item.get("evidence") or []) for item in recs):
                        warnings.append("RECOMMENDATION_WITHOUT_EVIDENCE")
                        break
        if has_recommendation_agent:
            rec_result = next((res for res in results if res.agent_name == "RecommendationAgent"), None)
            recs = (rec_result.data.get("recommendations") or []) if rec_result and isinstance(rec_result.data, dict) else []
            if recs and all(not (item.get("evidence") or []) for item in recs if isinstance(item, dict)):
                warnings.append("RECOMMENDATION_WITHOUT_EVIDENCE")

        lowered_answer = (answer or "").lower()
        if any(
            token in lowered_answer
            for token in (
                "inconnu",
                "non disponible",
                "aucun ",
                "aucune ",
                "ne permettent pas de confirmer",
                "données insuffisantes",
            )
        ):
            warnings.append("MISSING_DATA_SIGNALLED")

        contradiction = False
        if has_sql and has_ml:
            contradiction = _is_sql_ml_contradiction(results)
            if contradiction:
                warnings.append("SQL_ML_CONTRADICTION")

        weak_retrieval = False
        for res in results:
            if res.agent_name == "RAGKnowledgeAgent":
                weak_retrieval = bool(res.data.get("weak_retrieval", False))
                if weak_retrieval:
                    warnings.append("WEAK_RETRIEVAL")

        weak_ml_confidence = False
        for res in results:
            if res.agent_name == "MLLossAgent" and float(res.confidence) < 0.55:
                weak_ml_confidence = True
                warnings.append("WEAK_ML_CONFIDENCE")

        incomplete_sql = any(
            "SQL_DATA_INCOMPLETE" in res.warnings or "NO_SQL_DATA" in res.warnings
            for res in results
            if res.agent_name == "SQLAnalyticsAgent"
        )
        if incomplete_sql:
            warnings.append("INCOMPLETE_SQL_DATA")

        if _has_prompt_injection(results):
            warnings.append("PROMPT_INJECTION_DETECTED")

        missing_expected_source = bool(
            (route in {AgentRoute.SQL_ONLY, AgentRoute.HYBRID_SQL_RAG, AgentRoute.HYBRID_SQL_ML, AgentRoute.HYBRID_FULL} and not has_sql)
            or (route in {AgentRoute.ML_ONLY, AgentRoute.HYBRID_SQL_ML, AgentRoute.HYBRID_FULL} and not has_ml)
            or (rag_needed and not has_rag)
        )
        if route in {AgentRoute.RECOMMENDATION_ONLY, AgentRoute.HYBRID_RAG_RECOMMENDATION, AgentRoute.HYBRID_FULL} and not has_recommendation_agent:
            missing_expected_source = True
            warnings.append("MISSING_RECOMMENDATION_SOURCE")

        grounded = not missing_expected_source and "NUMERIC_CLAIMS_NOT_GROUNDED" not in warnings
        return VerificationResult(
            grounded=grounded,
            warnings=sorted(set([*context.warnings, *warnings])),
            missing_expected_source=missing_expected_source,
            weak_retrieval=weak_retrieval,
            incomplete_sql=incomplete_sql,
            contradiction=contradiction,
            weak_ml_confidence=weak_ml_confidence,
        )


def _extract_numeric_values(results: list[AgentResult], agent_name: str) -> list[float]:
    values: list[float] = []
    for res in results:
        if res.agent_name != agent_name:
            continue
        stack = [res.data]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                stack.extend(current.values())
            elif isinstance(current, list):
                stack.extend(current)
            elif isinstance(current, (int, float)):
                values.append(float(current))
    return values


def _derive_sql_risk_from_results(results: list[AgentResult]) -> str:
    sql_result = next((res for res in results if res.agent_name == "SQLAnalyticsAgent"), None)
    if not sql_result or not isinstance(sql_result.data, dict):
        return "unknown"
    data = sql_result.data

    losses: list[float] = []
    efficiencies: list[float] = []
    for row in data.get("process_step_losses", []) or []:
        if isinstance(row, dict) and isinstance(row.get("loss_pct"), (int, float)):
            losses.append(float(row.get("loss_pct")))
    for row in data.get("material_balance", []) or []:
        if isinstance(row, dict):
            if isinstance(row.get("loss_percentage"), (int, float)):
                losses.append(float(row.get("loss_percentage")))
            if isinstance(row.get("efficiency_percentage"), (int, float)):
                efficiencies.append(float(row.get("efficiency_percentage")))
    for row in data.get("batch_summary", []) or []:
        if isinstance(row, dict):
            if isinstance(row.get("loss_pct"), (int, float)):
                losses.append(float(row.get("loss_pct")))
            if isinstance(row.get("efficiency_pct"), (int, float)):
                efficiencies.append(float(row.get("efficiency_pct")))

    max_loss = max(losses) if losses else None
    min_eff = min(efficiencies) if efficiencies else None
    if max_loss is None and min_eff is None:
        return "unknown"
    if (max_loss is not None and max_loss >= 12.0) or (min_eff is not None and min_eff <= 85.0):
        return "high"
    return "low"


def _derive_ml_risk_from_results(results: list[AgentResult]) -> str:
    ml_result = next((res for res in results if res.agent_name == "MLLossAgent"), None)
    if not ml_result or not isinstance(ml_result.data, dict):
        return "unknown"
    risk = str(ml_result.data.get("risk_level") or "").strip().upper()
    if risk == "HIGH":
        return "high"
    if risk == "LOW":
        return "low"
    if risk == "MEDIUM":
        return "medium"
    return "unknown"


def _is_sql_ml_contradiction(results: list[AgentResult]) -> bool:
    sql_values = _extract_numeric_values(results, "SQLAnalyticsAgent")
    ml_values = _extract_numeric_values(results, "MLLossAgent")
    if not sql_values or not ml_values:
        return False
    sql_span = max(sql_values) - min(sql_values)
    ml_span = max(ml_values) - min(ml_values)
    if sql_span <= 0 or ml_span <= 0:
        return False
    return abs(max(sql_values) - max(ml_values)) > max(5.0, sql_span * 0.5)


def _has_operational_numeric_claim(answer: str) -> bool:
    cleaned_lines = []
    in_sources = False
    for line in str(answer or "").splitlines():
        lower = line.strip().lower()
        if lower.startswith("4. sources utilisées") or lower == "sources utilisées":
            in_sources = True
            continue
        if lower.startswith("5. avertissements"):
            in_sources = False
        if in_sources:
            continue
        if re.match(r"^\s*\d+\.\s+\D", line):
            cleaned_lines.append(re.sub(r"^\s*\d+\.\s+", "", line))
        else:
            cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"score=\d+(?:[\.,]\d+)?", "", cleaned, flags=re.IGNORECASE)
    return bool(OPERATIONAL_NUMBER_PATTERN.search(cleaned))


def _has_prompt_injection(results: list[AgentResult]) -> bool:
    for res in results:
        chunks = res.data.get("chunks") if isinstance(res.data, dict) else None
        if not isinstance(chunks, list):
            continue
        for chunk in chunks:
            text = str((chunk or {}).get("content", "")).lower()
            if any(marker in text for marker in PROMPT_INJECTION_MARKERS):
                return True
    return False
