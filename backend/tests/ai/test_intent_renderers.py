from __future__ import annotations

from app.ai.orchestrator.evidence_pipeline import AnswerPlan, EvidencePack, compose_answer, verify_evidence
from app.ai.schemas.agent_schemas import AgentRoute


def _pack(route: AgentRoute, question: str, sql_payload: dict, *, intent_family: str, rag_chunks: list[dict] | None = None, recs: list[dict] | None = None) -> EvidencePack:
    operation = str(sql_payload.get("operation") or "")
    payload = dict(sql_payload)
    if operation and operation not in payload:
        if operation == "get_current_stock":
            payload[operation] = payload.get("current_stock") or []
        elif operation == "get_available_postharvest_lots":
            payload[operation] = payload.get("available_postharvest_lots") or []
        elif operation in {"get_canonical_material_balance", "get_canonical_material_balance_for_lots"}:
            payload[operation] = payload.get("batch_summary") or payload.get("material_balance") or []
        elif operation == "get_stage_loss_analysis":
            payload[operation] = payload.get("stage_loss_analysis") or []
        else:
            payload[operation] = []
    return EvidencePack(
        question=question,
        plan=AnswerPlan(
            module="global",
            intent="test",
            answer_type="list",
            required_sources=["SQL"] if route != AgentRoute.RAG_ONLY else ["RAG"],
            required_fields=[],
            completeness_rules=[],
            output_blocks_needed=["answer_summary"],
            operation=operation,
            answer_contract={"route": route.value, "intent_family": intent_family},
        ),
        route=route,
        sql={"tables_used": ["batches"], "rows": [{"id": 1}] if payload else [], "metrics": {}, "calculations": {}, "payload": payload},
        rag={"chunks": rag_chunks or [], "titles": [c.get("title", "") for c in (rag_chunks or [])], "content_snippets": [c.get("content", "") for c in (rag_chunks or [])], "scores": [0.8] * len(rag_chunks or []), "topics": []},
        ml={},
        recommendations={"actions": recs or [], "insufficient_evidence": False},
        warnings=[],
        confidence=0.9,
        module_registry={},
    )


def test_stock_current_top_product_renderer():
    pack = _pack(
        AgentRoute.SQL_ONLY,
        "Quel produit a le plus de stock disponible actuellement ?",
        {"operation": "get_current_stock", "row_count": 2, "current_stock": [{"product": "Mil", "available_stock_kg": 98.0, "restant_kg": 98.0, "grades": {"A": 0.0, "B": 40.0, "C": 58.0}}, {"product": "Mangue", "available_stock_kg": 43.0, "restant_kg": 43.0, "grades": {"A": 43.0, "B": 0.0, "C": 0.0}}]},
        intent_family="STOCK_CURRENT",
    )
    answer, blocks, _ = compose_answer(pack, verify_evidence(pack))
    assert "produit avec le plus de stock disponible" in answer.lower()
    table = next(b for b in blocks if b.get("type") == "table")
    assert table.get("title") == "Stock actuel par produit"
    assert any(b.get("type") == "kpi_cards" for b in blocks)
    assert any(b.get("type") == "chart" for b in blocks)


def test_loss_ranking_renderer_orders_rows():
    pack = _pack(
        AgentRoute.SQL_ONLY,
        "Quels lots ont le pire rendement ?",
        {"operation": "get_canonical_material_balance", "row_count": 2, "batch_summary": [{"batch_ref": "LOT-A", "product": "Mil", "input_qty": 20, "output_qty": 5, "gap_qty": 15, "loss_pct": 75.0, "efficiency_pct": 25.0}, {"batch_ref": "LOT-B", "product": "Mangue", "input_qty": 30, "output_qty": 24, "gap_qty": 6, "loss_pct": 20.0, "efficiency_pct": 80.0}]},
        intent_family="LOSS_RANKING",
    )
    _, blocks, _ = compose_answer(pack, verify_evidence(pack))
    table = next(b for b in blocks if b.get("type") == "table")
    assert table.get("title") == "Classement des lots par pertes"
    assert table["rows"][0][0] == "LOT-A"


