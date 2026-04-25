from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest, RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.features.engineer import build_features
from app.ml.recommendations.impact_engine import train_impact_models
from app.ml.recommendations.rule_engine import NORMAL_PERFORMANCE_SIGNAL, build_recommendation, derive_prediction_signals
from app.ml.utils.feature_prep import CATEGORICAL_FEATURES, assign_risk_level, prepare_feature_frame
from app.models.ml import MLModelRegistry, MLTrainingRun
from app.utils.exceptions import ValidationError


MODEL_FILES = {
    "loss_regressor": "loss_regressor.joblib",
    "risk_classifier": "risk_classifier.joblib",
    "anomaly_detector": "anomaly_detector.joblib",
    "feature_metadata": "feature_metadata.json",
}


def _ensure_artifacts_dir() -> Path:
    path = Path(settings.ml_artifacts_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_preprocessor(feature_names: list[str]) -> ColumnTransformer:
    categorical = [feature for feature in feature_names if feature in CATEGORICAL_FEATURES]
    numeric = [feature for feature in feature_names if feature not in CATEGORICAL_FEATURES]
    return ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
            ("num", "passthrough", numeric),
        ]
    )


def _build_pipeline(feature_names: list[str], estimator: object) -> Pipeline:
    return Pipeline(
        steps=[
            ("preprocessor", _build_preprocessor(feature_names)),
            ("model", estimator),
        ]
    )


