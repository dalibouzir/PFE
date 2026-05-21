from __future__ import annotations

from app.ai.orchestrator.response_verifier import ResponseVerifier
from app.ai.orchestrator.evidence_pipeline import AnswerPlan, EvidencePack, collapse_user_warning_items, compose_answer, verify_evidence
from app.ai.schemas.agent_schemas import AgentContext, AgentResult, AgentRoute


def _pack(
    *,
    route: AgentRoute,
    question: str,
    sql_payload: dict,
    warnings: list[str],
    required_sources: list[str],
    rec_actions: list[dict] | None = None,
) -> EvidencePack:
    return EvidencePack(
        question=question,
        plan=AnswerPlan(
            module="global",
            intent="test",
            answer_type="list",
            required_sources=required_sources,
            required_fields=[],
            completeness_rules=[],
            output_blocks_needed=["answer_summary"],
            operation="",
        ),
        route=route,
        sql={
            "tables_used": ["stocks"],
            "rows": [{"product": "Mil"}] if sql_payload else [],
            "metrics": {},
            "calculations": {},
            "payload": sql_payload,
        },
        rag={"chunks": [], "titles": [], "content_snippets": [], "scores": [], "topics": []},
        ml={},
        recommendations={"actions": rec_actions or [], "insufficient_evidence": False},
        warnings=warnings,
        confidence=0.8,
        module_registry={},
    )


def test_business_warning_does_not_render_technical_warning_text():
    pack = _pack(
        route=AgentRoute.SQL_ONLY,
        question="Quel est le stock actuel ?",
        sql_payload={
            "current_stock": [
                {
                    "product": "Mil",
                    "available_stock_kg": 98.0,
                    "grades": {"A": 0.0, "B": 43.0, "C": 55.0},
                }
            ]
        },
        warnings=["PRODUCT_FILTER_IGNORED"],
        required_sources=["SQL"],
    )
    verification = verify_evidence(pack)
    answer, _, _ = compose_answer(pack, verification)
    assert "avertissement technique" not in answer.lower()


def test_technical_warning_still_renders_technical_warning_text():
    pack = _pack(
        route=AgentRoute.SQL_ONLY,
        question="Quel est le stock actuel ?",
        sql_payload={"current_stock": [{"product": "Mil", "available_stock_kg": 98.0}]},
        warnings=["AGENT_ERROR_SQLANALYTICSAGENT"],
        required_sources=["SQL"],
    )
    verification = verify_evidence(pack)
    answer, _, _ = compose_answer(pack, verification)
    assert "avertissement technique" in answer.lower()


def test_sql_only_with_rows_does_not_fallback_missing_data():
    pack = _pack(
        route=AgentRoute.SQL_ONLY,
        question="Quels lots post-récolte sont disponibles actuellement ?",
        sql_payload={
            "available_postharvest_lots": [
                {
                    "batch_ref": "LOT-MILX-001",
                    "product": "Mil",
                    "initial_qty": 30.0,
                    "current_qty": 5.0,
                }
            ]
        },
        warnings=[],
        required_sources=["SQL"],
    )
    verification = verify_evidence(pack)
    answer, _, _ = compose_answer(pack, verification)
    assert "Donnée non disponible" not in answer
    assert "LOT-MILX-001" in answer


def test_hybrid_sql_rag_with_missing_rag_is_not_technical_when_sql_exists():
    pack = _pack(
        route=AgentRoute.HYBRID_SQL_RAG,
        question="Pourquoi ce lot a une mauvaise efficacité ?",
        sql_payload={
            "material_balance": [
                {
                    "batch_ref": "LOT-MILX-001",
                    "input_qty": 27.0,
                    "output_qty": 7.0,
                    "loss_pct": 74.0,
                    "efficiency_pct": 26.0,
                }
            ]
        },
        warnings=["MISSING_RAG_SOURCE"],
        required_sources=["SQL", "RAG"],
    )
    verification = verify_evidence(pack)
    answer, _, metadata = compose_answer(pack, verification)
    assert "avertissement technique" not in answer.lower()
    assert "documentaire" in answer.lower() or "sql" in answer.lower()
    assert metadata.get("warning_categories", {}).get("MISSING_RAG_SOURCE") == "EVIDENCE_WARNING"


def test_warning_deduplication_in_blocks():
    pack = _pack(
        route=AgentRoute.SQL_ONLY,
        question="Quel est le stock actuel ?",
        sql_payload={"current_stock": [{"product": "Mil", "available_stock_kg": 98.0}]},
        warnings=["PRODUCT_FILTER_IGNORED", "PRODUCT_FILTER_IGNORED"],
        required_sources=["SQL"],
    )
    verification = verify_evidence(pack)
    _, blocks, _ = compose_answer(pack, verification)
    warning_block = next((b for b in blocks if b.get("type") == "warnings"), {"items": []})
    items = warning_block.get("items") or []
    assert len(items) == len(set(items))


