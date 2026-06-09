from __future__ import annotations

from types import SimpleNamespace

from app.ai.orchestrator.evidence_pipeline import AnswerPlan, EvidencePack, compose_answer, verify_evidence
from app.ai.schemas.agent_schemas import AgentRoute
from app.ai.tools import rag_tools


def test_strong_rag_evidence_is_marked_usable():
    items = [
        {
            "document_id": "doc-1",
            "chunk_id": "chunk-1",
            "title": "Guide séchage",
            "content": "Contrôler l'humidité finale avant emballage et limiter les manipulations au tri.",
            "metadata": {"chunk_type": "agronomic_knowledge", "topic": "best_practice", "stage": "drying", "product": "mango"},
            "source_type": "knowledge_chunks",
            "final_score": 0.82,
        }
    ]
    assessed = rag_tools._assess_rag_evidence_items(
        query="Quelles bonnes pratiques appliquer avant l'emballage ?",
        detected_entities={"scope": "global", "module": "rag_knowledge"},
        items=items,
    )
    assert assessed[0]["quality_status"] in {"STRONG", "PARTIAL"}
    assert assessed[0]["usable_for"] in {"best_practice", "recommendation_support", "documentation", "explanation"}


def test_weak_rag_evidence_is_rejected_or_weak():
    items = [
        {
            "document_id": "doc-1",
            "chunk_id": "chunk-1",
            "title": "Header",
            "content": "# Table of contents\\nsource: /tmp/file.md\\n",
            "metadata": {"chunk_type": "agronomic_knowledge"},
            "source_type": "knowledge_chunks",
            "final_score": 0.18,
        }
    ]
    assessed = rag_tools._assess_rag_evidence_items(
        query="Comment réduire les pertes pendant le séchage ?",
        detected_entities={"scope": "global", "module": "rag_knowledge"},
        items=items,
    )
    assert assessed[0]["quality_status"] in {"WEAK", "REJECTED"}


def test_raw_chunk_text_is_sanitized():
    raw = "# Guide\n```md\n|A|B|\n```\nsource: /tmp/doc.md\nAvant emballage, vérifier l'humidité."
    sanitized = rag_tools._sanitize_chunk_text(raw)
    assert "```" not in sanitized
    assert "source:" not in sanitized.lower()
    assert "Avant emballage" in sanitized


def test_mango_damaged_sorting_advice_uses_keyword_fallback(monkeypatch):
    class FakeRetriever:
        current_user = SimpleNamespace(cooperative_id="coop-1")

        def retrieve_with_diagnostics(self, *, query, filters, top_k):
            return {
                "results": [
                    {
                        "document_id": "op-doc",
                        "chunk_id": "op-chunk",
                        "title": "Operational stock",
                        "content": "Stock actuel de mangue",
                        "metadata": {"source_table": "stocks"},
                        "source_type": "stocks",
                        "final_score": 0.9,
                    }
                ],
                "timing_ms": {},
                "counts": {},
            }

    tool = object.__new__(rag_tools.RAGTools)
    tool.current_user = SimpleNamespace(cooperative_id="coop-1")
    tool.retriever = FakeRetriever()

    def fake_keyword_fallback(*, query, filters, top_k):
        return [
            {
                "document_id": "doc-a26",
                "chunk_id": "chunk-a26",
                "title": "Knowledge Mangue - tri mangues abîmées",
                "content": (
                    "Critères de tri mangues abîmées: zones molles étendues, moisissure visible, "
                    "fissures profondes, odeur fermentée. Isoler ces fruits protège le reste du lot."
                ),
                "metadata": {"chunk_type": "agronomic_knowledge", "topic": "tri mangues abîmées", "crop": "Mangue"},
                "source_type": "knowledge_chunks",
                "final_score": 0.9,
            }
        ]

    monkeypatch.setattr(tool, "_direct_keyword_fallback", fake_keyword_fallback)

    result = tool.search(
        query="Donne-moi les critères de tri pour les mangues abîmées.",
        detected_entities={"language": "fr"},
        top_k=3,
    )

    assert result["chunks"]
    assert result["chunks"][0]["quality_status"] in {"STRONG", "PARTIAL"}
    assert "mangues abîmées" in result["chunks"][0]["sanitized_summary"]
    assert "RAG_QUALITY_INSUFFICIENT" not in result["warnings"]


