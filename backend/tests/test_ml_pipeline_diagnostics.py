from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.core import config
from app.ml.features import engineer
from app.ml.features.engineer import build_features
from app.ml.inference.predictor import _prepare_assessment_features, predict_from_features
from app.ml.recommendations.rule_engine import build_recommendation
from app.ml.training.trainer import train_models
from app.ml.utils.feature_prep import (
    FORBIDDEN_PREDICTIVE_FEATURES,
    assign_thresholded_risk_level,
    forbidden_predictive_violations,
    get_risk_thresholds,
    prepare_feature_frame,
)
from app.utils.exceptions import ValidationError


def test_feature_engineering_loss_and_efficiency_are_correct(db_session):
    feature_set = build_features(db_session)
    assert not feature_set.features.empty

    row = feature_set.features.iloc[0]
    expected_loss_pct = ((row["qty_in"] - row["qty_out"]) / row["qty_in"]) * 100.0
    expected_efficiency = row["qty_out"] / row["qty_in"]

    assert abs(float(row["loss_pct"]) - float(expected_loss_pct)) < 1e-9
    assert abs(float(row["efficiency_pct"]) - float(expected_efficiency)) < 1e-9
    assert np.isfinite(row["loss_pct"])
    assert np.isfinite(row["efficiency_pct"])


def test_feature_engineering_no_division_by_zero(monkeypatch):
    monkeypatch.setattr(
        engineer,
        "fetch_process_records",
        lambda _db: [
            {
                "batch_id": "batch-1",
                "cooperative_id": "coop-1",
                "product": "mango",
                "process_type": "drying",
                "qty_in": 0.0,
                "qty_out": 0.0,
                "batch_size": 0.0,
                "batch_current_qty": 0.0,
                "date": date(2026, 1, 1),
                "stock_level": 10.0,
            }
        ],
    )

    feature_set = build_features(db=None)
    row = feature_set.features.iloc[0]
    assert row["loss_pct"] == 0.0
    assert row["efficiency_pct"] == 0.0
    assert np.isfinite(row["loss_pct"])
    assert np.isfinite(row["efficiency_pct"])


def test_historical_product_stage_features_use_previous_rows_only(monkeypatch):
    monkeypatch.setattr(
        engineer,
        "fetch_process_records",
        lambda _db: [
            {
                "batch_id": "b1",
                "cooperative_id": "c1",
                "product": "mango",
                "process_type": "Séchage",
                "qty_in": 100.0,
                "qty_out": 90.0,
                "batch_size": 100.0,
                "batch_current_qty": 90.0,
                "date": date(2026, 1, 1),
                "stock_level": 1000.0,
            },
            {
                "batch_id": "b2",
                "cooperative_id": "c1",
                "product": "mango",
                "process_type": "Séchage",
                "qty_in": 100.0,
                "qty_out": 80.0,
                "batch_size": 100.0,
                "batch_current_qty": 80.0,
                "date": date(2026, 1, 2),
                "stock_level": 1000.0,
            },
        ],
    )
    feature_set = build_features(db=None)
    rows = feature_set.features.sort_values("date").reset_index(drop=True)
    first_loss = float(rows.loc[0, "loss_pct"])
    second_avg = float(rows.loc[1, "product_stage_historical_avg_loss"])
    second_roll5 = float(rows.loc[1, "product_stage_rolling_loss_last_5"])
    assert abs(first_loss - 10.0) < 1e-6
    assert abs(second_avg - first_loss) < 1e-6
    assert abs(second_roll5 - first_loss) < 1e-6


def test_assessment_feature_preparation_handles_missing_loss_and_zero_qty():
    features = pd.DataFrame(
        [
            {
                "product": "mango",
                "process_type": "drying",
                "qty_in": 0.0,
                "qty_out": 0.0,
                "batch_size": 100.0,
                "stock_level": 50.0,
                "date": "2026-01-01",
                "month": 1,
                "week_of_year": 1,
                "season": "dry",
                "historical_avg_loss_same_product": 10.0,
                "historical_avg_loss_same_stage": 9.5,
                "historical_avg_efficiency_same_stage": 0.9,
                "deviation_from_stage_avg": 0.0,
                "previous_batch_loss": 11.0,
                "rolling_loss_last_n_batches": 10.5,
                "rolling_efficiency_last_n_batches": 0.89,
                "loss_pct": np.nan,
                "efficiency_pct": np.nan,
            }
        ]
    )
    prepared = _prepare_assessment_features(features)
    assert prepared.loc[0, "loss_pct"] == 0.0
    assert prepared.loc[0, "efficiency_pct"] == 0.0


def test_training_inference_feature_columns_are_consistent(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "ml_min_rows", 1)
    monkeypatch.setattr(config.settings, "ml_artifacts_path", str(tmp_path))

    train_models(db_session, run_name="feature-consistency")
    metadata = json.loads(Path(tmp_path / "feature_metadata.json").read_text())

    features = build_features(db_session).features
    prepared, _ = prepare_feature_frame(features)

    for group in (
        "predictive_regression_features",
        "predictive_classification_features",
        "assessment_anomaly_features",
    ):
        missing = set(metadata[group]) - set(prepared.columns)
        assert not missing, f"Missing columns for {group}: {missing}"