def test_sql_success_does_not_emit_missing_data_signalled_warning():
    verifier = ResponseVerifier()
    context = AgentContext(user_query="stock", route=AgentRoute.SQL_ONLY, language="fr")
    sql_result = AgentResult(
        agent_name="SQLAnalyticsAgent",
        route=AgentRoute.SQL_ONLY,
        answer_part="Réponse SQL",
        data={"sql_dispatch_trace": {"sql_operation": "get_current_stock", "row_count": 4}},
        sources=[{"type": "sql", "table": "stocks"}],
        confidence=0.9,
        warnings=[],
    )
    result = verifier.verify(
        context=context,
        answer="1. Réponse directe\nAucune explication détaillée disponible.",
        route=AgentRoute.SQL_ONLY,
        results=[sql_result],
    )
    assert "MISSING_DATA_SIGNALLED" not in result.warnings


def test_sql_empty_result_keeps_missing_data_warning():
    verifier = ResponseVerifier()
    context = AgentContext(user_query="stock", route=AgentRoute.SQL_ONLY, language="fr")
    sql_result = AgentResult(
        agent_name="SQLAnalyticsAgent",
        route=AgentRoute.SQL_ONLY,
        answer_part="Donnée non disponible pour cette requête précise.",
        data={"sql_dispatch_trace": {"sql_operation": "get_current_stock", "row_count": 0}},
        sources=[{"type": "sql", "table": "stocks"}],
        confidence=0.5,
        warnings=["NO_SQL_DATA"],
    )
    result = verifier.verify(
        context=context,
        answer="Donnée non disponible pour cette requête précise.",
        route=AgentRoute.SQL_ONLY,
        results=[sql_result],
    )
    assert "MISSING_DATA_SIGNALLED" in result.warnings


def test_hybrid_sql_rag_keeps_rag_warning_without_sql_missing_data_warning():
    verifier = ResponseVerifier()
    context = AgentContext(user_query="pourquoi lot", route=AgentRoute.HYBRID_SQL_RAG, language="fr")
    sql_result = AgentResult(
        agent_name="SQLAnalyticsAgent",
        route=AgentRoute.HYBRID_SQL_RAG,
        answer_part="Lot LOT-MILX-001: perte 74.1%",
        data={"sql_dispatch_trace": {"sql_operation": "get_canonical_material_balance", "row_count": 1}},
        sources=[{"type": "sql", "table": "process_steps"}],
        confidence=0.9,
        warnings=[],
    )
    rag_result = AgentResult(
        agent_name="RAGKnowledgeAgent",
        route=AgentRoute.HYBRID_SQL_RAG,
        answer_part="",
        data={"weak_retrieval": True, "chunks": []},
        sources=[],
        confidence=0.2,
        warnings=[],
    )
    result = verifier.verify(
        context=context,
        answer="Lot LOT-MILX-001 perte 74.1%. Le contexte documentaire est insuffisant pour répondre.",
        route=AgentRoute.HYBRID_SQL_RAG,
        results=[sql_result, rag_result],
    )
    assert "MISSING_DATA_SIGNALLED" not in result.warnings
    assert "MISSING_RAG_SOURCE" in result.warnings


def test_rag_warning_codes_are_collapsed_for_user_facing_output():
    warnings = collapse_user_warning_items(
        [
            "MISSING_RAG_SOURCE",
            "WEAK_RETRIEVAL",
            "RAG_QUALITY_INSUFFICIENT",
            "RAG_EVIDENCE_REJECTED",
        ]
    )
    assert warnings == ["Le contexte documentaire est limité pour cette question."]


def test_partial_warning_codes_are_collapsed_for_user_facing_output():
    warnings = collapse_user_warning_items(
        [
            "MISSING_EXPECTED_ROUTE_EVIDENCE",
            "MISSING_RECOMMENDATION_EVIDENCE",
            "SOURCE_DATA_EMPTY",
        ]
    )
    assert warnings == ["Certaines preuves attendues sont partielles ou indisponibles."]


