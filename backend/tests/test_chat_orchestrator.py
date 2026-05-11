from datetime import UTC, datetime

from app.models.user import User
from app.schemas.chat import ChatMetricFact
from app.services.assistant import RetrievalHit
from app.services.chat_orchestrator import (
    analyze_scope_contamination,
    build_grounded_citation,
    classify_scope,
    orchestrate_context,
)
from app.services.chat_retrieval_router import build_retrieval_plan


def test_hybrid_orchestration_merges_sql_rag_and_citations(db_session):
    manager = db_session.query(User).first()
    plan = build_retrieval_plan("why are drying losses high this week for mango?")
    hit = RetrievalHit(
        chunk_id="c1",
        source_table="process_steps",
        source_record_ref="process_step:1",
        content="Drying losses for mango increased this week.",
        metadata={
            "chunk_type": "process_step_summary",
            "source_row_id": "1",
            "freshness_timestamp": datetime.now(UTC).isoformat(),
            "product_name": "mango",
            "stage": "drying",
            "stage_canonical": "drying",
            "loss_pct": 14.0,
            "batch_id": str(manager.cooperative.batches[0].id),
        },
        distance=0.2,
        keyword_score=0.7,
        vector_rank=1,
        keyword_rank=1,
        rerank_score=0.42,
        retrieval_reason="chunk_type_boost,freshness_boost",
    )
    metrics = [
        ChatMetricFact(
            source_id="ops",
            region="Thies",
            crop="multi",
            metric="avg_batch_loss_pct",
            period="current",
            value=12.0,
            unit="%",
            notes=None,
        )
    ]
    payload = orchestrate_context(
        db_session,
        current_user=manager,
        retrieval_plan=plan,
        message="why are drying losses high this week for mango?",
        retrieval_hits=[hit],
        context_metrics=metrics,
        retrieval_filters={"stage_canonical": {"drying"}},
    )
    assert payload.sql_context["metric_count"] >= 1
    assert payload.rag_context["hit_count"] == 1
    assert payload.citations
    assert payload.confidence_estimate["label"] in {"LOW", "MEDIUM", "HIGH"}


def test_grounded_citation_contains_provenance_fields():
    citation = build_grounded_citation(
        source_type="rag_chunk",
        source_table="recommendations",
        source_row_id="row-1",
        chunk_type="recommendation_context",
        retrieval_score=0.37,
        freshness_timestamp=datetime.now(UTC).isoformat(),
        evidence_snippet="Recommendation suggests airflow correction.",
        evidence_reason="chunk_type_boost",
    )
    for key in (
        "citation_id",
        "source_type",
        "source_table",
        "source_row_id",
        "chunk_type",
        "retrieval_score",
        "freshness_timestamp",
        "evidence_snippet",
        "evidence_reason",
        "grounding_confidence",
    ):
        assert key in citation


def test_orchestrator_citation_uses_entity_fallback_for_chunk_type(db_session):
    manager = db_session.query(User).first()
    plan = build_retrieval_plan("why anomaly risk is high?")
    hit = RetrievalHit(
        chunk_id="c-legacy",
        source_table="ml_prediction_logs",
        source_record_ref="ml_prediction_log:1",
        content="Legacy ML anomaly evidence.",
        metadata={
            "entity": "ml_prediction_logs",
            "source_row_id": "1",
            "freshness_timestamp": datetime.now(UTC).isoformat(),
        },
        distance=0.3,
        keyword_score=0.3,
        vector_rank=1,
        keyword_rank=1,
        rerank_score=0.25,
        retrieval_reason="chunk_type_boost",
    )
    payload = orchestrate_context(
        db_session,
        current_user=manager,
        retrieval_plan=plan,
        message="why anomaly risk is high?",
        retrieval_hits=[hit],
        context_metrics=[],
        retrieval_filters={},
    )
    assert payload.citations
    first = payload.citations[0]
    assert first["chunk_type"] == "ml_prediction_context"
    assert first["source_table"] == "ml_prediction_logs"
    assert first["source_row_id"] == "1"


