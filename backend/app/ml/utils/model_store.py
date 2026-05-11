from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import joblib

from app.core.config import settings
from app.ml.training.trainer import MODEL_FILES
from app.ml.utils.feature_prep import FORBIDDEN_PREDICTIVE_FEATURES, forbidden_predictive_violations
from app.ml.utils.model_registry import get_active_model_version, materialize_model_artifacts
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


def _artifact_error(reason: str | None = None) -> ValidationError:
    base = "ML model artifacts are missing or invalid. Retrain models first."
    if reason:
        base = f"{base} {reason}"
    return ValidationError(base)


def load_model_bundle() -> ModelBundle:
    artifacts_dir = Path(settings.ml_artifacts_path)
    active_model = get_active_model_version()
    if active_model:
        active_version = str(active_model.get("model_version"))
        metadata_path = artifacts_dir / MODEL_FILES["feature_metadata"]
        if metadata_path.exists():
            try:
                existing_metadata = json.loads(metadata_path.read_text())
            except (OSError, json.JSONDecodeError):
                existing_metadata = {}
            existing_version = str(existing_metadata.get("model_version") or "")
            if existing_version and existing_version != active_version:
                try:
                    materialize_model_artifacts(active_version)
                except Exception:
                    pass

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

    regression_violations = forbidden_predictive_violations(
        list(metadata.get("predictive_regression_features", []))
    )
    classification_violations = forbidden_predictive_violations(
        list(metadata.get("predictive_classification_features", []))
    )
    if regression_violations or classification_violations:
        raise _artifact_error(
            "Artifact predictive features are contaminated with target-derived fields "
            f"(forbidden={sorted(FORBIDDEN_PREDICTIVE_FEATURES)}, "
            f"regression_violations={regression_violations}, "
            f"classification_violations={classification_violations}). "
            "Retrain with a clean predictive feature contract."
        )

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


def artifact_compatibility_status() -> Dict:
    artifacts_dir = Path(settings.ml_artifacts_path)
    metadata_path = artifacts_dir / MODEL_FILES["feature_metadata"]
    if not metadata_path.exists():
        return {
            "compatible": False,
            "reason": "missing_metadata",
            "predictive_regression_features": [],
            "predictive_classification_features": [],
            "forbidden_predictive_violations": {},
        }

    try:
        metadata = json.loads(metadata_path.read_text())
    except (OSError, json.JSONDecodeError):
        return {
            "compatible": False,
            "reason": "invalid_metadata_json",
            "predictive_regression_features": [],
            "predictive_classification_features": [],
            "forbidden_predictive_violations": {},
        }

    regression = list(metadata.get("predictive_regression_features", []))
    classification = list(metadata.get("predictive_classification_features", []))
    regression_violations = forbidden_predictive_violations(regression)
    classification_violations = forbidden_predictive_violations(classification)
    detailed_violations = {
        "predictive_regression_features": regression_violations,
        "predictive_classification_features": classification_violations,
    }
    contaminated = bool(regression_violations or classification_violations)

    active_model = get_active_model_version()

    return {
        "compatible": not contaminated,
        "reason": "forbidden_predictive_features_present" if contaminated else "ok",
        "model_version": metadata.get("model_version"),
        "active_model_version": active_model.get("model_version") if active_model else None,
        "feature_schema_version": metadata.get("feature_schema_version"),
        "predictive_regression_features": regression,
        "predictive_classification_features": classification,
        "forbidden_predictive_violations": detailed_violations if contaminated else {},
        "forbidden_predictive_features": sorted(FORBIDDEN_PREDICTIVE_FEATURES),
    }
