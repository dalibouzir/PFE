from __future__ import annotations

import json
from pathlib import Path

import joblib

from app.core import config
from app.ml.training.trainer import MODEL_FILES
from app.ml.utils.model_registry import (
    ensure_registry_files,
    get_active_model_version,
    register_model_version,
    rollback_active_model,
    set_active_model_version,
    store_versioned_artifacts,
)
from app.ml.utils.model_validation import evaluate_validation_gates
from app.ml.utils.prediction_logging import append_prediction_log, read_prediction_logs
from scripts.ml_monitoring_report import run_monitoring_report


def _create_dummy_artifacts(tmp_path: Path) -> dict:
    sources = {}
    joblib.dump({"name": "loss"}, tmp_path / MODEL_FILES["loss_regressor"])
    joblib.dump({"name": "risk"}, tmp_path / MODEL_FILES["risk_classifier"])
    joblib.dump({"name": "anomaly"}, tmp_path / MODEL_FILES["anomaly_detector"])
    (tmp_path / MODEL_FILES["feature_metadata"]).write_text(json.dumps({"model_version": "dummy"}))
    for key, name in MODEL_FILES.items():
        sources[key] = str(tmp_path / name)
    return sources


def test_model_registry_creation_and_candidate_registration(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "ml_artifacts_path", str(tmp_path))
    ensure_registry_files()

    sources = _create_dummy_artifacts(tmp_path)
    stored = store_versioned_artifacts("v1", sources)

    record = register_model_version(
        model_version="v1",
        run_name="test-run",
        feature_schema_version="phase4-v1",
        training_rows=500,
        metrics={"regression_mae": 3.0, "false_low_high_risk_rate": 0.1},
        artifact_paths=stored,
        status="candidate",
        validation={"mvp_demo_allowed": True, "production_ready": False},
    )

    registry_path = tmp_path / "model_registry.json"
    assert registry_path.exists()
    payload = json.loads(registry_path.read_text())
    assert payload["versions"]
    assert record["status"] == "candidate"


def test_active_model_switch_and_rollback(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "ml_artifacts_path", str(tmp_path))
    ensure_registry_files()
    sources = _create_dummy_artifacts(tmp_path)

    stored_v1 = store_versioned_artifacts("v1", sources)
    register_model_version(
        model_version="v1",
        run_name="run-v1",
        feature_schema_version="phase4-v1",
        training_rows=600,
        metrics={"regression_mae": 3.2, "false_low_high_risk_rate": 0.1},
        artifact_paths=stored_v1,
        status="candidate",
        validation={"mvp_demo_allowed": True, "production_ready": False},
    )

    # Update source metadata then register v2 so copied files differ across versions.
    (tmp_path / MODEL_FILES["feature_metadata"]).write_text(json.dumps({"model_version": "v2"}))
    stored_v2 = store_versioned_artifacts("v2", sources)
    register_model_version(
        model_version="v2",
        run_name="run-v2",
        feature_schema_version="phase4-v1",
        training_rows=700,
        metrics={"regression_mae": 3.1, "false_low_high_risk_rate": 0.1},
        artifact_paths=stored_v2,
        status="candidate",
        validation={"mvp_demo_allowed": True, "production_ready": False},
    )

    set_active_model_version("v1")
    assert get_active_model_version()["model_version"] == "v1"

    set_active_model_version("v2")
    assert get_active_model_version()["model_version"] == "v2"

    rollback_active_model()
    assert get_active_model_version()["model_version"] == "v1"


def test_validation_gate_output_contains_expected_flags():
    metadata = {
        "feature_schema_version": "phase4-v1",
        "forbidden_predictive_violations": {
            "predictive_regression_features": [],
            "predictive_classification_features": [],
        },
        "metrics": {
            "regression_mae": 3.8,
            "regression_stage_mean_mae": 2.7,
            "regression_product_stage_mean_mae": 2.8,
            "false_low_high_risk_rate": 0.1,
        },
    }
    gates = evaluate_validation_gates(
        metadata=metadata,
        artifact_compatibility={"compatible": True},
        trained_rows=1500,
    )
    assert "gates" in gates
    assert gates["mvp_demo_allowed"] is True
    assert gates["production_ready"] is False
    assert gates["underperforms_stage_baseline"] is True


def test_prediction_log_write_and_read(tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "ml_artifacts_path", str(tmp_path))
    append_prediction_log(
        {
            "model_version": "v-test",
            "feature_schema_version": "phase4-v1",
            "predicted_loss_pct": 9.2,
            "risk_level": "medium",
            "risk_method": "thresholded_predicted_loss",
            "warning_flags": ["low_data_confidence"],
        }
    )
    logs = read_prediction_logs()
    assert len(logs) == 1
    assert logs[0]["model_version"] == "v-test"


def test_monitoring_report_generation(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "ml_artifacts_path", str(tmp_path))
    ensure_registry_files()

    sources = _create_dummy_artifacts(tmp_path)
    stored = store_versioned_artifacts("v-active", sources)
    register_model_version(
        model_version="v-active",
        run_name="monitoring",
        feature_schema_version="phase4-v1",
        training_rows=1200,
        metrics={"regression_mae": 3.8, "regression_stage_mean_mae": 2.7, "false_low_high_risk_rate": 0.1},
        artifact_paths=stored,
        status="candidate",
        validation={"mvp_demo_allowed": True, "production_ready": False},
        extra_metadata={
            "dataset_profile": {
                "product_distribution": {"mango": 12},
                "stage_distribution": {"drying": 6},
                "risk_distribution": {"low": 10, "medium": 2},
            },
            "contains_demo_seed_data": True,
        },
    )
    set_active_model_version("v-active")

    output_json = tmp_path / "ml_monitoring_report.json"
    output_md = tmp_path / "ml_monitoring_report.md"
    report = run_monitoring_report(db_session, output_json=output_json, output_md=output_md)

    assert output_json.exists()
    assert output_md.exists()
    assert report["dataset"]["row_count"] > 0
    assert "warnings" in report
