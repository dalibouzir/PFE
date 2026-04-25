import json
from pathlib import Path

from app.ml.training.trainer import train_models
from app.core import config


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
    assert "qty_out" not in metadata["predictive_regression_features"]
    assert "loss_pct" not in metadata["predictive_regression_features"]
    assert "efficiency_pct" not in metadata["predictive_regression_features"]
    assert "qty_out" not in metadata["predictive_classification_features"]
    assert "loss_pct" not in metadata["predictive_classification_features"]
    assert "efficiency_pct" not in metadata["predictive_classification_features"]
    assert "qty_out" in metadata["assessment_anomaly_features"]
    assert "loss_pct" in metadata["assessment_anomaly_features"]
    assert "efficiency_pct" in metadata["assessment_anomaly_features"]
