from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MLSchemaBase(BaseModel):
    model_config = ConfigDict(protected_namespaces=())


class MLTrainRequest(MLSchemaBase):
    run_name: str = Field(default="manual")


class MLTrainMetrics(MLSchemaBase):
    regression_mae: float
    regression_rmse: float
    classification_accuracy: float
    classification_f1: float
    anomaly_ratio: float
    recommendation_action_coverage: float
    recommendation_issue_alignment: float
    impact_model_ready: bool = False
    impact_feedback_rows: int = 0
    impact_holdout_rows: int = 0
    impact_precision_at_1: float = 0.0
    impact_harmful_rate: float = 0.0
    impact_calibration_error: float = 0.0
    impact_mean_loss_reduction_after_action: float = 0.0
    impact_holdout_ratio: float = 0.0
    impact_real_feedback_rows: int = 0
    impact_proxy_feedback_rows: int = 0
    impact_coverage: float = 0.0
    impact_recommended_rows: int = 0
    impact_targets_met: bool = False
    impact_used_auto_backfill: bool = False


class MLTrainResponse(MLSchemaBase):
    run_id: UUID
    run_name: str
    trained_rows: int
    model_version: str
    metrics: MLTrainMetrics
    completed_at: datetime


class PredictiveFeaturePayload(MLSchemaBase):
    product: str
    process_type: str
    qty_in: float
    batch_size: float
    stock_level: float
    date: datetime
    month: int
    week_of_year: int
    season: str
    historical_avg_loss_same_product: float
    historical_avg_loss_same_stage: float
    historical_avg_efficiency_same_stage: float
    previous_batch_loss: float
    rolling_loss_last_n_batches: float
    rolling_efficiency_last_n_batches: float


class AssessmentFeaturePayload(PredictiveFeaturePayload):
    qty_out: float
    deviation_from_stage_avg: Optional[float] = None
    loss_pct: Optional[float] = None
    efficiency_pct: Optional[float] = None


class MLReadinessMetadata(MLSchemaBase):
    ml_readiness_state: Optional[str] = None
    dataset_n: Optional[int] = None
    minimum_required_n: Optional[int] = None
    dataset_readiness_level: Optional[str] = None
    model_gate_status: Optional[str] = None
    promoted: Optional[bool] = None
    fallback_reason: Optional[str] = None
    recommendation_mode: Optional[str] = None
    evidence_sources: List[str] = Field(default_factory=list)
    caveat: Optional[str] = None


class BaselineEstimateOutput(MLSchemaBase):
    estimate_loss_pct: float
    baseline_type: str
    evidence_count: int
    confidence_label: str


class CriticalRiskAdvisoryOutput(MLSchemaBase):
    risk_level: str
    risk_score: float
    advisory_flags: List[str] = Field(default_factory=list)
    caveat: Optional[str] = None


class AssessmentAnomalyDiagnosticsOutput(MLSchemaBase):
    is_anomalous: bool
    anomaly_flags: List[str] = Field(default_factory=list)
    severity: float
    severity_label: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    explanation: str


class RankedRecommendationAdvisoryOutput(MLSchemaBase):
    action: str
    priority_score: float
    priority_reason: str


class MLPredictRequest(MLSchemaBase):
    features: List[PredictiveFeaturePayload]
    include_explanation: bool = False


class MLAssessRequest(MLSchemaBase):
    batch_id: Optional[UUID] = None
    features: Optional[List[AssessmentFeaturePayload]] = None
    include_explanation: bool = False


class MLPredictionOutput(MLReadinessMetadata):
    mode: str
    batch_id: Optional[str]
    product: str
    critical_stage: str
    predicted_loss_pct: float
    predicted_efficiency_pct: float
    risk_level: str
    risk_method: str
    risk_thresholds_used: Dict[str, float]
    top_signals: List[str]
    model_version: Optional[str] = None
    feature_schema_version: Optional[str] = None
    warning_flags: List[str] = Field(default_factory=list)
    latency_ms: Optional[float] = None
    baseline_estimate: Optional[BaselineEstimateOutput] = None
    critical_risk_advisory: Optional[CriticalRiskAdvisoryOutput] = None
    ml_strategy: Optional[str] = None
    benchmark_source: Optional[str] = None
    integrated_strategy: Optional[bool] = None
    advisory_only: Optional[bool] = None


class MLAssessmentOutput(MLReadinessMetadata):
    mode: str
    batch_id: Optional[str]
    product: str
    critical_stage: str
    observed_loss_pct: float
    observed_efficiency_pct: float
    benchmark_predicted_loss_pct: float
    risk_level: str
    anomaly_score: float
    is_anomalous: bool
    top_signals: List[str]
    baseline_estimate: Optional[BaselineEstimateOutput] = None
    critical_risk_advisory: Optional[CriticalRiskAdvisoryOutput] = None
    assessment_anomaly_diagnostics: Optional[AssessmentAnomalyDiagnosticsOutput] = None
    ml_strategy: Optional[str] = None
    benchmark_source: Optional[str] = None
    integrated_strategy: Optional[bool] = None
    advisory_only: Optional[bool] = None