def test_collapsed_user_warnings_keep_detailed_codes_in_metadata():
    pack = _pack(
        route=AgentRoute.HYBRID_SQL_RAG,
        question="Pourquoi ce lot a une mauvaise efficacité ?",
        sql_payload={"material_balance": [{"batch_ref": "LOT-MILX-001", "loss_pct": 74.1, "efficiency_pct": 25.9}]},
        warnings=["MISSING_RAG_SOURCE", "WEAK_RETRIEVAL", "RAG_QUALITY_INSUFFICIENT"],
        required_sources=["SQL", "RAG"],
    )
    verification = verify_evidence(pack)
    _, blocks, metadata = compose_answer(pack, verification)
    warning_block = next((b for b in blocks if b.get("type") == "warnings"), {"items": []})
    assert warning_block.get("items") == ["Le contexte documentaire est limité pour cette question."]
    categories = metadata.get("warning_categories", {})
    assert "MISSING_RAG_SOURCE" in categories
    assert "WEAK_RETRIEVAL" in categories


def test_stock_top_product_question_uses_top_product_summary_shape():
    pack = _pack(
        route=AgentRoute.SQL_ONLY,
        question="Quel produit a le plus de stock disponible actuellement ?",
        sql_payload={
            "operation": "get_current_stock",
            "row_count": 2,
            "current_stock": [
                {"product": "Mil", "available_stock_kg": 98.0, "restant_kg": 98.0, "grades": {"A": 0.0, "B": 43.0, "C": 55.0}},
                {"product": "Mangue", "available_stock_kg": 30.0, "restant_kg": 30.0, "grades": {"A": 10.0, "B": 15.0, "C": 5.0}},
            ],
        },
        warnings=[],
        required_sources=["SQL"],
    )
    pack.plan.answer_contract = {"intent_family": "STOCK_CURRENT"}
    verification = verify_evidence(pack)
    answer, _, _ = compose_answer(pack, verification)
    assert "produit avec le plus de stock disponible" in answer.lower()


def test_sql_only_complete_success_hides_non_blocking_product_filter_warning():
    pack = _pack(
        route=AgentRoute.SQL_ONLY,
        question="Donne-moi le stock restant par produit.",
        sql_payload={
            "operation": "get_current_stock",
            "row_count": 1,
            "current_stock": [{"product": "Mil", "available_stock_kg": 98.0, "restant_kg": 98.0, "grades": {"A": 0.0, "B": 43.0, "C": 55.0}}],
        },
        warnings=["PRODUCT_FILTER_IGNORED"],
        required_sources=["SQL"],
    )
    verification = verify_evidence(pack)
    _, blocks, _ = compose_answer(pack, verification)
    warning_block = next((b for b in blocks if b.get("type") == "warnings"), None)
    assert warning_block is None


def test_recommendation_requested_count_explains_reliable_subset_only():
    pack = _pack(
        route=AgentRoute.HYBRID_FULL,
        question="Donne-moi 3 actions concrètes pour réduire les pertes de LOT-MILX-001.",
        sql_payload={
            "operation": "get_canonical_material_balance",
            "row_count": 1,
            "material_balance": [
                {"batch_ref": "LOT-MILX-001", "input_qty": 27.0, "output_qty": 7.0, "loss_pct": 74.1, "efficiency_pct": 25.9}
            ],
        },
        warnings=["MISSING_RAG_SOURCE"],
        required_sources=["SQL", "RECOMMENDATION"],
        rec_actions=[
            {
                "id": "r1",
                "title": "Réduire humidité au séchage",
                "action": "Réduire humidité au séchage",
                "priority": "HIGH",
                "related_batch": "LOT-MILX-001",
                "evidence_refs": [{"type": "SQL", "source_id": "sql:material_balance:LOT-MILX-001"}],
            }
        ],
    )
    verification = verify_evidence(pack)
    answer, _, _ = compose_answer(pack, verification)
    assert "Je peux proposer 1 action fiable" in answer


def test_hybrid_full_summary_not_contradictory_with_targeted_recommendation():
    pack = _pack(
        route=AgentRoute.HYBRID_FULL,
        question="Que recommandes-tu pour ce lot ?",
        sql_payload={"operation": "get_canonical_material_balance", "row_count": 0},
        warnings=[],
        required_sources=["SQL", "RECOMMENDATION"],
        rec_actions=[
            {
                "id": "r1",
                "title": "Contrôle tri",
                "action": "Renforcer le contrôle tri",
                "priority": "MEDIUM",
                "related_batch": "LOT-MILX-001",
                "evidence_refs": [{"type": "SQL", "source_id": "sql:material_balance:LOT-MILX-001"}],
            }
        ],
    )
    verification = verify_evidence(pack)
    answer, _, _ = compose_answer(pack, verification)
    assert "ne permettent pas d’identifier un lot prioritaire" not in answer
