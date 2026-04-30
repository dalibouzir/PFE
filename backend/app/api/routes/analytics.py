from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_cooperative_user, get_current_manager, get_current_user
from app.db.session import get_db
from app.schemas.analytics import (
    AnomalyResponse,
    CostBreakdownRow,
    DashboardResponse,
    PreHarvestCostBreakdownResponse,
    PreHarvestSummaryResponse,
    RecommendationResponse,
)
from app.schemas.batch import BatchMetricsSummary
from app.services import analytics as analytics_service
from app.services import preharvest_analytics


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


@router.get("/pre-harvest/summary", response_model=PreHarvestSummaryResponse, summary="Pre-harvest analytics summary.")
def preharvest_summary(db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_user)):
    return PreHarvestSummaryResponse.model_validate(preharvest_analytics.get_summary(db, current_user))


@router.get("/pre-harvest/costs-by-farmer", response_model=PreHarvestCostBreakdownResponse, summary="Pre-harvest costs grouped by farmer.")
def preharvest_costs_by_farmer(db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_user)):
    rows = [CostBreakdownRow.model_validate(item) for item in preharvest_analytics.costs_by_farmer(db, current_user)]
    return PreHarvestCostBreakdownResponse(items=rows)


@router.get("/pre-harvest/costs-by-parcel", response_model=PreHarvestCostBreakdownResponse, summary="Pre-harvest costs grouped by parcel.")
def preharvest_costs_by_parcel(db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_user)):
    rows = [CostBreakdownRow.model_validate(item) for item in preharvest_analytics.costs_by_parcel(db, current_user)]
    return PreHarvestCostBreakdownResponse(items=rows)


@router.get("/pre-harvest/costs-by-crop", response_model=PreHarvestCostBreakdownResponse, summary="Pre-harvest costs grouped by crop.")
def preharvest_costs_by_crop(db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_user)):
    rows = [CostBreakdownRow.model_validate(item) for item in preharvest_analytics.costs_by_crop(db, current_user)]
    return PreHarvestCostBreakdownResponse(items=rows)


@router.get("/pre-harvest/costs-by-hectare", response_model=PreHarvestCostBreakdownResponse, summary="Pre-harvest costs per hectare by parcel.")
def preharvest_costs_by_hectare(db: Session = Depends(get_db), current_user=Depends(get_current_cooperative_user)):
    rows = [CostBreakdownRow.model_validate(item) for item in preharvest_analytics.costs_by_hectare(db, current_user)]
    return PreHarvestCostBreakdownResponse(items=rows)
