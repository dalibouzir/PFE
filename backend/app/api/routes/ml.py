from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_manager
from app.db.session import get_db
from app.schemas.ml import (
    MLAssessRequest,
    MLAssessResponse,
    MLFeaturesResponse,
    MLHealthResponse,
    MLReliabilityStatusResponse,
    MLPredictRequest,
    MLPredictResponse,
    MLRecommendationResponse,
    RecommendationFeedbackCreate,
    RecommendationFeedbackRead,
    MLTrainRequest,
    MLTrainResponse,
)
from app.services import ml as ml_service
from app.services.rag_reindex_hooks import reindex_ml_prediction_if_needed


router = APIRouter(prefix="/ml", tags=["ML"])


@router.post("/train", response_model=MLTrainResponse, summary="Train ML models on available data.")
def train_models(payload: MLTrainRequest, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    result = ml_service.train(db, payload.run_name)
    return MLTrainResponse(
        run_id=result["run_id"],
        run_name=result["run_name"],
        trained_rows=result["trained_rows"],
        model_version=result["model_version"],
        metrics=result["metrics"],
        completed_at=result["completed_at"],
    )


@router.post("/predict", response_model=MLPredictResponse, summary="Predict stage loss/risk before stage completion.")
def predict(payload: MLPredictRequest, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    result = ml_service.predict(
        db,
        features=payload.features,
        include_explanation=payload.include_explanation,
    )
    # TODO(phase3): move this hook to service once user-scoped context is propagated in ml_service signatures.
    reindex_ml_prediction_if_needed(
        db,
        current_user=current_manager,
        prediction_log_id=None,
        batch_id=None,
        cooperative_id=current_manager.cooperative_id,
    )
    return MLPredictResponse(
        prediction=result["prediction"],
        recommendation=result["recommendation"],
        explanation=result.get("explanation"),
        recommendation_log_id=result.get("recommendation_log_id"),
    )


@router.post("/assess", response_model=MLAssessResponse, summary="Assess completed stage outcomes and anomaly signals.")
def assess(payload: MLAssessRequest, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    result = ml_service.assess(
        db,
        batch_id=payload.batch_id,
        features=payload.features,
        include_explanation=payload.include_explanation,
    )
    # TODO(phase3): move this hook to service once user-scoped context is propagated in ml_service signatures.
    reindex_ml_prediction_if_needed(
        db,
        current_user=current_manager,
        prediction_log_id=None,
        batch_id=payload.batch_id,
        cooperative_id=current_manager.cooperative_id,
    )
    return MLAssessResponse(
        assessment=result["assessment"],
        recommendation=result["recommendation"],
        explanation=result.get("explanation"),
        recommendation_log_id=result.get("recommendation_log_id"),
    )


@router.get("/health", response_model=MLHealthResponse, summary="Return ML model availability and training status.")
def health(db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return ml_service.health(db)


@router.get("/features/{batch_id}", response_model=MLFeaturesResponse, summary="Return engineered assessment features for a batch.")
def features(batch_id: UUID, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    features_payload = ml_service.get_features(db, batch_id)
    return MLFeaturesResponse(batch_id=batch_id, features=features_payload)


@router.get("/recommendation/{batch_id}", response_model=MLRecommendationResponse, summary="Return recommendation from assessed batch outcomes.")
def recommendation(batch_id: UUID, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    payload = ml_service.get_recommendation(db, batch_id, include_explanation=True)
    return MLRecommendationResponse(
        batch_id=batch_id,
        assessment=payload["assessment"],
        recommendation=payload["recommendation"],
        explanation=payload.get("explanation"),
        recommendation_log_id=payload.get("recommendation_log_id"),
    )


@router.post("/feedback", response_model=RecommendationFeedbackRead, summary="Log operator feedback and observed outcomes for a recommendation.")
def feedback(payload: RecommendationFeedbackCreate, db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    feedback_row = ml_service.log_feedback(db, payload)
    reindex_ml_prediction_if_needed(
        db,
        current_user=current_manager,
        prediction_log_id=None,
        batch_id=payload.batch_id,
        cooperative_id=current_manager.cooperative_id,
    )
    return feedback_row


@router.get("/reliability", response_model=MLReliabilityStatusResponse, summary="Return offline recommendation reliability metrics and drift status.")
def reliability(db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return ml_service.reliability_status(db)
