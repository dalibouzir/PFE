from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Dict, List, Optional
from uuid import UUID

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.features.engineer import build_features
from app.ml.llm.provider import generate_explanation
from app.ml.advisory_diagnostics import (
    ADVISORY_CAVEAT,
    BENCHMARK_SOURCE,
    ML_STRATEGY,
    compute_critical_risk_advisory,
    detect_assessment_anomalies,
    estimate_loss_with_stage_baseline,
    rank_rule_recommendations,
)
from app.ml.readiness import (
    build_readiness_metadata,
    evaluate_model_gate,
    infer_evidence_sources,
    recommendation_mode,
)
from app.ml.recommendations.rule_engine import LIMITED_CONFIDENCE_SIGNAL, build_recommendation
from app.ml.utils.feature_prep import assign_thresholded_risk_level, get_risk_thresholds
from app.ml.utils.model_registry import get_active_model_version
from app.ml.utils.prediction_logging import append_prediction_log
from app.ml.utils.model_store import artifact_compatibility_status, artifacts_status, load_model_bundle
from app.models.ml import MLRecommendationLog, MLTrainingRun, RecommendationFeedbackLog
from app.schemas.ml import AssessmentFeaturePayload, PredictiveFeaturePayload, RecommendationFeedbackCreate
from app.utils.exceptions import ValidationError


DURATION_FEATURE_KEYS = {
    "step_duration_minutes",
    "delay_since_previous_step_minutes",
    "total_postharvest_duration_minutes",
    "cumulative_duration_before_stage",
    "missing_duration_flag",
}
WEATHER_FEATURE_KEYS = {
    "weather_available",
    "weather_feature_timestamp",
    "weather_avg_humidity_window",
    "weather_max_humidity_window",
    "weather_avg_temperature_window",
    "weather_avg_dew_point_window",
    "weather_avg_wind_speed_window",
    "weather_avg_surface_pressure_window",
    "weather_rain_flag_window",
    "weather_precip_total_window",
    "weather_is_forecast",
    "weather_is_observed",
}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        out = float(value)
    except (TypeError, ValueError):
        return default
    if out != out:  # NaN
        return default
    return out


def _select_critical_feature_row(
    feature_records: List[Dict],
    *,
    product: Optional[str],
    critical_stage: Optional[str],
) -> Dict:
    if not feature_records:
        return {}
    product_target = str(product or "").strip().lower()
    stage_target = str(critical_stage or "").strip().lower()
    for row in feature_records:
        row_product = str(row.get("product") or "").strip().lower()
        row_stage = str(row.get("process_type") or row.get("stage") or row.get("stage_canonical") or "").strip().lower()
        if row_product == product_target and row_stage == stage_target:
            return row
    for row in feature_records:
        row_stage = str(row.get("process_type") or row.get("stage") or row.get("stage_canonical") or "").strip().lower()
        if row_stage == stage_target:
            return row
    return feature_records[0]


