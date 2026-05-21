from __future__ import annotations

from statistics import fmean

from app.ai.schemas.agent_schemas import AgentResult

EVIDENCE_HAS = "HAS_EVIDENCE"
EVIDENCE_NO_DATA = "PROVEN_NO_DATA"
EVIDENCE_PARTIAL = "PARTIAL_EVIDENCE"
EVIDENCE_TOOL_ERROR = "TOOL_ERROR"
EVIDENCE_UNSUPPORTED = "UNSUPPORTED"


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
    sql_evidence = _has_sql_evidence(agent_results)
    rag_evidence = _has_rag_evidence(agent_results)
    ml_evidence = _has_ml_evidence(agent_results)
    recommendation_evidence = _has_recommendation_evidence(agent_results)
    partial_recommendation_evidence = _has_partial_recommendation_evidence(agent_results)
    sql_status = _sql_evidence_status(agent_results)
    rag_status = _rag_evidence_status(agent_results)
    ml_status = _ml_evidence_status(agent_results)
    statuses = {sql_status, rag_status, ml_status}
    evidence_count = sum([sql_evidence, rag_evidence, ml_evidence, recommendation_evidence])

    bonus = 0.0
    if sql_evidence:
        bonus += 0.06
    if rag_evidence:
        bonus += 0.06
    if ml_evidence:
        bonus += 0.05
    if recommendation_evidence:
        bonus += 0.06

    penalty = 0.0
    if missing_expected_source:
        penalty += 0.22
    if weak_retrieval:
        penalty += 0.08
    if incomplete_sql:
        penalty += 0.12
    if contradiction:
        penalty += 0.20
    if weak_ml_confidence:
        penalty += 0.08
    if partial_recommendation_evidence:
        penalty += 0.10

    final_score = max(0.0, min(1.0, base + bonus - penalty))

    # Keep confidence low when evidence is missing.
    has_proven_no_data = EVIDENCE_NO_DATA in statuses
    has_tool_or_unsupported = any(status in {EVIDENCE_TOOL_ERROR, EVIDENCE_UNSUPPORTED} for status in statuses)
    if evidence_count == 0 and not has_proven_no_data:
        final_score = min(final_score, 0.4)
    if has_proven_no_data and not has_tool_or_unsupported:
        final_score = max(final_score, 0.68)
        final_score = min(final_score, 0.85)
    if has_tool_or_unsupported:
        final_score = min(final_score, 0.35)
    # Keep confidence constrained when critical contradictions remain.
    if contradiction:
        final_score = min(final_score, 0.55)
    if _has_unmapped_sql_operation(agent_results):
        final_score = min(final_score, 0.3)
    return max(0.0, min(1.0, final_score))


def _has_sql_evidence(agent_results: list[AgentResult]) -> bool:
    sql_result = next((item for item in agent_results if item.agent_name == "SQLAnalyticsAgent"), None)
    if not sql_result or not isinstance(sql_result.data, dict):
        return False
    trace = sql_result.data.get("sql_dispatch_trace") or {}
    status = str(trace.get("evidence_status") or "").strip().upper()
    if status in {EVIDENCE_HAS, EVIDENCE_NO_DATA, EVIDENCE_PARTIAL}:
        return True
    ignored_keys = {"detected_module", "query_text", "requested_batch_ref"}
    for key, value in sql_result.data.items():
        if key in ignored_keys:
            continue
        if isinstance(value, list) and value:
            return True
        if isinstance(value, dict) and value:
            return True
        if isinstance(value, (int, float)) and float(value) != 0.0:
            return True
    return False


def _has_rag_evidence(agent_results: list[AgentResult]) -> bool:
    rag_result = next((item for item in agent_results if item.agent_name == "RAGKnowledgeAgent"), None)
    if not rag_result:
        return False
    if isinstance(rag_result.data, dict):
        status = str(rag_result.data.get("evidence_status") or "").strip().upper()
        if status in {EVIDENCE_HAS, EVIDENCE_NO_DATA, EVIDENCE_PARTIAL}:
            return True
    if rag_result.sources:
        return True
    if not isinstance(rag_result.data, dict):
        return False
    chunks = rag_result.data.get("chunks") or []
    return isinstance(chunks, list) and any(str((chunk or {}).get("content") or "").strip() for chunk in chunks if isinstance(chunk, dict))


