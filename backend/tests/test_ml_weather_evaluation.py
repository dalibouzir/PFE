from __future__ import annotations

import json

import pandas as pd

from app.ml.features.engineer import build_features
from app.ml.utils.feature_prep import prepare_feature_frame
from app.ml.weather_features import build_weather_feature_frame
from scripts.evaluate_ml_weather import run_weather_evaluation


def test_weather_timestamp_leakage_is_rejected():
    events = pd.DataFrame(
        [
            {
                "cooperative_id": "c1",
                "date": "2026-01-01T12:00:00Z",
            }
        ]
    )
    weather_records = [
        {
            "timestamp": "2026-01-01T13:00:00Z",
            "temperature": 31.0,
            "relative_humidity": 80.0,
            "source_kind": "observed_historical",
        }
    ]
    try:
        build_weather_feature_frame(events, weather_records=weather_records, enforce_leakage_check=True)
        assert False, "Expected leakage validation error."
    except ValueError as exc:
        assert "Weather leakage detected" in str(exc)


def test_missing_weather_does_not_crash_feature_build(db_session):
    feature_set = build_features(db_session, include_weather=True)
    assert not feature_set.features.empty
    assert "weather_available" in feature_set.features.columns
    assert feature_set.diagnostics is not None
    assert "weather" in feature_set.diagnostics


def test_train_and_inference_columns_match_with_weather(db_session):
    feature_set = build_features(db_session, include_weather=True)
    prepared_train, _ = prepare_feature_frame(feature_set.features.copy())
    prepared_infer, _ = prepare_feature_frame(feature_set.features.head(1).copy())
    assert set(prepared_train.columns) == set(prepared_infer.columns)


def test_weather_evaluation_report_contains_coverage_and_fallback_decision(db_session, tmp_path):
    output_json = tmp_path / "ml_weather_evaluation.json"
    output_md = tmp_path / "ml_weather_evaluation.md"
    report = run_weather_evaluation(db_session, output_json=output_json, output_md=output_md)

    assert output_json.exists()
    assert output_md.exists()
    assert "weather_coverage" in report
    assert "comparison" in report
    assert "regression" in report["comparison"]
    assert "selected_decision" in report["comparison"]["regression"]
    assert report["leakage_check"]["status"] == "PASS"

    reg = report["comparison"]["regression"]
    baseline = float(reg["best_baseline_mae"])
    weather_mae = float(reg["weather_model_mae"])
    if weather_mae >= baseline * 0.9:
        assert report["gates"]["regression_weather"] == "FAIL"

    payload = json.loads(output_json.read_text())
    assert "weather_coverage" in payload
    assert "selected_decision" in payload["comparison"]["regression"]