def test_keyword_fallback_terms_strip_accents_punctuation_and_fillers():
    assert rag_tools._keyword_fallback_terms("Donne-moi les critères de tri pour les mangues abîmées.") == [
        "criteres",
        "tri",
        "mangues",
        "abimees",
    ]


def test_merge_ranked_chunks_keeps_exact_keyword_match_first():
    exact = {"chunk_id": "a26", "title": "Knowledge Mangue - tri mangues abîmées", "final_score": 1.0}
    broad = {"chunk_id": "generic", "title": "Knowledge Mangue - tri mangue", "final_score": 0.72}

    merged = rag_tools._merge_ranked_chunks([exact], [broad], top_k=2)

    assert [item["chunk_id"] for item in merged] == ["a26", "generic"]


def test_rag_only_weak_evidence_returns_insufficient_message():
    pack = EvidencePack(
        question="q",
        plan=AnswerPlan(
            module="rag_knowledge",
            intent="explain_best_practices",
            answer_type="explanation",
            required_sources=["RAG"],
            required_fields=[],
            completeness_rules=[],
            output_blocks_needed=["answer_summary"],
            operation="",
        ),
        route=AgentRoute.RAG_ONLY,
        sql={"tables_used": [], "rows": [], "metrics": {}, "calculations": {}, "payload": {}},
        rag={"chunks": [], "titles": [], "content_snippets": [], "scores": [], "topics": []},
        ml={},
        recommendations={"actions": [], "insufficient_evidence": False},
        warnings=[],
        confidence=0.4,
        module_registry={},
    )
    verification = verify_evidence(pack)
    answer, _, _ = compose_answer(pack, verification)
    assert answer.strip() == "Je n’ai pas assez de contexte documentaire fiable pour répondre précisément à cette question."


def test_hybrid_sql_rag_missing_rag_degrades_with_sql_required_contract():
    pack = EvidencePack(
        question="Pourquoi ce lot a une mauvaise efficacité ?",
        plan=AnswerPlan(
            module="post_harvest",
            intent="analyze_with_explanation",
            answer_type="hybrid_analysis",
            required_sources=["SQL", "RAG"],
            required_fields=[],
            completeness_rules=[],
            output_blocks_needed=["answer_summary"],
            operation="",
        ),
        route=AgentRoute.HYBRID_SQL_RAG,
        sql={"tables_used": ["batches"], "rows": [{"batch_ref": "MANG-004", "loss_pct": 14.0}], "metrics": {}, "calculations": {}, "payload": {"batch_summary": [{"batch_ref": "MANG-004", "loss_pct": 14.0, "efficiency_pct": 81.0}]}} ,
        rag={"chunks": [], "titles": [], "content_snippets": [], "scores": [], "topics": []},
        ml={},
        recommendations={"actions": [], "insufficient_evidence": False},
        warnings=[],
        confidence=0.7,
        module_registry={},
    )
    verification = verify_evidence(pack)
    answer, _, metadata = compose_answer(pack, verification)
    assert "RAG" in metadata["missing_evidence_types"]
    assert "1. Données mesurées" in answer
    assert "2. Analyse" in answer
    assert "3. Limites" in answer
    assert "Le contexte documentaire est limité pour cette question." in answer


def test_operational_query_rejects_operational_like_rag_chunk():
    items = [
        {
            "document_id": "doc-1",
            "chunk_id": "chunk-1",
            "title": "Stock dump",
            "content": "Stock mango 1200 kg",
            "metadata": {"chunk_type": "stock"},
            "source_type": "stocks",
            "final_score": 0.9,
        }
    ]
    assessed = rag_tools._assess_rag_evidence_items(
        query="Est-ce que le stock actuel est suffisant ?",
        detected_entities={"module": "stocks", "scope": "global"},
        items=items,
    )
    assert assessed[0]["quality_status"] == "REJECTED"


