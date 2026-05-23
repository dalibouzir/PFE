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
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_recall_fscore_support,
    r2_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.constants import MODEL_FILES
from app.ml.features.engineer import build_features
from app.ml.recommendations.impact_engine import train_impact_models
from app.ml.recommendations.rule_engine import NORMAL_PERFORMANCE_SIGNAL, build_recommendation, derive_prediction_signals
from app.ml.utils.model_registry import (
    ensure_registry_files,
    get_active_model_version,
    register_model_version,
    set_active_model_version,
    store_versioned_artifacts,
)
from app.ml.utils.model_validation import evaluate_validation_gates
from app.ml.utils.feature_prep import (
    CATEGORICAL_FEATURES,
    FEATURE_SCHEMA_VERSION,
    FORBIDDEN_PREDICTIVE_FEATURES,
    assign_risk_level,
    assign_thresholded_risk_level,
    forbidden_predictive_violations,
    get_risk_thresholds,
    prepare_feature_frame,
)
from app.models.batch import Batch
from app.models.ml import MLModelRegistry, MLTrainingRun
from app.utils.exceptions import ValidationError


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


def _split_train_test_indices(prepared: pd.DataFrame, test_size: float = 0.2) -> tuple[pd.Index, pd.Index, Dict]:
    unique_dates = np.sort(prepared["date_ordinal"].dropna().unique())
    if len(unique_dates) >= 2:
        split_pos = max(1, int(round(len(unique_dates) * (1.0 - test_size))))
        split_pos = min(split_pos, len(unique_dates) - 1)
        split_cutoff = unique_dates[split_pos - 1]

        train_indices = prepared.index[prepared["date_ordinal"] <= split_cutoff]
        test_indices = prepared.index[prepared["date_ordinal"] > split_cutoff]
        if len(train_indices) > 0 and len(test_indices) > 0:
            return train_indices, test_indices, {
                "strategy": "time_based",
                "split_cutoff_date_ordinal": int(split_cutoff),
                "train_rows": int(len(train_indices)),
                "test_rows": int(len(test_indices)),
            }

    train_indices, test_indices = train_test_split(prepared.index, test_size=test_size, random_state=42)
    return train_indices, test_indices, {
        "strategy": "random_fallback",
        "train_rows": int(len(train_indices)),
        "test_rows": int(len(test_indices)),
    }


def _contains_demo_seed_data(db: Session, batch_ids: pd.Series) -> bool:
    values = [value for value in batch_ids.dropna().unique().tolist() if value is not None]
    if not values:
        return False
    demo_batch = db.scalar(
        select(Batch.id).where(
            Batch.id.in_(values),
            Batch.code.like("DEMO-ML-%"),
        )
    )
    return demo_batch is not None