def _assessment_historical_context(feature_records: List[Dict]) -> Dict:
    if not feature_records:
        return {}
    frame = pd.DataFrame(feature_records).copy()
    if frame.empty:
        return {}
    if "loss_pct" not in frame.columns:
        return {}

    frame["product"] = frame.get("product", "unknown").astype(str).str.lower().str.strip()
    frame["stage"] = frame.get("process_type", frame.get("stage", "unknown")).astype(str).str.lower().str.strip()
    frame["loss_pct"] = pd.to_numeric(frame.get("loss_pct"), errors="coerce")
    frame["step_duration_minutes"] = pd.to_numeric(frame.get("step_duration_minutes"), errors="coerce")
    frame["delay_since_previous_step_minutes"] = pd.to_numeric(frame.get("delay_since_previous_step_minutes"), errors="coerce")
    frame = frame.dropna(subset=["loss_pct"])
    if frame.empty:
        return {}

    stage_loss_thresholds = {
        str(stage): float(value)
        for stage, value in frame.groupby("stage")["loss_pct"].quantile(0.95).to_dict().items()
    }

    product_stage_bounds: Dict[str, Dict[str, float]] = {}
    grouped = frame.groupby(["product", "stage"])["loss_pct"]
    for (product, stage), series in grouped:
        q1 = float(series.quantile(0.25))
        q3 = float(series.quantile(0.75))
        iqr = q3 - q1
        upper = q3 + 1.5 * iqr
        product_stage_bounds[f"{product}|{stage}"] = {"upper": float(upper)}

    duration_threshold = float(frame["step_duration_minutes"].dropna().quantile(0.95)) if frame["step_duration_minutes"].notna().any() else 210.0
    delay_threshold = float(frame["delay_since_previous_step_minutes"].dropna().quantile(0.95)) if frame["delay_since_previous_step_minutes"].notna().any() else 180.0

    return {
        "stage_loss_thresholds": stage_loss_thresholds,
        "product_stage_bounds": product_stage_bounds,
        "duration_threshold": duration_threshold if duration_threshold > 0 else 210.0,
        "delay_threshold": delay_threshold if delay_threshold > 0 else 180.0,
    }


def _artifact_missing_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "artifact" in message and "missing" in message


def _fallback_predict_from_feature_records(feature_records: List[Dict]) -> Dict:
    critical_row = _select_critical_feature_row(feature_records, product=None, critical_stage=None)
    baseline = estimate_loss_with_stage_baseline(critical_row)
    predicted_loss = _safe_float(baseline.get("estimate_loss_pct"), 0.0)
    predicted_efficiency = max(0.0, min(100.0, 100.0 - predicted_loss))
    stage = str(
        critical_row.get("process_type")
        or critical_row.get("stage")
        or critical_row.get("stage_canonical")
        or "unknown"
    )
    return {
        "mode": "predictive",
        "batch_id": str(critical_row.get("batch_id")) if critical_row.get("batch_id") is not None else None,
        "product": str(critical_row.get("product") or "unknown"),
        "critical_stage": stage,
        "predicted_loss_pct": predicted_loss,
        "predicted_efficiency_pct": predicted_efficiency,
        "risk_level": assign_thresholded_risk_level(predicted_loss),
        "risk_method": "baseline_threshold_fallback",
        "risk_thresholds_used": get_risk_thresholds(),
        "top_signals": [
            f"baseline_type:{baseline.get('baseline_type', 'global_mean_loss')}",
            f"baseline_confidence:{baseline.get('confidence_label', 'low')}",
        ],
        "model_version": "artifact_fallback_v1",
        "feature_schema_version": "phase4-v1",
        "warning_flags": ["model_artifacts_missing_fallback"],
        "latency_ms": None,
    }


def _fallback_assess_from_feature_records(feature_records: List[Dict], batch_id: Optional[UUID]) -> Dict:
    critical_row = _select_critical_feature_row(feature_records, product=None, critical_stage=None)
    baseline = estimate_loss_with_stage_baseline(critical_row)
    observed_loss = _safe_float(critical_row.get("loss_pct"), _safe_float(baseline.get("estimate_loss_pct"), 0.0))
    observed_efficiency = _safe_float(critical_row.get("efficiency_pct"), max(0.0, min(100.0, 100.0 - observed_loss)))
    stage = str(
        critical_row.get("process_type")
        or critical_row.get("stage")
        or critical_row.get("stage_canonical")
        or "unknown"
    )
    anomaly = detect_assessment_anomalies(
        {
            **critical_row,
            "critical_stage": stage,
            "loss_pct": observed_loss,
            "efficiency_pct": observed_efficiency,
        },
        historical_context=_assessment_historical_context(feature_records),
    )
    return {
        "mode": "assessment",
        "batch_id": str(batch_id) if batch_id is not None else None,
        "product": str(critical_row.get("product") or "unknown"),
        "critical_stage": stage,
        "observed_loss_pct": observed_loss,
        "observed_efficiency_pct": observed_efficiency,
        "benchmark_predicted_loss_pct": _safe_float(baseline.get("estimate_loss_pct"), observed_loss),
        "risk_level": assign_thresholded_risk_level(observed_loss),
        "anomaly_score": _safe_float(anomaly.get("severity"), 0.0),
        "is_anomalous": bool(anomaly.get("is_anomalous", False)),
        "top_signals": [
            f"baseline_type:{baseline.get('baseline_type', 'global_mean_loss')}",
            f"anomaly_flags:{len(anomaly.get('anomaly_flags', []))}",
        ],
    }


