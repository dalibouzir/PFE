from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import joblib

from app.core.config import settings
from app.ml.training.trainer import MODEL_FILES
from app.utils.exceptions import ValidationError


@dataclass
class ModelBundle:
    loss_regressor: object
    risk_classifier: object
    anomaly_detector: object
    metadata: Dict
    predictive_regression_features: List[str]
    predictive_classification_features: List[str]
    assessment_anomaly_features: List[str]


def _artifact_error() -> ValidationError:
    return ValidationError("ML model artifacts are missing or invalid. Retrain models first.")


def load_model_bundle() -> ModelBundle:
    artifacts_dir = Path(settings.ml_artifacts_path)
    metadata_path = artifacts_dir / MODEL_FILES["feature_metadata"]
    artifact_paths = {
        name: artifacts_dir / file_name
        for name, file_name in MODEL_FILES.items()
    }
    if any(not path.exists() for path in artifact_paths.values()):
        raise _artifact_error()

    try:
        metadata = json.loads(metadata_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise _artifact_error() from exc

    required_metadata = (
        "predictive_regression_features",
        "predictive_classification_features",
        "assessment_anomaly_features",
    )
    if any(not isinstance(metadata.get(key), list) or not metadata.get(key) for key in required_metadata):
        raise _artifact_error()

    try:
        loss_regressor = joblib.load(artifact_paths["loss_regressor"])
        risk_classifier = joblib.load(artifact_paths["risk_classifier"])
        anomaly_detector = joblib.load(artifact_paths["anomaly_detector"])
    except Exception as exc:
        raise _artifact_error() from exc

    return ModelBundle(
        loss_regressor=loss_regressor,
        risk_classifier=risk_classifier,
        anomaly_detector=anomaly_detector,
        metadata=metadata,
        predictive_regression_features=list(metadata["predictive_regression_features"]),
        predictive_classification_features=list(metadata["predictive_classification_features"]),
        assessment_anomaly_features=list(metadata["assessment_anomaly_features"]),
    )


def artifacts_status() -> Dict[str, bool]:
    artifacts_dir = Path(settings.ml_artifacts_path)
    return {
        name: (artifacts_dir / file_name).exists()
        for name, file_name in MODEL_FILES.items()
    }
