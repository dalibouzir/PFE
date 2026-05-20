from __future__ import annotations

from app.ai.orchestrator.evidence_pipeline import AnswerPlan, EvidencePack, compose_answer, verify_evidence
from app.ai.schemas.agent_schemas import AgentRoute


def _pack(route: AgentRoute, required_sources: list[str], *, sql=False, rag=False, ml=False, recommendation=False) -> EvidencePack:
    return EvidencePack(
        question="q",
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
        sql={"tables_used": ["stocks"] if sql else [], "rows": [{"product": "mango"}] if sql else [], "metrics": {}, "calculations": {}, "payload": {"current_stock": [{"product": "mango"}]} if sql else {}},
        rag={"chunks": [{"title": "doc", "content": "best practice"}] if rag else [], "titles": ["doc"] if rag else [], "content_snippets": ["best practice"] if rag else [], "scores": [0.8] if rag else [], "topics": ["guidance"] if rag else []},
        ml={"risk_level": "HIGH"} if ml else {},
        recommendations={"actions": [{"title": "A"}]} if recommendation else {"actions": [], "insufficient_evidence": False},
        warnings=[],
        confidence=0.8,
        module_registry={},
    )


def test_sql_only_missing_sql_is_hard_gated():
    pack = _pack(AgentRoute.SQL_ONLY, ["SQL"], sql=False)
    verification = verify_evidence(pack)
    answer, blocks, metadata = compose_answer(pack, verification)
    assert "Donnée non disponible" in answer
    assert "SQL" in metadata["missing_evidence_types"]


def test_rag_only_missing_rag_is_hard_gated_with_knowledge_message():
    pack = _pack(AgentRoute.RAG_ONLY, ["RAG"], rag=False)
    verification = verify_evidence(pack)
    answer, blocks, metadata = compose_answer(pack, verification)
    assert "contexte documentaire" in answer.lower()
    assert "RAG" in metadata["missing_evidence_types"]


def test_hybrid_sql_ml_missing_ml_degrades_explicitly():
    pack = _pack(AgentRoute.HYBRID_SQL_ML, ["SQL", "ML"], sql=True, ml=False)
    verification = verify_evidence(pack)
    answer, blocks, metadata = compose_answer(pack, verification)
    assert "Aucun signal ML exploitable" in answer
    assert "ML" in metadata["missing_evidence_types"]
    assert "SQL" in metadata["found_evidence_types"]


def test_hybrid_sql_rag_requires_sql_and_uses_rag_when_required():
    pack = _pack(AgentRoute.HYBRID_SQL_RAG, ["SQL", "RAG"], sql=True, rag=True)
    verification = verify_evidence(pack)
    assert verification.ok is True
    answer, blocks, metadata = compose_answer(pack, verification)
    assert metadata["required_evidence_types"] == ["SQL", "RAG"]


def test_hybrid_full_missing_recommendation_is_hard_gated():
    pack = _pack(AgentRoute.HYBRID_FULL, ["SQL", "RECOMMENDATION"], sql=True, recommendation=False)
    verification = verify_evidence(pack)
    answer, blocks, metadata = compose_answer(pack, verification)
    assert "je ne peux pas générer de recommandations fiables" in answer.lower()
    assert "RECOMMENDATION" in metadata["missing_evidence_types"]
