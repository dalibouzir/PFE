import json
from pathlib import Path

from app.ml.training.trainer import train_models
from app.core import config
from app.ml.utils.feature_prep import FEATURE_SCHEMA_VERSION


def test_training_pipeline_creates_artifacts(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(config.settings, "ml_min_rows", 1)
    monkeypatch.setattr(config.settings, "ml_artifacts_path", str(tmp_path))

    result = train_models(db_session, run_name="test-run")
    assert result["trained_rows"] > 0

    artifacts = [
        Path(tmp_path / "loss_regressor.joblib"),
        Path(tmp_path / "risk_classifier.joblib"),
        Path(tmp_path / "anomaly_detector.joblib"),
        Path(tmp_path / "feature_metadata.json"),
    ]
    assert all(item.exists() for item in artifacts)

    metadata = json.loads(Path(tmp_path / "feature_metadata.json").read_text())
    assert metadata["feature_schema_version"] == FEATURE_SCHEMA_VERSION
    assert metadata["predictive_features_clean"] is True
    assert metadata["forbidden_predictive_violations"]["predictive_regression_features"] == []
    assert metadata["forbidden_predictive_violations"]["predictive_classification_features"] == []
    assert "qty_out" not in metadata["predictive_regression_features"]
    assert "loss_pct" not in metadata["predictive_regression_features"]
    assert "efficiency_pct" not in metadata["predictive_regression_features"]
    assert "deviation_from_stage_avg" not in metadata["predictive_regression_features"]
    assert "qty_out" not in metadata["predictive_classification_features"]
    assert "loss_pct" not in metadata["predictive_classification_features"]
    assert "efficiency_pct" not in metadata["predictive_classification_features"]
    assert "deviation_from_stage_avg" not in metadata["predictive_classification_features"]
    assert "deviation_from_stage_avg" in metadata["assessment_anomaly_features"]
    assert "qty_out" in metadata["assessment_anomaly_features"]
    assert "loss_pct" in metadata["assessment_anomaly_features"]
    assert "efficiency_pct" in metadata["assessment_anomaly_features"]
    assert metadata["metrics"]["split_details"]["strategy"] in {"time_based", "random_fallback"}
    assert "classification_per_class" in metadata["metrics"]
    assert "classification_confusion_matrix" in metadata["metrics"]