def train(db: Session, run_name: str) -> Dict:
    from app.ml.training.trainer import train_models

    return train_models(db, run_name)


def get_features(db: Session, batch_id: UUID) -> List[Dict]:
    feature_set = build_features(db, batch_id)
    if feature_set.features.empty:
        raise ValidationError("No features available for this batch.")
    return feature_set.raw


def _attach_confidence_decision(db: Session, recommendation: Dict, context_snapshot: Dict) -> Dict:
    from app.ml.recommendations.impact_engine import recommend_action_with_confidence

    candidate_actions = recommendation.get("recommended_actions") or []
    fallback_action = candidate_actions[0] if candidate_actions else "Continue current process and request manual review."
    decision = recommend_action_with_confidence(
        db,
        context_snapshot=context_snapshot,
        candidate_actions=candidate_actions,
        fallback_action=fallback_action,
    )

    ranked_actions = decision.get("ranked_actions") or []
    if ranked_actions:
        recommendation["recommended_actions"] = [item["action"] for item in ranked_actions]
    if decision.get("selected_action"):
        selected = decision["selected_action"]
        recommendation["recommended_actions"] = [selected] + [
            item for item in recommendation["recommended_actions"] if item != selected
        ]
    if decision.get("manual_review_required"):
        signals = recommendation.get("reasoning_signals") or []
        if "Manual review required" not in signals:
            signals.append("Manual review required")
        if LIMITED_CONFIDENCE_SIGNAL not in signals:
            signals.append(LIMITED_CONFIDENCE_SIGNAL)
        recommendation["reasoning_signals"] = signals

    recommendation["decision"] = decision
    recommendation.setdefault("source", "rule_engine")
    return recommendation


def _dataset_row_count(db: Session) -> int:
    feature_set = build_features(db)
    if feature_set.features.empty:
        return 0
    return int(len(feature_set.features))


def _record_has_any_feature(records: List[Dict], feature_keys: set[str]) -> bool:
    for row in records:
        for key in feature_keys:
            if key in row and row.get(key) is not None:
                return True
    return False


def _build_truthfulness_metadata(db: Session, recommendation: Dict, feature_records: List[Dict]) -> Dict:
    dataset_n = _dataset_row_count(db)
    active_model = get_active_model_version()
    model_gate_status, model_gate_passed, gate_fallback_reason = evaluate_model_gate(active_model)
    decision = recommendation.get("decision") or {}
    ml_support_used = bool(decision.get("model_version"))
    mode = recommendation_mode(
        recommendation_source=str(recommendation.get("source") or "rule_engine"),
        ml_support_used=ml_support_used,
        promoted_by_policy=False,
    )
    fallback_reason = decision.get("fallback_reason") or gate_fallback_reason
    include_duration = _record_has_any_feature(feature_records, DURATION_FEATURE_KEYS)
    include_weather = _record_has_any_feature(feature_records, WEATHER_FEATURE_KEYS)
    evidence_sources = infer_evidence_sources(
        include_weather=include_weather,
        include_duration=include_duration,
        include_ml_support=ml_support_used,
    )
    return build_readiness_metadata(
        dataset_n=dataset_n,
        model_gate_status=model_gate_status,
        model_gate_passed=model_gate_passed,
        mode=mode,
        evidence_sources=evidence_sources,
        fallback_reason=fallback_reason,
        caveat=ADVISORY_CAVEAT,
    )


