from __future__ import annotations

import pandas as pd

from app.ml.utils.feature_prep import prepare_feature_frame
from scripts.evaluate_ml_reliability import _build_gate_results, _build_selection


def _time_eval_fixture(*, model_mae: float, baseline_mae: float, model_f1: float, thr1_f1: float, thr2_f1: float):
    return {
        "regression": {
            "model": {"mae": model_mae},
            "baselines": {
                "stage_season_mean_loss": {"mae": baseline_mae},
                "stage_mean_loss": {"mae": baseline_mae + 0.1},
            },
        },
        "classification": {
            "model": {"macro_f1": model_f1},
            "thresholded_predicted_loss_baseline": {"macro_f1": thr1_f1},
            "thresholded_product_stage_average_baseline": {"macro_f1": thr2_f1},
        },
    }


def test_evaluation_modules_import_with_current_runtime():
    import scripts.evaluate_ml_reliability as reliability_mod  # noqa: F401
    import scripts.evaluate_ml_weather as weather_mod  # noqa: F401


def test_prepare_feature_frame_populates_weather_timestamp_ordinal():
    df = pd.DataFrame(
        [
            {
                "product": "Mangue",
                "process_type": "Sechage",
                "stage_canonical": "drying",
                "product_stage_key": "mangue|drying",
                "season": "dry",
                "qty_in": 100.0,
                "batch_size": 100.0,
                "stock_level": 50.0,
                "month": 1,
                "week_of_year": 1,
                "historical_avg_loss_same_product": 5.0,
                "historical_avg_loss_same_stage": 5.0,
                "historical_avg_efficiency_same_stage": 0.95,
                "rolling_loss_last_n_batches": 5.0,
                "rolling_efficiency_last_n_batches": 0.95,
                "date": "2026-01-01",
                "weather_feature_timestamp": "2026-01-01T00:00:00Z",
            }
        ]
    )
    prepared, _ = prepare_feature_frame(df)
    assert "weather_feature_timestamp_ordinal" in prepared.columns
    assert float(prepared.iloc[0]["weather_feature_timestamp_ordinal"]) > 0


def test_prepare_feature_frame_weather_timestamp_missing_falls_back_safely():
    df = pd.DataFrame(
        [
            {
                "product": "Mangue",
                "process_type": "Sechage",
                "stage_canonical": "drying",
                "product_stage_key": "mangue|drying",
                "season": "dry",
                "qty_in": 100.0,
                "batch_size": 100.0,
                "stock_level": 50.0,
                "month": 1,
                "week_of_year": 1,
                "historical_avg_loss_same_product": 5.0,
                "historical_avg_loss_same_stage": 5.0,
                "historical_avg_efficiency_same_stage": 0.95,
                "rolling_loss_last_n_batches": 5.0,
                "rolling_efficiency_last_n_batches": 0.95,
                "date": "2026-01-01",
                "weather_feature_timestamp": None,
            }
        ]
    )
    prepared, _ = prepare_feature_frame(df)
    assert "weather_feature_timestamp_ordinal" in prepared.columns
    assert float(prepared.iloc[0]["weather_feature_timestamp_ordinal"]) == 0.0


def test_regression_fallback_remains_baseline_when_gate_fails():
    eval_payload = _time_eval_fixture(
        model_mae=4.0,
        baseline_mae=3.0,
        model_f1=0.45,
        thr1_f1=0.35,
        thr2_f1=0.33,
    )
    gates = _build_gate_results(eval_payload, has_reco_feedback=False)
    selection = _build_selection(gates)
    assert gates["regression"]["status"] == "FAIL"
    assert selection["regression"].startswith("baseline:")


def test_recommendation_policy_remains_rule_based_without_feedback():
    eval_payload = _time_eval_fixture(
        model_mae=3.0,
        baseline_mae=4.0,
        model_f1=0.45,
        thr1_f1=0.35,
        thr2_f1=0.33,
    )
    gates = _build_gate_results(eval_payload, has_reco_feedback=False)
    assert gates["recommendation_policy"]["status"] == "RULE_BASED"
    assert gates["recommendation_policy"]["action_outcome_feedback_exists"] is False