def train_models(db: Session, run_name: str) -> Dict:
    ensure_registry_files()
    feature_set = build_features(db)
    df = feature_set.features
    if df.empty or len(df) < settings.ml_min_rows:
        raise ValidationError("Not enough data to train ML models. Seed data first.")

    prepared, feature_groups = prepare_feature_frame(df)
    prepared["risk_level"] = prepared["loss_pct"].apply(assign_risk_level)
    dataset_profile = {
        "product_distribution": {str(k): int(v) for k, v in prepared["product"].value_counts(dropna=False).to_dict().items()},
        "stage_distribution": {str(k): int(v) for k, v in prepared["stage_canonical"].value_counts(dropna=False).to_dict().items()},
        "risk_distribution": {str(k): int(v) for k, v in prepared["risk_level"].value_counts(dropna=False).to_dict().items()},
        "missing_feature_rate": {
            str(col): float(prepared[col].isna().mean())
            for col in feature_groups["predictive_regression_features"]
            if col in prepared.columns
        },
    }

    y_loss = prepared["loss_pct"]
    y_risk = prepared["risk_level"]
    regression_features = feature_groups["predictive_regression_features"]
    classification_features = feature_groups["predictive_classification_features"]
    anomaly_features = feature_groups["assessment_anomaly_features"]
    regression_violations = forbidden_predictive_violations(regression_features)
    classification_violations = forbidden_predictive_violations(classification_features)
    if regression_violations or classification_violations:
        raise ValidationError(
            "Predictive feature contract violated. Remove target-derived predictive features and retrain."
        )

    train_indices, test_indices, split_details = _split_train_test_indices(prepared, test_size=0.2)
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
    baseline_loss = np.full(shape=len(y_loss_test), fill_value=float(y_loss_train.mean()))
    stage_mean_map = prepared.loc[train_indices].groupby("stage_canonical")["loss_pct"].mean().to_dict()
    product_stage_mean_map = prepared.loc[train_indices].groupby(["product", "stage_canonical"])["loss_pct"].mean().to_dict()
    default_mean = float(y_loss_train.mean())
    stage_mean_pred = np.array(
        [stage_mean_map.get(row["stage_canonical"], default_mean) for _, row in prepared.loc[test_indices].iterrows()],
        dtype=float,
    )
    product_stage_mean_pred = np.array(
        [
            product_stage_mean_map.get(
                (row["product"], row["stage_canonical"]),
                stage_mean_map.get(row["stage_canonical"], default_mean),
            )
            for _, row in prepared.loc[test_indices].iterrows()
        ],
        dtype=float,
    )
    thresholded_risk_pred = np.array([assign_thresholded_risk_level(float(value)) for value in loss_pred])
    high_mask = y_risk_test == "high"
    false_low_high_risk_rate = float(np.mean(thresholded_risk_pred[high_mask] == "low")) if int(np.sum(high_mask)) else 0.0
    risk_labels = ["low", "medium", "high"]
    precision, recall, f1, support = precision_recall_fscore_support(
        y_risk_test,
        risk_pred,
        labels=risk_labels,
        zero_division=0,
    )
    class_report = {
        label: {
            "precision": float(precision[idx]),
            "recall": float(recall[idx]),
            "f1": float(f1[idx]),
            "support": int(support[idx]),
        }
        for idx, label in enumerate(risk_labels)
    }
    confusion = confusion_matrix(y_risk_test, risk_pred, labels=risk_labels).tolist()

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
        "regression_r2": float(r2_score(y_loss_test, loss_pred)),
        "regression_baseline_mae": float(mean_absolute_error(y_loss_test, baseline_loss)),
        "regression_baseline_rmse": float(mean_squared_error(y_loss_test, baseline_loss, squared=False)),
        "regression_stage_mean_mae": float(mean_absolute_error(y_loss_test, stage_mean_pred)),
        "regression_product_stage_mean_mae": float(mean_absolute_error(y_loss_test, product_stage_mean_pred)),
        "classification_accuracy": float(accuracy_score(y_risk_test, risk_pred)),
        "classification_macro_f1": float(f1_score(y_risk_test, risk_pred, average="macro")),
        "classification_f1": float(f1_score(y_risk_test, risk_pred, average="weighted")),
        "classification_majority_baseline_accuracy": float(np.mean(y_risk_test == y_risk_train.mode().iloc[0])),
        "thresholded_risk_accuracy": float(accuracy_score(y_risk_test, thresholded_risk_pred)),
        "thresholded_risk_macro_f1": float(f1_score(y_risk_test, thresholded_risk_pred, average="macro")),
        "false_low_high_risk_rate": false_low_high_risk_rate,
        "risk_thresholds_used": get_risk_thresholds(),
        "classification_per_class": class_report,
        "classification_confusion_matrix": confusion,
        "anomaly_ratio": float(anomaly_ratio),
        "recommendation_action_coverage": recommendation_action_coverage,
        "recommendation_issue_alignment": recommendation_issue_alignment,
        "split_details": split_details,
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
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "trained_rows": int(len(df)),
        "predictive_regression_features": regression_features,
        "predictive_classification_features": classification_features,
        "assessment_anomaly_features": anomaly_features,
        "forbidden_predictive_features": sorted(FORBIDDEN_PREDICTIVE_FEATURES),
        "forbidden_predictive_violations": {
            "predictive_regression_features": regression_violations,
            "predictive_classification_features": classification_violations,
        },
        "predictive_features_clean": not (regression_violations or classification_violations),
        "contains_demo_seed_data": _contains_demo_seed_data(db, prepared["batch_id"]),
        "dataset_profile": dataset_profile,
        "metrics": metrics,
    }
    metadata_path = artifacts_dir / MODEL_FILES["feature_metadata"]
    metadata_path.write_text(json.dumps(metadata, indent=2))

    artifact_compatibility = {
        "compatible": not (regression_violations or classification_violations),
        "reason": "ok" if not (regression_violations or classification_violations) else "forbidden_predictive_features_present",
    }
    validation = evaluate_validation_gates(
        metadata=metadata,
        artifact_compatibility=artifact_compatibility,
        trained_rows=int(len(df)),
    )
    metadata["validation"] = validation
    metadata_path.write_text(json.dumps(metadata, indent=2))

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

    artifact_paths = {
        name: str(artifacts_dir / file_name)
        for name, file_name in MODEL_FILES.items()
    }
    versioned_artifacts = store_versioned_artifacts(model_version, artifact_paths)
    active_before = get_active_model_version()
    notes = (
        "Candidate registered after validation. "
        f"mvp_demo_allowed={validation['mvp_demo_allowed']} production_ready={validation['production_ready']}"
    )
    registry_record = register_model_version(
        model_version=model_version,
        run_name=run_name,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        training_rows=int(len(df)),
        metrics=metrics,
        artifact_paths=versioned_artifacts,
        status="candidate",
        notes=notes,
        validation=validation,
        extra_metadata={
            "contains_demo_seed_data": metadata["contains_demo_seed_data"],
            "dataset_profile": dataset_profile,
        },
    )

    activation_action = "candidate_registered"
    if validation.get("can_activate") and not active_before:
        set_active_model_version(model_version, notes="Auto-activated: first validated model")
        activation_action = "auto_activated_first_validated_model"

    return {
        "run_id": run.id,
        "run_name": run.run_name,
        "trained_rows": len(df),
        "model_version": model_version,
        "metrics": metrics,
        "validation": validation,
        "registry_status": registry_record.get("status"),
        "activation_action": activation_action,
        "completed_at": run.completed_at,
    }