def train_models(db: Session, run_name: str) -> Dict:
    feature_set = build_features(db)
    df = feature_set.features
    if df.empty or len(df) < settings.ml_min_rows:
        raise ValidationError("Not enough data to train ML models. Seed data first.")

    prepared, feature_groups = prepare_feature_frame(df)
    prepared["risk_level"] = prepared["loss_pct"].apply(assign_risk_level)

    y_loss = prepared["loss_pct"]
    y_risk = prepared["risk_level"]
    regression_features = feature_groups["predictive_regression_features"]
    classification_features = feature_groups["predictive_classification_features"]
    anomaly_features = feature_groups["assessment_anomaly_features"]

    train_indices, test_indices = train_test_split(
        prepared.index, test_size=0.2, random_state=42
    )
    X_loss_train = prepared.loc[train_indices, regression_features]
    X_loss_test = prepared.loc[test_indices, regression_features]
    X_risk_train = prepared.loc[train_indices, classification_features]
    X_risk_test = prepared.loc[test_indices, classification_features]
    X_anomaly_train = prepared.loc[train_indices, anomaly_features]
    X_anomaly_test = prepared.loc[test_indices, anomaly_features]
    eval_rows = prepared.loc[test_indices].reset_index(drop=True)
    y_loss_train = y_loss.loc[train_indices]
    y_loss_test = y_loss.loc[test_indices]
    y_risk_train = y_risk.loc[train_indices]
    y_risk_test = y_risk.loc[test_indices]

    loss_model = _build_pipeline(
        regression_features,
        RandomForestRegressor(n_estimators=250, random_state=42),
    )
    risk_model = _build_pipeline(
        classification_features,
        RandomForestClassifier(n_estimators=250, random_state=42),
    )
    anomaly_model = _build_pipeline(
        anomaly_features,
        IsolationForest(n_estimators=200, random_state=42, contamination=0.08),
    )

    loss_model.fit(X_loss_train, y_loss_train)
    risk_model.fit(X_risk_train, y_risk_train)
    anomaly_model.fit(X_anomaly_train)

    loss_pred = loss_model.predict(X_loss_test)
    risk_pred = risk_model.predict(X_risk_test)
    anomaly_scores = anomaly_model.decision_function(X_anomaly_test)
    anomaly_flags = anomaly_model.predict(X_anomaly_test)
    anomaly_ratio = float(np.mean(anomaly_scores < 0))

    recommendation_actions = []
    recommendation_alignments = []
    for idx, row in eval_rows.iterrows():
        predicted_loss = float(loss_pred[idx])
        top_signals = derive_prediction_signals(predicted_loss, row)
        is_anomalous = bool(anomaly_flags[idx] == -1)
        prediction_payload = {
            "critical_stage": row["process_type"],
            "risk_level": str(risk_pred[idx]),
            "predicted_loss_pct": predicted_loss,
            "is_anomalous": is_anomalous,
            "top_signals": top_signals,
        }
        recommendation = build_recommendation(prediction_payload)
        recommendation_actions.append(bool(recommendation.get("recommended_actions")))
        expected_issue = "high_loss"
        if predicted_loss < settings.step_loss_threshold:
            expected_issue = "efficiency_dip"
        if (
            prediction_payload["risk_level"] == "low"
            and not is_anomalous
            and top_signals == [NORMAL_PERFORMANCE_SIGNAL]
        ):
            expected_issue = "monitor"
        recommendation_alignments.append(recommendation.get("issue_type") == expected_issue)

    recommendation_action_coverage = float(np.mean(recommendation_actions)) if recommendation_actions else 0.0
    recommendation_issue_alignment = float(np.mean(recommendation_alignments)) if recommendation_alignments else 0.0

    metrics = {
        "regression_mae": float(mean_absolute_error(y_loss_test, loss_pred)),
        "regression_rmse": float(mean_squared_error(y_loss_test, loss_pred, squared=False)),
        "classification_accuracy": float(accuracy_score(y_risk_test, risk_pred)),
        "classification_f1": float(f1_score(y_risk_test, risk_pred, average="weighted")),
        "anomaly_ratio": float(anomaly_ratio),
        "recommendation_action_coverage": recommendation_action_coverage,
        "recommendation_issue_alignment": recommendation_issue_alignment,
    }

    artifacts_dir = _ensure_artifacts_dir()
    model_version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    joblib.dump(loss_model, artifacts_dir / MODEL_FILES["loss_regressor"])
    joblib.dump(risk_model, artifacts_dir / MODEL_FILES["risk_classifier"])
    joblib.dump(anomaly_model, artifacts_dir / MODEL_FILES["anomaly_detector"])

    impact_metrics = train_impact_models(db, model_version=model_version)
    metrics.update({
        "impact_model_ready": bool(impact_metrics.get("impact_model_ready", False)),
        "impact_feedback_rows": int(impact_metrics.get("feedback_rows", 0)),
        "impact_holdout_rows": int(impact_metrics.get("holdout_rows", 0)),
        "impact_holdout_ratio": float(impact_metrics.get("holdout_ratio", 0.0)),
        "impact_real_feedback_rows": int(impact_metrics.get("real_feedback_rows", 0)),
        "impact_proxy_feedback_rows": int(impact_metrics.get("proxy_feedback_rows", 0)),
        "impact_precision_at_1": float(impact_metrics.get("precision_at_1", 0.0)),
        "impact_harmful_rate": float(impact_metrics.get("harmful_rate", 0.0)),
        "impact_calibration_error": float(impact_metrics.get("calibration_error", 0.0)),
        "impact_mean_loss_reduction_after_action": float(impact_metrics.get("mean_loss_reduction_after_action", 0.0)),
        "impact_coverage": float(impact_metrics.get("coverage", 0.0)),
        "impact_recommended_rows": int(impact_metrics.get("recommended_rows", 0)),
        "impact_targets_met": bool(impact_metrics.get("targets_met", False)),
        "impact_used_auto_backfill": bool(impact_metrics.get("used_auto_backfill", False)),
    })

    metadata = {
        "model_version": model_version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "predictive_regression_features": regression_features,
        "predictive_classification_features": classification_features,
        "assessment_anomaly_features": anomaly_features,
        "metrics": metrics,
    }
    (artifacts_dir / MODEL_FILES["feature_metadata"]).write_text(json.dumps(metadata, indent=2))

    run = MLTrainingRun(
        run_name=run_name,
        status="completed",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        dataset_rows=len(df),
        metrics=metrics,
    )
    db.add(run)
    db.flush()

    models = [
        MLModelRegistry(
            model_name="loss_regressor",
            version=model_version,
            artifact_path=str(artifacts_dir / MODEL_FILES["loss_regressor"]),
            metrics=metrics,
            is_active=True,
            training_run_id=run.id,
        ),
        MLModelRegistry(
            model_name="risk_classifier",
            version=model_version,
            artifact_path=str(artifacts_dir / MODEL_FILES["risk_classifier"]),
            metrics=metrics,
            is_active=True,
            training_run_id=run.id,
        ),
        MLModelRegistry(
            model_name="anomaly_detector",
            version=model_version,
            artifact_path=str(artifacts_dir / MODEL_FILES["anomaly_detector"]),
            metrics=metrics,
            is_active=True,
            training_run_id=run.id,
        ),
    ]
    db.add_all(models)
    db.commit()

    return {
        "run_id": run.id,
        "run_name": run.run_name,
        "trained_rows": len(df),
        "model_version": model_version,
        "metrics": metrics,
        "completed_at": run.completed_at,
    }