def test_sql_prioritized_when_contradictions_detected(db_session):
    manager = db_session.query(User).first()
    plan = build_retrieval_plan("why are losses high?")
    hit = RetrievalHit(
        chunk_id="c2",
        source_table="batches",
        source_record_ref="batch:1",
        content="Historical chunk suggests 35% loss.",
        metadata={
            "chunk_type": "batch_summary",
            "source_row_id": "1",
            "loss_pct": 35.0,
            "freshness_timestamp": datetime.now(UTC).isoformat(),
        },
        distance=0.3,
        keyword_score=0.4,
        vector_rank=1,
        keyword_rank=1,
        rerank_score=0.2,
        retrieval_reason="base_rank",
    )
    metrics = [
        ChatMetricFact(
            source_id="ops",
            region="Thies",
            crop="multi",
            metric="avg_batch_loss_pct",
            period="current",
            value=10.0,
            unit="%",
            notes=None,
        )
    ]
    payload = orchestrate_context(
        db_session,
        current_user=manager,
        retrieval_plan=plan,
        message="why are losses high?",
        retrieval_hits=[hit],
        context_metrics=metrics,
        retrieval_filters={},
    )
    assert payload.contradictory_signals
    assert any("prioritize SQL" in note for note in payload.grounding_notes)


def test_scope_classifier_detects_lot_product_stage_and_benchmark():
    scope = classify_scope("why is LOT-MANG-004 drying loss high compared with benchmark reference?")
    assert scope.scope_level == "LOT"
    assert scope.lot_codes
    assert scope.stages
    assert scope.benchmark_intent is True


def test_contamination_diagnostics_counts_unrelated_products():
    scope = classify_scope("why are mango drying losses high?")
    hits = [
        type(
            "H",
            (),
            {
                "source_table": "process_steps",
                "metadata": {"product_name": "mango", "stage_canonical": "drying", "chunk_type": "process_step_summary"},
            },
        )(),
        type(
            "H",
            (),
            {
                "source_table": "process_steps",
                "metadata": {"product_name": "bissap", "stage_canonical": "drying", "chunk_type": "process_step_summary"},
            },
        )(),
    ]
    summary = analyze_scope_contamination(scope=scope, hits=hits)
    assert summary["unrelated_product_evidence_count"] >= 1
    assert summary["contamination_risk_score"] > 0.0


def test_confidence_degrades_with_scope_contamination(db_session):
    manager = db_session.query(User).first()
    plan = build_retrieval_plan("why are mango drying losses high?")
    metrics = [
        ChatMetricFact(
            source_id="ops",
            region="Thies",
            crop="multi",
            metric="avg_batch_loss_pct",
            period="current",
            value=12.0,
            unit="%",
            notes=None,
        )
    ]

    clean_hit = RetrievalHit(
        chunk_id="clean-1",
        source_table="process_steps",
        source_record_ref="process_step:1",
        content="Mango drying losses increased.",
        metadata={"chunk_type": "process_step_summary", "product_name": "mango", "stage_canonical": "drying", "freshness_timestamp": datetime.now(UTC).isoformat()},
        distance=0.2,
        keyword_score=0.7,
        vector_rank=1,
        keyword_rank=1,
        rerank_score=0.5,
        retrieval_reason="scope_match_boost",
    )
    contaminated_hit = RetrievalHit(
        chunk_id="cont-1",
        source_table="process_steps",
        source_record_ref="process_step:2",
        content="Bissap drying losses catastrophic.",
        metadata={"chunk_type": "process_step_summary", "product_name": "bissap", "stage_canonical": "drying", "freshness_timestamp": datetime.now(UTC).isoformat()},
        distance=0.2,
        keyword_score=0.7,
        vector_rank=1,
        keyword_rank=1,
        rerank_score=0.5,
        retrieval_reason="scope_mismatch_penalty",
    )

    clean = orchestrate_context(
        db_session,
        current_user=manager,
        retrieval_plan=plan,
        message="why are mango drying losses high?",
        retrieval_hits=[clean_hit],
        context_metrics=metrics,
        retrieval_filters={"product_name": {"mango"}, "stage_canonical": {"drying"}},
    )
    contaminated = orchestrate_context(
        db_session,
        current_user=manager,
        retrieval_plan=plan,
        message="why are mango drying losses high?",
        retrieval_hits=[clean_hit, contaminated_hit],
        context_metrics=metrics,
        retrieval_filters={"product_name": {"mango"}, "stage_canonical": {"drying"}},
    )
    assert contaminated.confidence_estimate["score"] <= clean.confidence_estimate["score"]
