from app.services.rag_grounding import (
    WARNING_CONTRADICTORY_EVIDENCE,
    WARNING_LOW_GROUNDING_CONFIDENCE,
    WARNING_ML_CONTEXT_MISSING,
    WARNING_ML_LOGS_EMPTY,
    WARNING_STALE_CONTEXT,
    detect_contradictions,
    summarize_grounding_quality,
)


def test_detect_contradictions_between_sql_rag_and_ml():
    contradictions = detect_contradictions(
        sql_context={"metrics": {"avg_batch_loss_pct": 12.0}},
        rag_context={"loss_pct_values": [32.0, 30.0]},
        ml_context={"predicted_loss_pct": 35.0},
    )
    assert contradictions


def test_grounding_summary_flags_stale_and_low_confidence():
    summary = summarize_grounding_quality(
        retrieval_summary={
            "hit_count": 1,
            "freshness": {"freshness_avg_minutes": 60 * 48},
        },
        sql_context={"metrics": {}},
        rag_context={"loss_pct_values": [20.0]},
        ml_context={"items": []},
    )
    assert WARNING_LOW_GROUNDING_CONFIDENCE in summary.warning_flags
    assert WARNING_STALE_CONTEXT in summary.warning_flags
    assert summary.confidence_label in {"LOW", "MEDIUM", "HIGH"}
    assert 0.0 <= summary.confidence_score <= 1.0


def test_grounding_summary_marks_contradictory_evidence():
    summary = summarize_grounding_quality(
        retrieval_summary={"hit_count": 4, "freshness": {"freshness_avg_minutes": 20}},
        sql_context={"metrics": {"avg_batch_loss_pct": 10.0}},
        rag_context={"loss_pct_values": [28.0]},
        ml_context={"predicted_loss_pct": 31.0, "items": [{"x": 1}]},
    )
    assert WARNING_CONTRADICTORY_EVIDENCE in summary.warning_flags
    assert summary.contradictory_signals


def test_grounding_ml_logs_empty_warning_is_specific():
    summary = summarize_grounding_quality(
        retrieval_summary={"hit_count": 3, "freshness": {"freshness_avg_minutes": 30}},
        sql_context={"metrics": {"avg_batch_loss_pct": 12.0}},
        rag_context={"loss_pct_values": [10.0, 11.0]},
        ml_context={"items": [], "ml_status": "empty"},
    )
    assert WARNING_ML_LOGS_EMPTY in summary.warning_flags
    assert WARNING_ML_CONTEXT_MISSING not in summary.warning_flags


def test_grounding_ml_context_missing_when_status_error():
    summary = summarize_grounding_quality(
        retrieval_summary={"hit_count": 3, "freshness": {"freshness_avg_minutes": 30}},
        sql_context={"metrics": {"avg_batch_loss_pct": 12.0}},
        rag_context={"loss_pct_values": [10.0, 11.0]},
        ml_context={"items": [], "ml_status": "error"},
    )
    assert WARNING_ML_CONTEXT_MISSING in summary.warning_flags
