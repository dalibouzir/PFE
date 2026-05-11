from __future__ import annotations

import uuid
import time
from typing import Dict, Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.ml.features.engineer import build_features
from app.ml.recommendations.rule_engine import derive_prediction_signals
from app.ml.utils.feature_prep import (
    assign_thresholded_risk_level,
    assign_risk_level,
    forbidden_predictive_violations,
    get_risk_thresholds,
    prepare_feature_frame,
)
from app.ml.utils.model_store import load_model_bundle
from app.ml.utils.prediction_logging import prediction_warning_flags
from app.models.enums import RiskLevel
from app.models.ml import MLPredictionLog
from app.utils.exceptions import ValidationError


def _sigmoid(value: float) -> float:
    return float(1 / (1 + np.exp(-value)))


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _normalize_record(record: Dict) -> Dict:
    normalized = {}
    for key, value in record.items():
        if hasattr(value, "isoformat"):
            normalized[key] = value.isoformat()
        elif isinstance(value, uuid.UUID):
            normalized[key] = str(value)
        elif isinstance(value, np.generic):
            normalized[key] = value.item()
        else:
            normalized[key] = value
    return normalized


def _prepare_assessment_features(features: pd.DataFrame) -> pd.DataFrame:
    working = features.copy()
    if "qty_out" not in working.columns:
        raise ValidationError("Assessment mode requires qty_out.")

    if "loss_pct" not in working.columns:
        qty_in = pd.to_numeric(working["qty_in"], errors="coerce").fillna(0.0)
        qty_out = pd.to_numeric(working["qty_out"], errors="coerce").fillna(0.0)
        valid_input = qty_in > 0
        working["loss_pct"] = np.where(valid_input, ((qty_in - qty_out) / qty_in) * 100.0, 0.0)
    else:
        missing_loss = working["loss_pct"].isna()
        missing_input = pd.to_numeric(working.loc[missing_loss, "qty_in"], errors="coerce").fillna(0.0)
        missing_output = pd.to_numeric(working.loc[missing_loss, "qty_out"], errors="coerce").fillna(0.0)
        valid_missing = missing_input > 0
        filled_loss = np.where(valid_missing, ((missing_input - missing_output) / missing_input) * 100.0, 0.0)
        working.loc[missing_loss, "loss_pct"] = filled_loss
    working["loss_pct"] = pd.to_numeric(working["loss_pct"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(lower=0.0)

    if "efficiency_pct" not in working.columns:
        working["efficiency_pct"] = working.apply(
            lambda row: _safe_ratio(float(row["qty_out"]), float(row["qty_in"])),
            axis=1,
        )
    else:
        missing_efficiency = working["efficiency_pct"].isna()
        working.loc[missing_efficiency, "efficiency_pct"] = working.loc[missing_efficiency].apply(
            lambda row: _safe_ratio(float(row["qty_out"]), float(row["qty_in"])),
            axis=1,
        )
    working["efficiency_pct"] = pd.to_numeric(working["efficiency_pct"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(lower=0.0)
    if "deviation_from_stage_avg" not in working.columns:
        if "historical_avg_loss_same_stage" in working.columns:
            working["deviation_from_stage_avg"] = (
                working["loss_pct"] - pd.to_numeric(working["historical_avg_loss_same_stage"], errors="coerce").fillna(0.0)
            )
        else:
            working["deviation_from_stage_avg"] = 0.0
    else:
        missing_deviation = working["deviation_from_stage_avg"].isna()
        if "historical_avg_loss_same_stage" in working.columns:
            fallback = working["loss_pct"] - pd.to_numeric(working["historical_avg_loss_same_stage"], errors="coerce").fillna(0.0)
            working.loc[missing_deviation, "deviation_from_stage_avg"] = fallback.loc[missing_deviation]
        else:
            working.loc[missing_deviation, "deviation_from_stage_avg"] = 0.0
    working["deviation_from_stage_avg"] = pd.to_numeric(
        working["deviation_from_stage_avg"], errors="coerce"
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    return working


def predict_from_features(
    db: Session,
    features: pd.DataFrame,
    batch_id: Optional[str] = None,
) -> Dict:
    started = time.perf_counter()
    if features.empty:
        raise ValidationError("No features available for prediction.")
    forbidden_columns = forbidden_predictive_violations(list(features.columns))
    if forbidden_columns:
        raise ValidationError(
            "Predictive payload contains forbidden target-derived fields "
            f"{forbidden_columns}. Use pre-stage fields only, or use /ml/assess for post-stage assessment."
        )

    bundle = load_model_bundle()
    prepared, _ = prepare_feature_frame(features)

    loss_predictions = bundle.loss_regressor.predict(prepared[bundle.predictive_regression_features])
    critical_index = int(np.argmax(loss_predictions))
    critical_row = prepared.iloc[critical_index]

    predicted_loss_pct = float(loss_predictions[critical_index])
    predicted_efficiency_pct = max(0.0, 1.0 - predicted_loss_pct / 100.0)
    risk_level = assign_thresholded_risk_level(predicted_loss_pct)
    risk_thresholds = get_risk_thresholds()
    top_signals = derive_prediction_signals(predicted_loss_pct, critical_row)

    output = {
        "mode": "predictive",
        "batch_id": str(batch_id) if batch_id else None,
        "product": str(critical_row["product"]),
        "critical_stage": str(critical_row["process_type"]),
        "predicted_loss_pct": round(predicted_loss_pct, 2),
        "predicted_efficiency_pct": round(predicted_efficiency_pct, 3),
        "risk_level": risk_level,
        "risk_method": "thresholded_predicted_loss",
        "risk_thresholds_used": risk_thresholds,
        "top_signals": top_signals,
        "model_version": str(bundle.metadata.get("model_version", "unknown")),
        "feature_schema_version": str(bundle.metadata.get("feature_schema_version", "unknown")),
        "warning_flags": prediction_warning_flags(bundle.metadata),
        "latency_ms": round((time.perf_counter() - started) * 1000.0, 2),
    }

    parsed_batch_id = None
    if batch_id:
        try:
            parsed_batch_id = uuid.UUID(str(batch_id))
        except ValueError:
            parsed_batch_id = None

    input_snapshot = [_normalize_record(item) for item in features.to_dict(orient="records")]

    prediction_log = MLPredictionLog(
        batch_id=parsed_batch_id,
        model_version=bundle.metadata.get("model_version", "unknown"),
        product=output["product"],
        critical_stage=output["critical_stage"],
        predicted_loss_pct=output["predicted_loss_pct"],
        expected_efficiency_pct=output["predicted_efficiency_pct"],
        risk_level=RiskLevel(risk_level) if risk_level in RiskLevel._value2member_map_ else None,
        anomaly_score=None,
        is_anomalous=None,
        input_snapshot=input_snapshot,
        output_snapshot=output,
    )
    db.add(prediction_log)
    db.commit()

    return output


def assess_from_features(
    features: pd.DataFrame,
    batch_id: Optional[str] = None,
) -> Dict:
    if features.empty:
        raise ValidationError("No features available for assessment.")

    bundle = load_model_bundle()
    assessment_features = _prepare_assessment_features(features)
    prepared, _ = prepare_feature_frame(assessment_features)

    observed_losses = prepared["loss_pct"].to_numpy()
    benchmark_loss_predictions = bundle.loss_regressor.predict(prepared[bundle.predictive_regression_features])
    anomaly_scores = bundle.anomaly_detector.decision_function(prepared[bundle.assessment_anomaly_features])
    anomaly_flags = bundle.anomaly_detector.predict(prepared[bundle.assessment_anomaly_features])

    critical_index = int(np.argmax(observed_losses))
    critical_row = prepared.iloc[critical_index]

    observed_loss_pct = float(observed_losses[critical_index])
    observed_efficiency_pct = float(critical_row["efficiency_pct"])
    anomaly_score = _sigmoid(float(-anomaly_scores[critical_index]))
    is_anomalous = bool(anomaly_flags[critical_index] == -1)
    top_signals = derive_prediction_signals(observed_loss_pct, critical_row)

    return {
        "mode": "assessment",
        "batch_id": str(batch_id) if batch_id else None,
        "product": str(critical_row["product"]),
        "critical_stage": str(critical_row["process_type"]),
        "observed_loss_pct": round(observed_loss_pct, 2),
        "observed_efficiency_pct": round(observed_efficiency_pct, 3),
        "benchmark_predicted_loss_pct": round(float(benchmark_loss_predictions[critical_index]), 2),
        "risk_level": assign_risk_level(observed_loss_pct),
        "anomaly_score": round(anomaly_score, 3),
        "is_anomalous": is_anomalous,
        "top_signals": top_signals,
    }


def assess_for_batch(db: Session, batch_id: str) -> Dict:
    feature_set = build_features(db, batch_id)
    if feature_set.features.empty:
        raise ValidationError("Batch does not have enough process data to assess.")
    return assess_from_features(feature_set.features, batch_id=batch_id)