def predict(
    db: Session,
    features: List[PredictiveFeaturePayload],
    include_explanation: bool = False,
) -> Dict:
    start = time.perf_counter()
    from app.ml.inference.predictor import predict_from_features

    df = pd.DataFrame([item.model_dump() for item in features])
    try:
        prediction = predict_from_features(db, df)
    except ValidationError as exc:
        if not _artifact_missing_error(exc):
            raise
        prediction = _fallback_predict_from_feature_records(feature_records=df.to_dict(orient="records"))
    feature_records = df.to_dict(orient="records")
    recommendation = build_recommendation(prediction)
    recommendation = _attach_confidence_decision(
        db,
        recommendation=recommendation,
        context_snapshot={"prediction": prediction, "features": feature_records[:3]},
    )
    metadata = _build_truthfulness_metadata(db, recommendation, feature_records)

    critical_row = _select_critical_feature_row(
        feature_records,
        product=prediction.get("product"),
        critical_stage=prediction.get("critical_stage"),
    )
    baseline_estimate = estimate_loss_with_stage_baseline(critical_row)
    critical_risk_advisory = compute_critical_risk_advisory(
        critical_row,
        baseline_estimate=baseline_estimate,
        predicted_loss_pct=_safe_float(prediction.get("predicted_loss_pct"), 0.0),
    )
    ranked_recommendations = rank_rule_recommendations(
        recommendation.get("recommended_actions", []),
        feature_row={**critical_row, "predicted_loss_pct": prediction.get("predicted_loss_pct")},
        critical_risk_advisory=critical_risk_advisory,
        anomaly_diagnostics=None,
        mode="predictive",
    )

    prediction.update(
        {
            "baseline_estimate": baseline_estimate,
            "critical_risk_advisory": critical_risk_advisory,
            "ml_strategy": ML_STRATEGY,
            "benchmark_source": BENCHMARK_SOURCE,
            "integrated_strategy": True,
            "advisory_only": True,
        }
    )
    recommendation.update(
        {
            "ranked_recommendations": ranked_recommendations,
            "ml_strategy": ML_STRATEGY,
            "benchmark_source": BENCHMARK_SOURCE,
            "integrated_strategy": True,
            "advisory_only": True,
        }
    )

    prediction.update(metadata)
    recommendation.update(metadata)

    explanation = None
    if include_explanation:
        explanation = generate_explanation(
            {
                "mode": "predictive",
                "prediction": prediction,
                "recommendation": recommendation,
                "features": feature_records[:3],
            }
        )

    recommendation_log = MLRecommendationLog(
        batch_id=None,
        structured_recommendation=recommendation,
        llm_explanation=explanation,
    )
    db.add(recommendation_log)
    db.commit()

    active_model = get_active_model_version()
    input_summary = {
        "rows": int(len(df)),
        "products": sorted({str(item.get("product")) for item in feature_records}),
        "stages": sorted({str(item.get("process_type")) for item in feature_records}),
    }
    append_prediction_log(
        {
            "model_version": prediction.get("model_version"),
            "active_model_version": active_model.get("model_version") if active_model else None,
            "feature_schema_version": prediction.get("feature_schema_version"),
            "input_summary": input_summary,
            "predicted_loss_pct": prediction.get("predicted_loss_pct"),
            "risk_level": prediction.get("risk_level"),
            "risk_method": prediction.get("risk_method"),
            "anomaly_flag": False,
            "top_signals": prediction.get("top_signals", []),
            "recommendation_log_id": str(recommendation_log.id),
            "recommendation_actions": recommendation.get("recommended_actions", []),
            "warning_flags": prediction.get("warning_flags", []),
            "latency_ms": round((time.perf_counter() - start) * 1000.0, 2),
            "data_quality": {
                "include_explanation": bool(include_explanation),
                "feature_rows": int(len(feature_records)),
            },
        }
    )

    return {
        "prediction": prediction,
        "recommendation": recommendation,
        "explanation": explanation,
        "recommendation_log_id": recommendation_log.id,
    }


