from __future__ import annotations

import pytest

from app.ai.orchestrator.evidence_pipeline import AnswerPlan, EvidencePack, _validate_llm_answer, compose_answer, verify_evidence
from app.ai.orchestrator.response_verifier import ResponseVerifier
from app.ai.schemas.agent_schemas import AgentContext, AgentResult, AgentRoute
from app.ai.tools.recommendation_tools import RecommendationTools


def test_recommendation_with_sql_evidence_passes():
    tools = RecommendationTools(db=None, current_user=None)
    recs = tools.build_recommendations(
        query="Que recommandes-tu pour réduire les pertes ?",
        sql_results={
            "data": {
                "material_balance": [
                    {"batch_ref": "MANG-004", "product": "mango", "loss_pct": 14.2, "efficiency_pct": 81.0}
                ]
            },
            "sources": [{"type": "sql", "table": "process_steps,batches", "label": "canonical material balance"}],
        },
        rag_results=[],
        ml_results={},
        detected_entities={"batch_ref": "MANG-004", "product": ["mango"], "stage": [], "scope": "batch", "module": "post_harvest"},
    )
    assert recs
    assert any(any(ref.get("type") == "SQL" for ref in (rec.get("evidence_refs") or [])) for rec in recs)


def test_recommendation_with_rag_evidence_passes():
    tools = RecommendationTools(db=None, current_user=None)
    recs = tools.build_recommendations(
        query="Quelles bonnes pratiques recommandes-tu ?",
        sql_results={"data": {}, "sources": []},
        rag_results=[{"title": "Guide séchage", "chunk_id": "chunk-1", "document_id": "doc-1"}],
        ml_results={},
        detected_entities={"product": ["mango"], "stage": ["drying"], "scope": "global", "module": "recommendations"},
    )
    assert any(any(ref.get("type") == "RAG" for ref in (rec.get("evidence_refs") or [])) for rec in recs)


def test_recommendation_with_ml_evidence_passes():
    tools = RecommendationTools(db=None, current_user=None)
    recs = tools.build_recommendations(
        query="Actions pour lots à risque ?",
        sql_results={"data": {}, "sources": []},
        rag_results=[],
        ml_results={
            "risk_level": "HIGH",
            "confidence": 0.8,
            "affected_batch": "MANG-004",
            "affected_stage": "drying",
            "sources": [{"model": "loss_anomaly_detector", "result_id": "ml-123"}],
        },
        detected_entities={"batch_ref": "MANG-004", "scope": "batch", "module": "recommendations"},
    )
    assert any(any(ref.get("type") == "ML" for ref in (rec.get("evidence_refs") or [])) for rec in recs)


def test_rule_evidence_requires_triggering_fact():
    tools = RecommendationTools(db=None, current_user=None)
    recs = tools.build_recommendations(
        query="Que faire ?",
        sql_results={
            "data": {"material_balance": [{"batch_ref": "MANG-004", "product": "mango", "loss_pct": 13.0, "efficiency_pct": 82.0}]},
            "sources": [{"type": "sql", "table": "process_steps,batches", "label": "canonical material balance"}],
        },
        rag_results=[],
        ml_results={},
        detected_entities={"batch_ref": "MANG-004", "scope": "batch", "module": "recommendations"},
    )
    rule_refs = [
        ref
        for rec in recs
        for ref in (rec.get("evidence_refs") or [])
        if isinstance(ref, dict) and ref.get("type") == "RULE"
    ]
    assert rule_refs
    assert all(ref.get("triggered_by_source_id") for ref in rule_refs)


def test_recommendation_without_evidence_refs_is_downgraded():
    verifier = ResponseVerifier()
    result = verifier.verify(
        context=AgentContext(user_query="q", language="fr", route=AgentRoute.RECOMMENDATION_ONLY),
        answer="Recommandation: faire une action.",
        route=AgentRoute.RECOMMENDATION_ONLY,
        results=[
            AgentResult(
                agent_name="RecommendationAgent",
                route=AgentRoute.RECOMMENDATION_ONLY,
                answer_part="",
                data={"recommendations": [{"id": "x", "title": "A", "action": "B", "evidence_refs": []}]},
                sources=[],
                confidence=0.6,
                warnings=[],
                execution_time_ms=1,
            )
        ],
    )
    assert "RECOMMENDATION_WITHOUT_EVIDENCE" in result.warnings