def _has_ml_evidence(agent_results: list[AgentResult]) -> bool:
    ml_result = next((item for item in agent_results if item.agent_name == "MLLossAgent"), None)
    if not ml_result or not isinstance(ml_result.data, dict):
        return False
    payload = ml_result.data
    status = str(payload.get("evidence_status") or "").strip().upper()
    if status in {EVIDENCE_HAS, EVIDENCE_NO_DATA, EVIDENCE_PARTIAL}:
        return True
    return any(payload.get(key) not in (None, "", []) for key in ("risk_level", "anomaly_detected", "predicted_loss_pct", "observed_loss_pct"))


def _has_recommendation_evidence(agent_results: list[AgentResult]) -> bool:
    rec_result = next((item for item in agent_results if item.agent_name == "RecommendationAgent"), None)
    if not rec_result or not isinstance(rec_result.data, dict):
        return False
    recommendations = rec_result.data.get("recommendations") or []
    return isinstance(recommendations, list) and any(_rec_has_refs(item) for item in recommendations if isinstance(item, dict))


def _has_partial_recommendation_evidence(agent_results: list[AgentResult]) -> bool:
    rec_result = next((item for item in agent_results if item.agent_name == "RecommendationAgent"), None)
    if not rec_result or not isinstance(rec_result.data, dict):
        return False
    recommendations = rec_result.data.get("recommendations") or []
    if not isinstance(recommendations, list) or not recommendations:
        return False
    has_with_refs = any(_rec_has_refs(item) for item in recommendations if isinstance(item, dict))
    has_without_refs = any(not _rec_has_refs(item) for item in recommendations if isinstance(item, dict))
    return has_with_refs and has_without_refs


def _rec_has_refs(item: dict) -> bool:
    refs = item.get("evidence_refs") if isinstance(item, dict) else None
    if not isinstance(refs, list) or not refs:
        return False
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        ref_type = str(ref.get("type") or "").upper()
        if ref_type == "RAG" and str(ref.get("quality_status") or "").upper() in {"WEAK", "REJECTED"}:
            continue
        if ref_type in {"SQL", "RAG", "ML", "RULE"} and str(ref.get("source_id") or "").strip():
            return True
    return False


def _has_unmapped_sql_operation(agent_results: list[AgentResult]) -> bool:
    sql_result = next((item for item in agent_results if item.agent_name == "SQLAnalyticsAgent"), None)
    if not sql_result:
        return False
    if "UNMAPPED_SQL_OPERATION" in (sql_result.warnings or []):
        return True
    if not isinstance(sql_result.data, dict):
        return False
    trace = sql_result.data.get("sql_dispatch_trace") or {}
    if trace and not str(trace.get("sql_operation") or "").strip():
        return True
    return False


def _sql_evidence_status(agent_results: list[AgentResult]) -> str:
    sql_result = next((item for item in agent_results if item.agent_name == "SQLAnalyticsAgent"), None)
    if not sql_result or not isinstance(sql_result.data, dict):
        return ""
    trace = sql_result.data.get("sql_dispatch_trace") or {}
    return str(trace.get("evidence_status") or "").strip().upper()


def _rag_evidence_status(agent_results: list[AgentResult]) -> str:
    rag_result = next((item for item in agent_results if item.agent_name == "RAGKnowledgeAgent"), None)
    if not rag_result or not isinstance(rag_result.data, dict):
        return ""
    return str(rag_result.data.get("evidence_status") or "").strip().upper()


def _ml_evidence_status(agent_results: list[AgentResult]) -> str:
    ml_result = next((item for item in agent_results if item.agent_name == "MLLossAgent"), None)
    if not ml_result or not isinstance(ml_result.data, dict):
        return ""
    return str(ml_result.data.get("evidence_status") or "").strip().upper()