def assess(
    db: Session,
    batch_id: Optional[UUID] = None,
    features: Optional[List[AssessmentFeaturePayload]] = None,
    include_explanation: bool = False,
) -> Dict:
    if batch_id:
        from app.ml.inference.predictor import assess_for_batch

        feature_set = build_features(db, batch_id)
        feature_records = feature_set.raw
        try:
            assessment = assess_for_batch(db, str(batch_id))
        except ValidationError as exc:
            if not _artifact_missing_error(exc):
                raise
            assessment = _fallback_assess_from_feature_records(feature_records, batch_id)
    elif features:
        from app.ml.inference.predictor import assess_from_features

        df = pd.DataFrame([item.model_dump() for item in features])
        feature_records = df.to_dict(orient="records")
        try:
            assessment = assess_from_features(df)
        except ValidationError as exc:
            if not _artifact_missing_error(exc):
                raise
            assessment = _fallback_assess_from_feature_records(feature_records, None)
    else:
        raise ValidationError("Provide batch_id or assessment feature payload.")

    recommendation = build_recommendation(assessment)
    recommendation = _attach_confidence_decision(
        db,
        recommendation=recommendation,
        context_snapshot={"assessment": assessment, "features": feature_records[:3]},
    )
    metadata = _build_truthfulness_metadata(db, recommendation, feature_records)

    critical_row = _select_critical_feature_row(
        feature_records,
        product=assessment.get("product"),
        critical_stage=assessment.get("critical_stage"),
    )
    baseline_estimate = estimate_loss_with_stage_baseline(critical_row)
    critical_risk_advisory = compute_critical_risk_advisory(
        critical_row,
        baseline_estimate=baseline_estimate,
        observed_loss_pct=_safe_float(assessment.get("observed_loss_pct"), 0.0),
    )
    anomaly_diagnostics = detect_assessment_anomalies(
        {
            **critical_row,
            "critical_stage": assessment.get("critical_stage"),
            "product": assessment.get("product"),
            "loss_pct": assessment.get("observed_loss_pct"),
            "efficiency_pct": assessment.get("observed_efficiency_pct"),
        },
        historical_context=_assessment_historical_context(feature_records),
    )
    ranked_recommendations = rank_rule_recommendations(
        recommendation.get("recommended_actions", []),
        feature_row={**critical_row, "loss_pct": assessment.get("observed_loss_pct")},
        critical_risk_advisory=critical_risk_advisory,
        anomaly_diagnostics=anomaly_diagnostics,
        mode="assessment",
    )

    assessment.update(
        {
            "baseline_estimate": baseline_estimate,
            "critical_risk_advisory": critical_risk_advisory,
            "assessment_anomaly_diagnostics": anomaly_diagnostics,
            "ml_strategy": ML_STRATEGY,
            "benchmark_source": BENCHMARK_SOURCE,
            "integrated_strategy": True,
            "advisory_only": True,
        }
    )
    recommendation.update(
        {
            "ranked_recommendations": ranked_recommendations,
            "ml_strategy": ML_STRATEGY,
            "benchmark_source": BENCHMARK_SOURCE,
            "integrated_strategy": True,
            "advisory_only": True,
        }
    )

    assessment.update(metadata)
    recommendation.update(metadata)

    explanation = None
    if include_explanation:
        explanation = generate_explanation(
            {
                "mode": "assessment",
                "assessment": assessment,
                "recommendation": recommendation,
                "features": feature_records[:3],
            }
        )

    recommendation_log = MLRecommendationLog(
        batch_id=batch_id,
        structured_recommendation=recommendation,
        llm_explanation=explanation,
    )
    db.add(recommendation_log)
    db.commit()

    return {
        "assessment": assessment,
        "recommendation": recommendation,
        "explanation": explanation,
        "recommendation_log_id": recommendation_log.id,
    }


