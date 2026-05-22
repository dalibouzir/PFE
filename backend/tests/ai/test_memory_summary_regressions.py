from __future__ import annotations

from app.ai.orchestrator.evidence_pipeline import AnswerPlan, EvidencePack, compose_answer, verify_evidence
from app.ai.schemas.agent_schemas import AgentRoute


def _pack_for_sql_summary(*, question: str, sql_payload: dict, sql_status: str, rows: list[dict] | None = None) -> EvidencePack:
    return EvidencePack(
        question=question,
        plan=AnswerPlan(
            module="global",
            intent="test",
            answer_type="list",
            required_sources=["SQL"],
            required_fields=[],
            completeness_rules=[],
            output_blocks_needed=["answer_summary"],
            operation="generic",
        ),
        route=AgentRoute.SQL_ONLY,
        sql={
            "tables_used": ["inputs", "stocks"],
            "rows": rows or [],
            "metrics": {},
            "calculations": {},
            "payload": sql_payload,
            "evidence_status": sql_status,
        },
        rag={"chunks": [], "titles": [], "content_snippets": [], "scores": [], "topics": [], "evidence_status": ""},
        ml={"evidence_status": ""},
        recommendations={"actions": [], "insufficient_evidence": False},
        warnings=[],
        confidence=0.8,
        module_registry={},
    )


def test_top_farmer_summary_uses_evidence_row():
    pack = _pack_for_sql_summary(
        question="Quel producteur a livré la plus grande quantité ?",
        sql_status="HAS_EVIDENCE",
        rows=[{"member_name": "Awa Diop", "member_code": "M-001", "total_quantity_kg": 135.0}],
        sql_payload={
            "sql_dispatch_trace": {"sql_operation": "get_top_farmers", "row_count": 1},
            "top_farmers": [{"member_name": "Awa Diop", "member_code": "M-001", "total_quantity_kg": 135.0}],
        },
    )
    verification = verify_evidence(pack)
    answer, _, _ = compose_answer(pack, verification)
    assert "Awa Diop est le producteur ayant livré la plus grande quantité, avec 135.0 kg." in answer


def test_low_stock_no_data_summary_is_precise():
    pack = _pack_for_sql_summary(
        question="Y a-t-il actuellement des produits sous le seuil critique ?",
        sql_status="PROVEN_NO_DATA",
        rows=[],
        sql_payload={
            "sql_dispatch_trace": {"sql_operation": "get_low_stock_alerts", "row_count": 0},
            "low_stock_alerts": [],
        },
    )
    verification = verify_evidence(pack)
    answer, _, _ = compose_answer(pack, verification)
    assert "Aucun produit n’est actuellement sous le seuil critique de stock." in answer
    assert "preuve opérationnelle exploitable" not in answer
