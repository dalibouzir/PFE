from __future__ import annotations

from typing import Any

from app.ai.schemas.agent_schemas import AgentResult, AgentRoute


SOURCE_TYPE_CANONICAL = {
    "sql": "SQL",
    "rag": "RAG",
    "ml": "ML",
    "recommendation": "RECOMMENDATION",
}


def build_source_contract(*, route: AgentRoute, agent_results: list[AgentResult]) -> tuple[list[dict[str, Any]], list[str]]:
    raw_sources = _merge_and_dedupe_sources(*[item.sources for item in agent_results])
    normalized = [_normalize_source_entry(source) for source in raw_sources]

    recommendation_source = _build_recommendation_source(agent_results)
    if recommendation_source:
        normalized.append(recommendation_source)

    normalized.extend(_missing_expected_source_placeholders(route=route, normalized_sources=normalized))
    normalized = _dedupe_contract_sources(normalized)
    warnings = _contract_warnings(route=route, normalized_sources=normalized)
    normalized = _attach_source_warnings(normalized, warnings)
    return normalized, warnings


def merge_and_dedupe_sources(*source_groups: list[dict]) -> list[dict]:
    # Backward-compatible helper kept for existing call sites.
    return _merge_and_dedupe_sources(*source_groups)


def _merge_and_dedupe_sources(*source_groups: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for group in source_groups:
        for source in group:
            key = str(source)
            if key in seen:
                continue
            seen.add(key)
            merged.append(source)
    return merged


def _normalize_source_entry(source: dict[str, Any]) -> dict[str, Any]:
    base = dict(source or {})
    source_type_raw = str(base.get("type") or base.get("source_type") or "").strip().lower()
    if source_type_raw not in SOURCE_TYPE_CANONICAL:
        source_type_raw = "sql" if base.get("table") else "rag" if base.get("document_id") or base.get("chunk_id") else "ml" if base.get("model") else "recommendation"

    source_type = SOURCE_TYPE_CANONICAL.get(source_type_raw, "SQL")
    source_name = _source_name(base=base, source_type_raw=source_type_raw)
    source_ref = _source_reference(base=base)
    confidence = _source_confidence(base=base)
    used_for = _used_for(source_type_raw)
    warning = _source_level_warning(base=base, source_type_raw=source_type_raw)

    normalized = {
        "type": source_type_raw,
        "source_type": source_type,
        "source_name": source_name,
        "source_reference": source_ref,
        "source_id": str(base.get("result_id") or base.get("chunk_id") or base.get("document_id") or base.get("related_batch") or ""),
        "confidence": confidence,
        "used_for": used_for,
        "warning": warning,
        "evidence_status": str(base.get("evidence_status") or ""),
        # Keep compatibility fields used by existing response adapters/tests.
        "table": base.get("table"),
        "label": str(base.get("label") or source_name),
        "record_count": base.get("record_count"),
        "document_id": base.get("document_id"),
        "chunk_id": base.get("chunk_id"),
        "title": str(base.get("title") or source_name) if source_type_raw == "rag" else base.get("title"),
        "model": str(base.get("model") or source_name) if source_type_raw == "ml" else base.get("model"),
        "score": base.get("score"),
        "risk_level": base.get("risk_level"),
        "related_batch": base.get("related_batch"),
        "related_product": base.get("related_product"),
        "related_stage": base.get("related_stage"),
    }
    return normalized


def _source_name(*, base: dict[str, Any], source_type_raw: str) -> str:
    if source_type_raw == "sql":
        table = str(base.get("table") or "operational_data")
        return table
    if source_type_raw == "rag":
        return str(base.get("title") or base.get("document_id") or "rag_document")
    if source_type_raw == "ml":
        return str(base.get("model") or "ml_model")
    return str(base.get("label") or "recommendation_evidence")


def _source_reference(*, base: dict[str, Any]) -> str:
    ref = base.get("source_id") or base.get("chunk_id") or base.get("document_id") or base.get("result_id") or base.get("related_batch")
    return str(ref or "")


def _source_confidence(*, base: dict[str, Any]) -> float | None:
    for key in ("score", "final_score", "confidence"):
        value = base.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _used_for(source_type_raw: str) -> str:
    mapping = {
        "sql": "operational_fact",
        "rag": "best_practice",
        "ml": "risk_signal",
        "recommendation": "recommendation_evidence",
    }
    return mapping.get(source_type_raw, "operational_fact")


def _source_level_warning(*, base: dict[str, Any], source_type_raw: str) -> str | None:
    evidence_status = str(base.get("evidence_status") or "").strip().upper()
    if evidence_status == "PROVEN_NO_DATA":
        return None
    if source_type_raw == "rag":
        score = base.get("score")
        if isinstance(score, (int, float)) and float(score) < 0.35:
            return "WEAK_SOURCE"
    if source_type_raw == "sql" and int(base.get("record_count") or 0) == 0:
        return "MISSING_SOURCE_DATA"
    if source_type_raw == "ml" and str(base.get("risk_level") or "").lower() in {"unknown", "none", ""}:
        return "WEAK_SOURCE"
    return None


def _build_recommendation_source(agent_results: list[AgentResult]) -> dict[str, Any] | None:
    rec_result = next((item for item in agent_results if item.agent_name == "RecommendationAgent"), None)
    if not rec_result:
        return None
    recommendations = rec_result.data.get("recommendations") if isinstance(rec_result.data, dict) else []
    rec_count = len(recommendations) if isinstance(recommendations, list) else 0
    has_evidence = False
    if isinstance(recommendations, list):
        for rec in recommendations:
            refs = rec.get("evidence_refs") if isinstance(rec, dict) else None
            if isinstance(refs, list) and any(
                isinstance(ref, dict)
                and str(ref.get("type") or "").upper() in {"SQL", "RAG", "ML", "RULE"}
                and not (
                    str(ref.get("type") or "").upper() == "RAG"
                    and str(ref.get("quality_status") or "").upper() in {"WEAK", "REJECTED"}
                )
                and str(ref.get("source_id") or "").strip()
                for ref in refs
            ):
                has_evidence = True
                break
    warning = None
    if rec_count > 0 and not has_evidence:
        warning = "MISSING_RECOMMENDATION_EVIDENCE"
    return {
        "type": "recommendation",
        "source_type": "RECOMMENDATION",
        "source_name": "recommendation_engine",
        "source_reference": f"recommendations:{rec_count}",
        "source_id": "recommendation_engine",
        "confidence": float(rec_result.confidence),
        "used_for": "recommendation_evidence",
        "warning": warning,
        "label": "Recommendation evidence",
        "title": "Recommendation evidence",
        "model": None,
    }


def _dedupe_contract_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in sources:
        key = "|".join(
            [
                str(source.get("type") or ""),
                str(source.get("source_name") or ""),
                str(source.get("source_reference") or ""),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)
    return deduped


def _contract_warnings(*, route: AgentRoute, normalized_sources: list[dict[str, Any]]) -> list[str]:
    types = {str(item.get("type") or "").lower() for item in normalized_sources}
    warnings: list[str] = []

    if route in {AgentRoute.SQL_ONLY, AgentRoute.HYBRID_SQL_RAG, AgentRoute.HYBRID_SQL_ML, AgentRoute.HYBRID_FULL} and "sql" not in types:
        warnings.append("MISSING_SQL_SOURCE")
    if route in {AgentRoute.RAG_ONLY, AgentRoute.HYBRID_SQL_RAG, AgentRoute.HYBRID_RAG_RECOMMENDATION, AgentRoute.HYBRID_FULL} and "rag" not in types:
        warnings.append("MISSING_RAG_SOURCE")
    if route in {AgentRoute.ML_ONLY, AgentRoute.HYBRID_SQL_ML, AgentRoute.HYBRID_FULL} and "ml" not in types:
        warnings.append("MISSING_ML_SOURCE")
    if route in {AgentRoute.RECOMMENDATION_ONLY, AgentRoute.HYBRID_RAG_RECOMMENDATION, AgentRoute.HYBRID_FULL} and "recommendation" not in types:
        warnings.append("MISSING_RECOMMENDATION_SOURCE")

    if any(item.get("warning") == "WEAK_SOURCE" for item in normalized_sources):
        warnings.append("WEAK_SOURCE")
    if any(item.get("warning") == "MISSING_SOURCE_DATA" for item in normalized_sources):
        warnings.append("SOURCE_DATA_EMPTY")
    if any(item.get("warning") == "MISSING_RECOMMENDATION_EVIDENCE" for item in normalized_sources):
        warnings.append("RECOMMENDATION_WITHOUT_EVIDENCE")
    for source in normalized_sources:
        warning = str(source.get("warning") or "").strip().upper()
        if warning in {"MISSING_SQL_SOURCE", "MISSING_RAG_SOURCE", "MISSING_ML_SOURCE", "MISSING_RECOMMENDATION_SOURCE"}:
            warnings.append(warning)

    return sorted(set(warnings))


def _missing_expected_source_placeholders(*, route: AgentRoute, normalized_sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    types = {str(item.get("type") or "").lower() for item in normalized_sources}
    placeholders: list[dict[str, Any]] = []

    def add_placeholder(raw_type: str, warning: str) -> None:
        placeholders.append(
            {
                "type": raw_type,
                "source_type": SOURCE_TYPE_CANONICAL.get(raw_type, raw_type.upper()),
                "source_name": f"{raw_type}_source_missing",
                "source_reference": "not_available",
                "source_id": "",
                "confidence": None,
                "used_for": _used_for(raw_type),
                "warning": warning,
                "label": f"{raw_type.upper()} source missing",
                "title": f"{raw_type.upper()} source missing",
                "model": None if raw_type != "ml" else "ml_source_missing",
            }
        )

    if route in {AgentRoute.SQL_ONLY, AgentRoute.HYBRID_SQL_RAG, AgentRoute.HYBRID_SQL_ML, AgentRoute.HYBRID_FULL} and "sql" not in types:
        add_placeholder("sql", "MISSING_SQL_SOURCE")
    if route in {AgentRoute.RAG_ONLY, AgentRoute.HYBRID_SQL_RAG, AgentRoute.HYBRID_RAG_RECOMMENDATION, AgentRoute.HYBRID_FULL} and "rag" not in types:
        add_placeholder("rag", "MISSING_RAG_SOURCE")
    if route in {AgentRoute.ML_ONLY, AgentRoute.HYBRID_SQL_ML, AgentRoute.HYBRID_FULL} and "ml" not in types:
        add_placeholder("ml", "MISSING_ML_SOURCE")
    if route in {AgentRoute.RECOMMENDATION_ONLY, AgentRoute.HYBRID_RAG_RECOMMENDATION, AgentRoute.HYBRID_FULL} and "recommendation" not in types:
        add_placeholder("recommendation", "MISSING_RECOMMENDATION_SOURCE")
    return placeholders


def _attach_source_warnings(sources: list[dict[str, Any]], warnings: list[str]) -> list[dict[str, Any]]:
    if not warnings:
        return sources
    attached = []
    warning_text = ",".join(warnings)
    for source in sources:
        item = dict(source)
        if not item.get("warning") and item.get("type") in {"sql", "rag", "ml", "recommendation"}:
            # Keep warning explicit for frontend safety and audit introspection.
            item["contract_warning"] = warning_text
        attached.append(item)
    return attached