def test_recommendation_support_cannot_use_weak_or_rejected_rag_refs():
    pack = EvidencePack(
        question="Que recommandes-tu pour réduire les pertes ?",
        plan=AnswerPlan(
            module="recommendations",
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
        recommendations={
            "actions": [
                {
                    "id": "r1",
                    "title": "Action",
                    "action": "Faire X",
                    "priority": "HIGH",
                    "evidence_refs": [
                        {"type": "RAG", "source_id": "doc-weak", "label": "weak", "short_fact": "generic", "quality_status": "WEAK"}
                    ],
                }
            ],
            "insufficient_evidence": False,
        },
        warnings=[],
        confidence=0.7,
        module_registry={},
    )
    verification = verify_evidence(pack)
    answer, _, _ = compose_answer(pack, verification)
    assert "Je ne peux pas générer de recommandations fiables" in answer


def test_hybrid_full_recommendation_answer_uses_deterministic_sections():
    pack = EvidencePack(
        question="Que recommandes-tu pour réduire les pertes ?",
        plan=AnswerPlan(
            module="recommendations",
            intent="recommend_actions",
            answer_type="recommendation",
            required_sources=["SQL", "RECOMMENDATION"],
            required_fields=[],
            completeness_rules=[],
            output_blocks_needed=["answer_summary"],
            operation="",
        ),
        route=AgentRoute.HYBRID_FULL,
        sql={
            "tables_used": ["batches", "process_steps"],
            "rows": [{"batch_ref": "LOT-MILX-001", "loss_pct": 74.1, "efficiency_pct": 25.9}],
            "metrics": {},
            "calculations": {},
            "payload": {
                "material_balance": [
                    {"batch_ref": "LOT-MILX-001", "input_qty": 27.0, "output_qty": 7.0, "loss_pct": 74.1, "efficiency_pct": 25.9}
                ]
            },
        },
        rag={"chunks": [], "titles": [], "content_snippets": [], "scores": [], "topics": []},
        ml={},
        recommendations={
            "actions": [
                {
                    "id": "rec-1",
                    "title": "Isoler le lot critique",
                    "action": "Isoler le lot LOT-MILX-001 et renforcer le contrôle au tri.",
                    "priority": "HIGH",
                    "reason": "Perte canonique élevée.",
                    "evidence_refs": [
                        {"type": "SQL", "source_id": "material_balance:LOT-MILX-001", "label": "Bilan matière", "short_fact": "Perte 74.1%"}
                    ],
                }
            ],
            "insufficient_evidence": False,
        },
        warnings=["MISSING_RAG_SOURCE", "WEAK_RETRIEVAL"],
        confidence=0.8,
        module_registry={},
    )
    verification = verify_evidence(pack)
    answer, _, _ = compose_answer(pack, verification)
    assert "1. Données mesurées" in answer
    assert "2. Signal ML" in answer
    assert "3. Recommandations validées" in answer
    assert "4. Limites" in answer


def test_ml_no_data_does_not_render_unknown_signal_card():
    pack = EvidencePack(
        question="Combien de signaux ML HIGH sont enregistrés ?",
        plan=AnswerPlan(
            module="ml_logs",
            intent="risk_ml",
            answer_type="explanation",
            required_sources=["ML"],
            required_fields=[],
            completeness_rules=[],
            output_blocks_needed=["answer_summary", "sources", "warnings"],
            operation="ml_high_signal_count",
            answer_contract={"intent_family": "risk_ml", "route": "ML_ONLY", "required_layers": {"ml": True}},
        ),
        route=AgentRoute.ML_ONLY,
        sql={"tables_used": [], "rows": [], "metrics": {}, "calculations": {}, "payload": {}},
        rag={"chunks": [], "titles": [], "content_snippets": [], "scores": [], "topics": []},
        ml={
            "anomaly_detected": False,
            "risk_level": "UNKNOWN",
            "observed_loss_pct": None,
            "expected_loss_pct": None,
            "deviation": None,
            "confidence": 0.72,
            "warnings": ["NO_ML_DATA"],
            "evidence_status": "PROVEN_NO_DATA",
            "sources": [{"type": "ml", "record_count": 0, "evidence_status": "PROVEN_NO_DATA"}],
        },
        recommendations={"actions": [], "insufficient_evidence": False},
        warnings=[],
        confidence=0.72,
        module_registry={},
    )

    verification = verify_evidence(pack)
    answer, blocks, _metadata = compose_answer(pack, verification)
    signal_cards = [
        item
        for block in blocks
        if block.get("type") == "kpi_cards"
        for item in (block.get("items") or [])
        if item.get("title") == "Signal ML"
    ]

    assert "UNKNOWN" not in answer
    assert signal_cards == []


def test_ml_high_signal_count_does_not_render_unknown_signal_card():
    pack = EvidencePack(
        question="Combien de signaux ML HIGH sont enregistrés ?",
        plan=AnswerPlan(
            module="ml_logs",
            intent="risk_ml",
            answer_type="risk_list",
            required_sources=["ML"],
            required_fields=["rows"],
            completeness_rules=[],
            output_blocks_needed=["answer_summary", "sources", "warnings"],
            operation="ml_high_signal_count",
            required_answer_fields=["high_signal_count"],
            allowed_sources=["ml"],
            answer_contract={"intent_family": "risk_ml", "route": "ML_ONLY", "required_layers": {"ml": True}},
        ),
        route=AgentRoute.ML_ONLY,
        sql={"tables_used": [], "rows": [], "metrics": {}, "calculations": {}, "payload": {}},
        rag={"chunks": [], "titles": [], "content_snippets": [], "scores": [], "topics": []},
        ml={
            "ml_high_signal_count": [{"high_signal_count": 1, "days": 60}],
            "evidence_status": "HAS_EVIDENCE",
        },
        recommendations={"actions": [], "insufficient_evidence": False},
        warnings=[],
        confidence=0.84,
        module_registry={},
    )

    verification = verify_evidence(pack)
    answer, blocks, _metadata = compose_answer(pack, verification)
    signal_cards = [
        item
        for block in blocks
        if block.get("type") == "kpi_cards"
        for item in (block.get("items") or [])
        if item.get("title") == "Signal ML"
    ]

    assert "UNKNOWN" not in answer
    assert "Signaux ML HIGH" in answer
    assert "Comptage agrégé" in answer
    assert signal_cards == []


def test_rag_checklist_answer_sanitizes_source_like_markers():
    pack = EvidencePack(
        question="Donne une checklist courte avant l’emballage des mangues.",
        plan=AnswerPlan(
            module="rag_knowledge",
            intent="best_practices",
            answer_type="explanation",
            required_sources=["RAG"],
            required_fields=[],
            completeness_rules=[],
            output_blocks_needed=["answer_summary"],
            operation="",
            answer_contract={"intent_family": "BEST_PRACTICES", "route": "RAG_ONLY"},
        ),
        route=AgentRoute.RAG_ONLY,
        sql={"tables_used": [], "rows": [], "metrics": {}, "calculations": {}, "payload": {}},
        rag={
            "chunks": [{"title": "Guide", "content": "Agronomic knowledge reference\nSource: REF-KNOW-1\nTopic: emballage\nChecklist: sécher, trier, emballer proprement."}],
            "titles": ["Guide emballage"],
            "content_snippets": ["Agronomic knowledge reference\nSource: REF-KNOW-1\nTopic: emballage\nChecklist: sécher, trier, emballer proprement."],
            "scores": [0.8],
            "topics": ["best_practice"],
        },
        ml={},
        recommendations={"actions": [], "insufficient_evidence": False},
        warnings=[],
        confidence=0.9,
        module_registry={},
    )
    verification = verify_evidence(pack)
    answer, blocks, metadata = compose_answer(pack, verification)
    lowered = answer.lower()
    assert "agronomic knowledge reference" not in lowered
    assert "source:" not in lowered
    assert "topic:" not in lowered
    assert "ref-know" not in lowered
    assert "checklist pratique" in lowered or "je n’ai pas assez de contexte documentaire fiable" in lowered
    assert any(block.get("type") == "sources" for block in blocks)
    assert "RAG" in metadata.get("found_evidence_types", [])
