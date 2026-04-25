from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.features.engineer import build_features
from app.ml.inference.predictor import assess_for_batch, assess_from_features, predict_from_features
from app.ml.llm.provider import generate_explanation
from app.ml.recommendations.impact_engine import (
    reliability_status as impact_reliability_status,
    recommend_action_with_confidence,
    should_assign_holdout,
)
from app.ml.recommendations.rule_engine import build_recommendation
from app.ml.training.trainer import train_models
from app.ml.utils.model_store import artifacts_status, load_model_bundle
from app.models.ml import MLRecommendationLog, MLTrainingRun, RecommendationFeedbackLog
from app.schemas.ml import AssessmentFeaturePayload, PredictiveFeaturePayload, RecommendationFeedbackCreate
from app.utils.exceptions import ValidationError


def train(db: Session, run_name: str) -> Dict:
    return train_models(db, run_name)


def get_features(db: Session, batch_id: UUID) -> List[Dict]:
    feature_set = build_features(db, batch_id)
    if feature_set.features.empty:
        raise ValidationError("No features available for this batch.")
    return feature_set.raw


def _attach_confidence_decision(db: Session, recommendation: Dict, context_snapshot: Dict) -> Dict:
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
        recommendation["reasoning_signals"] = signals

    recommendation["decision"] = decision
    return recommendation


def predict(
    db: Session,
    features: List[PredictiveFeaturePayload],
    include_explanation: bool = False,
) -> Dict:
    df = pd.DataFrame([item.model_dump() for item in features])
    prediction = predict_from_features(db, df)
    feature_records = df.to_dict(orient="records")
    recommendation = build_recommendation(prediction)
    recommendation = _attach_confidence_decision(
        db,
        recommendation=recommendation,
        context_snapshot={"prediction": prediction, "features": feature_records[:3]},
    )

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
        assessment = assess_for_batch(db, str(batch_id))
        feature_set = build_features(db, batch_id)
        feature_records = feature_set.raw
    elif features:
        df = pd.DataFrame([item.model_dump() for item in features])
        assessment = assess_from_features(df)
        feature_records = df.to_dict(orient="records")
    else:
        raise ValidationError("Provide batch_id or assessment feature payload.")

    recommendation = build_recommendation(assessment)
    recommendation = _attach_confidence_decision(
        db,
        recommendation=recommendation,
        context_snapshot={"assessment": assessment, "features": feature_records[:3]},
    )

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
    return impact_reliability_status(db)


def health(db: Session) -> Dict:
    status = artifacts_status()
    reliability = impact_reliability_status(db)
    models_ready = all(status.values())
    model_version = None
    if models_ready:
        try:
            model_version = load_model_bundle().metadata.get("model_version")
        except ValidationError:
            models_ready = False

    last_run = db.scalar(select(MLTrainingRun).order_by(MLTrainingRun.completed_at.desc()))
    return {
        "models_ready": models_ready,
        "model_version": model_version,
        "last_training_time": last_run.completed_at if last_run else None,
        "available_artifacts": {
            **status,
            "impact_recommender": bool(reliability.get("impact_model_ready", False)),
        },
    }
