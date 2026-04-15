from typing import List
from uuid import UUID

from pydantic import BaseModel

from app.schemas.input import InputRead
from app.schemas.process_step import ProcessStepRead
from app.schemas.stock import StockAlertRead


class AnomalyResponse(BaseModel):
    batch_id: UUID
    anomaly_detected: bool
    anomaly_score: float
    reasons: List[str]


class RecommendationResponse(BaseModel):
    batch_id: UUID
    loss_pct: float
    efficiency_pct: float
    anomaly_detected: bool
    anomaly_score: float
    risk_level: str
    suggested_action: str
    rationale: str
    reasons: List[str]


class DashboardResponse(BaseModel):
    total_production: float
    loss_rate: float
    efficiency_rate: float
    number_of_active_batches: int
    stock_alerts: List[StockAlertRead]
    recent_inputs: List[InputRead]
    recent_process_steps: List[ProcessStepRead]
    recent_recommendations: List[RecommendationResponse]
