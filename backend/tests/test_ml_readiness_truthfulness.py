from __future__ import annotations

from datetime import date, datetime, timezone

from app.ml.cold_start_priors import get_cold_start_priors
from app.ml.features import engineer
from app.ml.features.engineer import build_features
from app.ml.readiness import RecommendationMode, build_readiness_metadata, recommendation_mode


def test_low_dataset_never_claims_promoted_state():
    metadata = build_readiness_metadata(
        dataset_n=30,
        model_gate_status="FAIL",
        model_gate_passed=False,
        mode=RecommendationMode.RULE_BASED,
        evidence_sources=["rule_engine"],
    )
    assert metadata["ml_readiness_state"] in {"INSUFFICIENT_DATA", "BASELINE_ONLY"}
    assert metadata["ml_readiness_state"] != "ML_PROMOTED"
    assert metadata["promoted"] is False


def test_failing_gate_returns_non_promoted_fallback_state():
    metadata = build_readiness_metadata(
        dataset_n=1400,
        model_gate_status="FAIL",
        model_gate_passed=False,
        mode=RecommendationMode.ML_PROMOTED,
        evidence_sources=["rule_engine", "impact_model"],
    )
    assert metadata["ml_readiness_state"] != "ML_PROMOTED"
    assert metadata["promoted"] is False
    assert metadata["fallback_reason"] in {"model_gate_failed", "ml_support_non_promoted"}


def test_passing_gate_but_insufficient_n_still_not_promoted():
    metadata = build_readiness_metadata(
        dataset_n=850,
        model_gate_status="PASS",
        model_gate_passed=True,
        mode=RecommendationMode.ML_PROMOTED,
        evidence_sources=["rule_engine", "impact_model"],
    )
    assert metadata["ml_readiness_state"] != "ML_PROMOTED"
    assert metadata["promoted"] is False
    assert metadata["fallback_reason"] == "insufficient_dataset_rows"


def test_rule_recommendation_mode_is_rule_based():
    mode = recommendation_mode(recommendation_source="rule_engine", ml_support_used=False)
    assert mode == RecommendationMode.RULE_BASED


def test_ml_supported_rule_recommendation_mode_is_ml_assisted_not_promoted():
    mode = recommendation_mode(recommendation_source="rule_engine", ml_support_used=True)
    assert mode == RecommendationMode.ML_ASSISTED
    metadata = build_readiness_metadata(
        dataset_n=2000,
        model_gate_status="PASS",
        model_gate_passed=True,
        mode=mode,
        evidence_sources=["rule_engine", "impact_model"],
    )
    assert metadata["ml_readiness_state"] == "ML_ASSISTED"
    assert metadata["promoted"] is False


def test_cold_start_priors_do_not_claim_app_history_without_real_flag():
    priors = get_cold_start_priors()
    assert priors
    assert all(item["source_type"] in {"expert_rule", "external_context", "app_history"} for item in priors)
    assert all(item["source_type"] != "app_history" for item in priors)


def test_duration_feature_logic_handles_missing_timestamps(monkeypatch):
    monkeypatch.setattr(
        engineer,
        "fetch_process_records",
        lambda _db: [
            {
                "batch_id": "b1",
                "cooperative_id": "c1",
                "product": "mangue",
                "process_type": "sechage",
                "qty_in": 100.0,
                "qty_out": 90.0,
                "batch_size": 100.0,
                "batch_current_qty": 90.0,
                "date": date(2026, 1, 1),
                "stock_level": 10.0,
                "sequence_order": 1,
                "duration_minutes": None,
                "step_started_at": None,
                "step_completed_at": None,
                "step_updated_at": None,
                "batch_postharvest_started_at": None,
            },
            {
                "batch_id": "b1",
                "cooperative_id": "c1",
                "product": "mangue",
                "process_type": "tri",
                "qty_in": 90.0,
                "qty_out": 86.0,
                "batch_size": 100.0,
                "batch_current_qty": 86.0,
                "date": date(2026, 1, 1),
                "stock_level": 10.0,
                "sequence_order": 2,
                "duration_minutes": 30,
                "step_started_at": datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
                "step_completed_at": datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc),
                "step_updated_at": datetime(2026, 1, 1, 9, 35, tzinfo=timezone.utc),
                "batch_postharvest_started_at": datetime(2026, 1, 1, 8, 30, tzinfo=timezone.utc),
            },
        ],
    )
    feature_set = build_features(db=None)
    assert not feature_set.features.empty
    assert "step_duration_minutes" in feature_set.features.columns
    assert "delay_since_previous_step_minutes" in feature_set.features.columns
    assert "total_postharvest_duration_minutes" in feature_set.features.columns
    assert "cumulative_duration_before_stage" in feature_set.features.columns
    assert "missing_duration_flag" in feature_set.features.columns

    first = feature_set.features[feature_set.features["process_type"] == "sechage"].iloc[0]
    assert float(first["step_duration_minutes"]) == 0.0
    assert int(first["missing_duration_flag"]) == 1