def test_predictive_feature_contract_excludes_forbidden_fields():
    prepared, feature_sets = prepare_feature_frame(
        pd.DataFrame(
            [
                {
                    "product": "mango",
                    "process_type": "drying",
                    "qty_in": 100.0,
                    "qty_out": 90.0,
                    "batch_size": 100.0,
                    "stock_level": 40.0,
                    "date": "2026-01-01",
                    "month": 1,
                    "week_of_year": 1,
                    "season": "dry",
                    "historical_avg_loss_same_product": 10.0,
                    "historical_avg_loss_same_stage": 9.0,
                    "historical_avg_efficiency_same_stage": 0.9,
                    "deviation_from_stage_avg": 1.0,
                    "previous_batch_loss": 8.0,
                    "rolling_loss_last_n_batches": 8.5,
                    "rolling_efficiency_last_n_batches": 0.91,
                    "loss_pct": 10.0,
                    "efficiency_pct": 0.9,
                }
            ]
        )
    )
    del prepared
    predictive_features = feature_sets["predictive_regression_features"]
    assert forbidden_predictive_violations(predictive_features) == []
    assert not (set(predictive_features) & FORBIDDEN_PREDICTIVE_FEATURES)
    enriched_expected = {
        "stage_canonical",
        "product_stage_key",
        "stock_pressure_ratio",
        "qty_in_log",
        "batch_size_log",
        "stage_order",
        "product_stage_historical_avg_loss",
        "product_stage_rolling_loss_last_5",
        "stage_season_avg_loss",
        "loss_volatility_product_stage",
    }
    assert enriched_expected.issubset(set(predictive_features))


def test_predictive_inference_works_without_deviation_from_stage_avg(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "ml_min_rows", 1)
    monkeypatch.setattr(config.settings, "ml_artifacts_path", str(tmp_path))
    train_models(db_session, run_name="predictive-contract")

    first_feature = build_features(db_session).features.iloc[0].to_dict()
    payload = pd.DataFrame(
        [
            {
                "product": first_feature["product"],
                "process_type": first_feature["process_type"],
                "qty_in": first_feature["qty_in"],
                "batch_size": first_feature["batch_size"],
                "stock_level": first_feature["stock_level"],
                "date": first_feature["date"],
                "month": first_feature["month"],
                "week_of_year": first_feature["week_of_year"],
                "season": first_feature["season"],
                "historical_avg_loss_same_product": first_feature["historical_avg_loss_same_product"],
                "historical_avg_loss_same_stage": first_feature["historical_avg_loss_same_stage"],
                "historical_avg_efficiency_same_stage": first_feature["historical_avg_efficiency_same_stage"],
                "previous_batch_loss": first_feature["previous_batch_loss"],
                "rolling_loss_last_n_batches": first_feature["rolling_loss_last_n_batches"],
                "rolling_efficiency_last_n_batches": first_feature["rolling_efficiency_last_n_batches"],
            }
        ]
    )
    prediction = predict_from_features(db_session, payload)
    assert "predicted_loss_pct" in prediction
    assert "risk_level" in prediction
    assert prediction["risk_method"] == "thresholded_predicted_loss"
    assert "risk_thresholds_used" in prediction


def test_predictive_inference_rejects_forbidden_fields(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "ml_min_rows", 1)
    monkeypatch.setattr(config.settings, "ml_artifacts_path", str(tmp_path))
    train_models(db_session, run_name="predictive-contract-forbidden")

    first_feature = build_features(db_session).features.iloc[0].to_dict()
    payload = pd.DataFrame(
        [
            {
                "product": first_feature["product"],
                "process_type": first_feature["process_type"],
                "qty_in": first_feature["qty_in"],
                "batch_size": first_feature["batch_size"],
                "stock_level": first_feature["stock_level"],
                "date": first_feature["date"],
                "month": first_feature["month"],
                "week_of_year": first_feature["week_of_year"],
                "season": first_feature["season"],
                "historical_avg_loss_same_product": first_feature["historical_avg_loss_same_product"],
                "historical_avg_loss_same_stage": first_feature["historical_avg_loss_same_stage"],
                "historical_avg_efficiency_same_stage": first_feature["historical_avg_efficiency_same_stage"],
                "previous_batch_loss": first_feature["previous_batch_loss"],
                "rolling_loss_last_n_batches": first_feature["rolling_loss_last_n_batches"],
                "rolling_efficiency_last_n_batches": first_feature["rolling_efficiency_last_n_batches"],
                "deviation_from_stage_avg": first_feature["deviation_from_stage_avg"],
            }
        ]
    )
    with pytest.raises(ValidationError, match="forbidden target-derived fields"):
        predict_from_features(db_session, payload)


def test_thresholded_risk_logic_and_configurable_thresholds(monkeypatch):
    monkeypatch.setattr(config.settings, "ml_risk_low_threshold", 6.0)
    monkeypatch.setattr(config.settings, "ml_risk_high_threshold", 12.0)

    assert assign_thresholded_risk_level(5.99) == "low"
    assert assign_thresholded_risk_level(6.0) == "medium"
    assert assign_thresholded_risk_level(11.99) == "medium"
    assert assign_thresholded_risk_level(12.0) == "high"
    thresholds = get_risk_thresholds()
    assert thresholds["low_to_medium"] == 6.0
    assert thresholds["medium_to_high"] == 12.0


def test_recommendations_generated_for_all_stages():
    for stage in ("cleaning", "drying", "sorting", "packaging"):
        recommendation = build_recommendation(
            {
                "critical_stage": stage,
                "risk_level": "medium",
                "predicted_loss_pct": 14.0,
                "is_anomalous": False,
                "top_signals": ["Stage loss above historical average"],
            }
        )
        assert recommendation["critical_stage"] == stage
        assert recommendation["recommended_actions"]