def test_hybrid_full_missing_recommendation_evidence_returns_insufficiency_message():
    pack = EvidencePack(
        question="q",
        plan=AnswerPlan(
            module="global",
            intent="recommend_actions",
            answer_type="recommendation",
            required_sources=["SQL", "RECOMMENDATION"],
            required_fields=[],
            completeness_rules=[],
            output_blocks_needed=["answer_summary"],
            operation="",
        ),
        route=AgentRoute.HYBRID_FULL,
        sql={"tables_used": ["batches"], "rows": [{"batch_ref": "MANG-004"}], "metrics": {}, "calculations": {}, "payload": {"batch_summary": [{"batch_ref": "MANG-004", "loss_pct": 14.0}]}} ,
        rag={"chunks": [], "titles": [], "content_snippets": [], "scores": [], "topics": []},
        ml={},
        recommendations={"actions": [{"id": "x", "title": "A", "action": "B", "evidence_refs": []}], "insufficient_evidence": False},
        warnings=[],
        confidence=0.7,
        module_registry={},
    )
    verification = verify_evidence(pack)
    answer, _, _ = compose_answer(pack, verification)
    assert "Je ne peux pas générer de recommandations fiables" in answer


def test_lot_specific_recommendation_not_global_scope():
    tools = RecommendationTools(db=None, current_user=None)
    recs = tools.build_recommendations(
        query="Actions pour le lot MANG-004",
        sql_results={"data": {"material_balance": [{"batch_ref": "MANG-004", "product": "mango", "loss_pct": 13.0, "efficiency_pct": 80.0}]}, "sources": []},
        rag_results=[],
        ml_results={},
        detected_entities={"batch_ref": "MANG-004", "scope": "batch", "module": "recommendations"},
    )
    assert recs
    assert all(str(rec.get("scope")) != "GLOBAL_COOPERATIVE" for rec in recs)


def test_recommendation_uses_canonical_loss_value_for_same_lot():
    tools = RecommendationTools(db=None, current_user=None)
    recs = tools.build_recommendations(
        query="Et pour ce lot, quelles actions appliquer ?",
        sql_results={
            "data": {
                "material_balance": [{"batch_ref": "LOT-MILX-001", "product": "mil", "loss_pct": 74.1, "efficiency_pct": 25.9}],
                "batch_summary": [{"batch_ref": "LOT-MILX-001", "product": "mil", "loss_pct": 83.3, "efficiency_pct": 16.7}],
            },
            "sources": [],
        },
        rag_results=[],
        ml_results={},
        detected_entities={"batch_ref": "LOT-MILX-001", "scope": "batch", "module": "recommendations"},
    )
    sql_refs = [ref for rec in recs for ref in (rec.get("evidence_refs") or []) if isinstance(ref, dict) and ref.get("type") == "SQL"]
    assert sql_refs
    assert any(abs(float(ref.get("metric_value", 0.0) or 0.0) - 74.1) < 0.01 for ref in sql_refs)
    assert all(abs(float(ref.get("metric_value", 0.0) or 0.0) - 83.3) > 0.01 for ref in sql_refs)


def test_global_recommendation_declares_global_scope(monkeypatch):
    tools = RecommendationTools(db=None, current_user=None)
    monkeypatch.setattr(
        RecommendationTools,
        "_build_snapshot",
        lambda self: {"high_risk_lots": [{"batch_ref": "LOT-1", "product": "mango", "loss_pct": 16.0}], "batch_count": 3},
    )
    recs = tools.build_recommendations(
        query="Donne des recommandations globales pour toute la coopérative",
        sql_results={"data": {}, "sources": []},
        rag_results=[],
        ml_results={},
        detected_entities={"scope": "global", "module": "recommendations"},
    )
    assert any(str(rec.get("scope")) == "GLOBAL_COOPERATIVE" for rec in recs)


def test_llm_validator_rejects_extra_recommendations_beyond_locked_items():
    pack = EvidencePack(
        question="q",
        plan=AnswerPlan(module="global", intent="recommend", answer_type="recommendation", required_sources=[], required_fields=[], completeness_rules=[], output_blocks_needed=["answer_summary"], operation=""),
        route=AgentRoute.HYBRID_FULL,
        sql={"tables_used": [], "rows": [], "metrics": {}, "calculations": {}, "payload": {}},
        rag={"chunks": [], "titles": [], "content_snippets": [], "scores": [], "topics": []},
        ml={},
        recommendations={"actions": [{"id": "r1", "title": "A", "action": "X", "priority": "HIGH", "evidence_refs": [{"type": "SQL", "source_id": "sql:batches:LOT-1"}]}], "insufficient_evidence": False},
        warnings=[],
        confidence=0.7,
        module_registry={},
    )
    answer = "- rec1\n- rec2\n- rec3"
    issues = _validate_llm_answer(answer, pack, {})
    assert "LLM_ADDED_EXTRA_RECOMMENDATIONS" in issues