def get_recommendation(db: Session, batch_id: UUID, include_explanation: bool = False) -> Dict:
    payload = assess(db, batch_id=batch_id, include_explanation=include_explanation)
    return {
        "assessment": payload["assessment"],
        "recommendation": payload["recommendation"],
        "explanation": payload.get("explanation"),
        "recommendation_log_id": payload.get("recommendation_log_id"),
    }


def log_feedback(db: Session, payload: RecommendationFeedbackCreate) -> RecommendationFeedbackLog:
    from app.ml.recommendations.impact_engine import should_assign_holdout

    recommendation_log_id = payload.recommendation_log_id
    recommendation_snapshot = dict(payload.recommendation_snapshot)

    if recommendation_log_id and not recommendation_snapshot:
        recommendation_log = db.scalar(select(MLRecommendationLog).where(MLRecommendationLog.id == recommendation_log_id))
        if recommendation_log:
            recommendation_snapshot = recommendation_log.structured_recommendation or {}

    delta_loss = None
    if payload.loss_before is not None and payload.loss_after is not None:
        delta_loss = payload.loss_before - payload.loss_after

    outcome_label = payload.outcome_label
    if outcome_label is None and delta_loss is not None:
        if delta_loss >= 1.0:
            outcome_label = "helpful"
        elif delta_loss <= -0.5:
            outcome_label = "harmful"
        else:
            outcome_label = "neutral"

    is_holdout = should_assign_holdout(str(recommendation_log_id) if recommendation_log_id else None)

    feedback = RecommendationFeedbackLog(
        recommendation_log_id=recommendation_log_id,
        batch_id=payload.batch_id,
        stage=payload.stage,
        context_snapshot=dict(payload.context_snapshot),
        recommendation_snapshot=recommendation_snapshot,
        accepted=payload.accepted,
        executed=payload.executed,
        outcome_window_hours=payload.outcome_window_hours,
        outcome_recorded_at=datetime.now(timezone.utc) if (payload.loss_before is not None or payload.loss_after is not None or payload.outcome_label is not None) else None,
        loss_before=payload.loss_before,
        loss_after=payload.loss_after,
        delta_loss=delta_loss,
        operator_reason=payload.operator_reason,
        outcome_label=outcome_label,
        confidence_score=payload.confidence_score,
        confidence_bucket=payload.confidence_bucket,
        harmful_probability=payload.harmful_probability,
        manual_review_required=payload.manual_review_required,
        is_holdout=is_holdout,
        model_version=payload.model_version,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def reliability_status(db: Session) -> Dict:
    from app.ml.recommendations.impact_engine import reliability_status as impact_reliability_status

    return impact_reliability_status(db)


def health(db: Session) -> Dict:
    from app.ml.recommendations.impact_engine import reliability_status as impact_reliability_status

    status = artifacts_status()
    compatibility = artifact_compatibility_status()
    reliability = impact_reliability_status(db)
    models_ready = all(status.values())
    model_version = None
    if models_ready:
        try:
            model_version = load_model_bundle().metadata.get("model_version")
        except ValidationError:
            models_ready = False

    last_run = db.scalar(select(MLTrainingRun).order_by(MLTrainingRun.completed_at.desc()))
    active_model = get_active_model_version()

    return {
        "models_ready": models_ready,
        "model_version": model_version,
        "active_model_version": active_model.get("model_version") if active_model else None,
        "last_training_time": last_run.completed_at if last_run else None,
        "available_artifacts": {
            **status,
            "artifact_compatible": bool(compatibility.get("compatible", False)),
            "impact_recommender": bool(reliability.get("impact_model_ready", False)),
        },
    }
