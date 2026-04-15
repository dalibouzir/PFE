from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_manager, get_current_user
from app.db.session import get_db
from app.schemas.analytics import AnomalyResponse, DashboardResponse, RecommendationResponse
from app.schemas.batch import BatchMetricsSummary
from app.services import analytics as analytics_service


router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard", response_model=DashboardResponse, summary="Return the manager dashboard summary for the current cooperative.")
def get_dashboard(db: Session = Depends(get_db), current_manager=Depends(get_current_manager)):
    return analytics_service.get_dashboard(db, current_manager)


@router.get("/batches/{batch_id}/metrics", response_model=BatchMetricsSummary, summary="Return aggregated metrics for a batch.")
def get_batch_metrics(batch_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    batch = analytics_service.get_batch_for_user(db, current_user, batch_id)
    return analytics_service.compute_batch_metrics(db, batch.id)


@router.get("/batches/{batch_id}/anomaly", response_model=AnomalyResponse, summary="Run deterministic anomaly checks for a batch.")
def get_batch_anomaly(batch_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    batch = analytics_service.get_batch_for_user(db, current_user, batch_id)
    return analytics_service.detect_anomaly(db, batch.id)


@router.get("/batches/{batch_id}/recommendation", response_model=RecommendationResponse, summary="Generate or refresh a rule-based recommendation for a batch.")
def get_batch_recommendation(batch_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    batch = analytics_service.get_batch_for_user(db, current_user, batch_id)
    recommendation = analytics_service.generate_recommendation(db, batch.id)
    db.commit()
    return recommendation