def test_input_output_gap_renderer_orders_by_gap_qty():
    pack = _pack(
        AgentRoute.SQL_ONLY,
        "Quel lot a perdu le plus de quantité en kg ?",
        {"operation": "get_canonical_material_balance", "row_count": 2, "batch_summary": [{"batch_ref": "LOT-A", "product": "Mil", "input_qty": 30, "output_qty": 20, "gap_qty": 10, "loss_pct": 33.3, "efficiency_pct": 66.7}, {"batch_ref": "LOT-B", "product": "Mangue", "input_qty": 30, "output_qty": 5, "gap_qty": 25, "loss_pct": 83.3, "efficiency_pct": 16.7}]},
        intent_family="INPUT_OUTPUT_GAP",
    )
    answer, blocks, _ = compose_answer(pack, verify_evidence(pack))
    assert "classement établi par écart de quantité (kg)" in answer.lower()
    table = next(b for b in blocks if b.get("type") == "table")
    assert table["rows"][0][0] == "LOT-B"


def test_lot_comparison_renderer_side_by_side():
    pack = _pack(
        AgentRoute.SQL_ONLY,
        "Compare LOT-A et LOT-B en perte et efficacité",
        {"operation": "get_canonical_material_balance_for_lots", "row_count": 2, "batch_summary": [{"batch_ref": "LOT-A", "product": "Mil", "input_qty": 20, "output_qty": 5, "gap_qty": 15, "loss_pct": 75.0, "efficiency_pct": 25.0}, {"batch_ref": "LOT-B", "product": "Mangue", "input_qty": 30, "output_qty": 24, "gap_qty": 6, "loss_pct": 20.0, "efficiency_pct": 80.0}]},
        intent_family="LOT_COMPARISON",
    )
    answer, blocks, _ = compose_answer(pack, verify_evidence(pack))
    assert "comparaison côte à côte" in answer.lower()
    table = next(b for b in blocks if b.get("type") in {"table", "comparison_table"})
    assert table.get("title") == "Comparaison des lots"


def test_recommendation_renderer_exposes_evidence_refs():
    recs = [
        {
            "id": "rec-1",
            "title": "Renforcer tri",
            "action": "Renforcer le tri",
            "priority": "HIGH",
            "reason": "Perte élevée",
            "related_batch": "LOT-A",
            "evidence_refs": [{"type": "SQL", "source_id": "material_balance:LOT-A", "label": "Bilan matière", "short_fact": "Perte 75%"}],
        }
    ]
    pack = _pack(
        AgentRoute.HYBRID_FULL,
        "Et pour ce lot, quelles actions appliquer ?",
        {"operation": "get_canonical_material_balance", "row_count": 1, "material_balance": [{"batch_ref": "LOT-A", "input_qty": 20, "output_qty": 5, "loss_pct": 75.0}]},
        intent_family="FOLLOW_UP",
        recs=recs,
    )
    answer, blocks, metadata = compose_answer(pack, verify_evidence(pack))
    assert "preuves:" in answer.lower()
    rec_block = next(b for b in blocks if b.get("type") == "recommendations")
    assert rec_block.get("evidence_refs_total", 0) > 0
    assert metadata.get("recommendation_refs_count", 0) > 0
    assert any(b.get("type") in {"limits_block", "warnings"} for b in blocks) or "4. Limites" in answer


def test_best_practices_weak_rag_returns_clean_insufficiency():
    pack = _pack(
        AgentRoute.RAG_ONLY,
        "Bonnes pratiques emballage",
        {},
        intent_family="BEST_PRACTICES",
        rag_chunks=[],
    )
    answer, _, _ = compose_answer(pack, verify_evidence(pack))
    assert answer == "Je n’ai pas assez de contexte documentaire fiable pour répondre précisément à cette question."