class RankedActionOutput(MLSchemaBase):
    action: str
    expected_loss_reduction: float
    harmful_probability: float
    confidence_score: float


class RecommendationDecisionOutput(MLSchemaBase):
    selected_action: str
    expected_loss_reduction: float
    harmful_probability: float
    confidence_score: float
    confidence_bucket: Literal["High", "Medium", "Low"]
    manual_review_required: bool
    abstained: bool
    fallback_reason: Optional[str] = None
    drift_detected: bool = False
    calibration_drift: float = 0.0
    model_version: Optional[str] = None
    ranked_actions: List[RankedActionOutput] = Field(default_factory=list)


class RecommendationOutput(MLReadinessMetadata):
    issue_type: str
    critical_stage: str
    severity: str
    recommended_actions: List[str]
    reasoning_signals: List[str]
    decision: Optional[RecommendationDecisionOutput] = None
    ranked_recommendations: List[RankedRecommendationAdvisoryOutput] = Field(default_factory=list)
    ml_strategy: Optional[str] = None
    benchmark_source: Optional[str] = None
    integrated_strategy: Optional[bool] = None
    advisory_only: Optional[bool] = None


class MLPredictResponse(MLSchemaBase):
    prediction: MLPredictionOutput
    recommendation: RecommendationOutput
    explanation: Optional[str] = None
    recommendation_log_id: Optional[UUID] = None


class MLAssessResponse(MLSchemaBase):
    assessment: MLAssessmentOutput
    recommendation: RecommendationOutput
    explanation: Optional[str] = None
    recommendation_log_id: Optional[UUID] = None


class MLHealthResponse(MLSchemaBase):
    models_ready: bool
    model_version: Optional[str]
    active_model_version: Optional[str] = None
    last_training_time: Optional[datetime]
    available_artifacts: Dict[str, bool]


class MLFeaturesResponse(MLSchemaBase):
    batch_id: UUID
    features: List[AssessmentFeaturePayload]


class MLRecommendationResponse(MLSchemaBase):
    batch_id: UUID
    assessment: MLAssessmentOutput
    recommendation: RecommendationOutput
    explanation: Optional[str] = None
    recommendation_log_id: Optional[UUID] = None


class RecommendationFeedbackCreate(MLSchemaBase):
    recommendation_log_id: Optional[UUID] = None
    batch_id: Optional[UUID] = None
    stage: Optional[str] = None
    context_snapshot: Dict[str, Any] = Field(default_factory=dict)
    recommendation_snapshot: Dict[str, Any] = Field(default_factory=dict)
    accepted: bool = False
    executed: bool = False
    outcome_window_hours: int = 48
    loss_before: Optional[float] = None
    loss_after: Optional[float] = None
    operator_reason: Optional[str] = None
    outcome_label: Optional[Literal["helpful", "neutral", "harmful"]] = None
    confidence_score: Optional[float] = None
    confidence_bucket: Optional[Literal["High", "Medium", "Low"]] = None
    harmful_probability: Optional[float] = None
    manual_review_required: bool = False
    model_version: Optional[str] = None
    rating: Optional[int] = None
    comment: Optional[str] = None


class RecommendationFeedbackRead(MLSchemaBase):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: UUID
    recommendation_log_id: Optional[UUID] = None
    batch_id: Optional[UUID] = None
    stage: Optional[str] = None
    accepted: bool
    executed: bool
    outcome_window_hours: int
    loss_before: Optional[float] = None
    loss_after: Optional[float] = None
    delta_loss: Optional[float] = None
    operator_reason: Optional[str] = None
    outcome_label: Optional[str] = None
    confidence_score: Optional[float] = None
    confidence_bucket: Optional[str] = None
    harmful_probability: Optional[float] = None
    manual_review_required: bool
    is_holdout: bool
    model_version: Optional[str] = None
    created_at: datetime


class MLReliabilityStatusResponse(MLSchemaBase):
    impact_model_ready: bool
    offline_metrics: Dict[str, Any] = Field(default_factory=dict)
    calibration_drift: float = 0.0
    drift_blocking_recommendations: bool = False
    model_version: Optional[str] = None
    targets: Dict[str, Any] = Field(default_factory=dict)
    targets_met: bool = False


class MLLogResponse(MLSchemaBase):
    prediction_log_id: Optional[UUID] = None
    recommendation_log_id: Optional[UUID] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
